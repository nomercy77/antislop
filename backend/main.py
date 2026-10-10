"""Run with: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000.

HTTP endpoints never expose a demo authentication bypass. Unconfigured external
services fail explicitly. Submitted repositories are never cloned or executed.
"""
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlparse
import base64
import hashlib
import hmac
import re
import secrets
import time
import uuid

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from antislop.models import Capability as VerificationCapability
from antislop.models import FormalConfiguration, Language as VerificationLanguage, SourceSnapshot, SubmissionCreate
from antislop.plugins.builtins import built_in_registry
from antislop.services.planner import VerificationPlanner
from antislop.services.store import SQLiteSubmissionStore

from .db import Database
from .categories import TaskCategory, TASK_CATEGORIES
from .permissions import effective_permissions
from .security import (OAUTH_COOKIE, OTP_SECONDS, SESSION_COOKIE, SESSION_SECONDS,
                       SMTPMailer, digest, random_token)
from .settings import Settings


def now() -> int:
    return int(time.time())


def identifier() -> str:
    return str(uuid.uuid4())


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OTPRequest(InputModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role: Literal["submitter", "coder"]


class OTPVerify(InputModel):
    email: EmailStr
    code: str = Field(pattern=r"^[0-9]{6}$")


class ApplicationInput(InputModel):
    name: str = Field(min_length=1, max_length=100)
    github: str = Field(max_length=200)
    experience: str = Field(min_length=1, max_length=80)
    specialty: str = Field(min_length=1, max_length=100)
    portfolio: str = Field(max_length=2000)
    bio: str = Field(min_length=20, max_length=5000)
    consent: Literal[True]

    @field_validator("github")
    @classmethod
    def github_profile(cls, value):
        u = urlparse(value)
        if u.scheme != "https" or u.netloc != "github.com" or u.query or u.fragment or not re.fullmatch(r"/[A-Za-z0-9][A-Za-z0-9-]{0,38}/?", u.path):
            raise ValueError("Use an HTTPS GitHub profile URL.")
        return value.rstrip("/")

    @field_validator("portfolio")
    @classmethod
    def portfolio_url(cls, value):
        u = urlparse(value)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            raise ValueError("Use an HTTPS portfolio or work sample URL.")
        return value


class DecisionInput(InputModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    notes: str = Field(default="", max_length=3000)


class ReviewInput(InputModel):
    title: str = Field(min_length=1, max_length=100)
    repo: str = Field(max_length=500)
    sha: str = Field(pattern=r"^[a-fA-F0-9]{40}$")
    stack: str = Field(min_length=1, max_length=100)
    scope: str = Field(min_length=20, max_length=10000)
    budget: int = Field(ge=1, le=1_000_000, strict=True)
    deadline: date
    visibility: Literal["private", "public"] = "private"
    category: TaskCategory = "general"
    verification_languages: set[VerificationLanguage] = Field(default_factory=set)
    verification_capabilities: set[VerificationCapability] = Field(default_factory=set)
    formal: FormalConfiguration | None = None
    expert_work: "ExpertWorkRequest | None" = None

    @field_validator("repo")
    @classmethod
    def github_repo(cls, value):
        u = urlparse(value)
        if u.scheme != "https" or u.netloc != "github.com" or u.query or u.fragment or not re.fullmatch(r"/[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+/?", u.path):
            raise ValueError("Use https://github.com/owner/repository.")
        parts = u.path.rstrip("/").split("/")
        if parts[-1] in {".", ".."}:
            raise ValueError("Invalid repository name.")
        return value.rstrip("/").removesuffix(".git")


class AssignmentInput(InputModel):
    reviewer_id: str = Field(min_length=1, max_length=100)


class ExpertWorkRequest(InputModel):
    kind: Literal["functional-tests", "formal-contracts", "manual-review"]
    tier: Literal["standard", "deep"]


class ExpertDeliveryInput(InputModel):
    summary: str = Field(min_length=20, max_length=10_000)
    artifact_url: str | None = Field(default=None, max_length=2_000)

    @field_validator("artifact_url")
    @classmethod
    def artifact_url_is_https(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("artifact_url must be an HTTPS URL")
        return value


EXPERT_PRICING = {
    "functional-tests": {"standard": 75, "deep": 150},
    "formal-contracts": {"standard": 150, "deep": 300},
    "manual-review": {"standard": 100, "deep": 250},
}


class AccessInput(InputModel):
    target: Literal["platform", "reviewer"]


class MessageInput(InputModel):
    text: str = Field(min_length=1, max_length=4000)


def public_user(row) -> dict:
    status = row.get("verification_status") if row["role"] == "coder" else None
    return {**{key: row[key] for key in ("id", "name", "email", "role")},
            "verification_status": status, "permissions": effective_permissions(row["role"], status)}


def public_application(row) -> dict:
    return {key: row[key] for key in ("id", "user_id", "name", "email", "github", "experience", "specialty", "portfolio", "bio", "status", "notes", "created_at", "updated_at")}


def public_review(row) -> dict:
    return {
        **{key: row[key] for key in ("id", "owner_id", "title", "repo", "sha", "stack", "scope", "budget", "deadline", "visibility", "category", "status", "created_at")},
        "access": row["platform_access"], "expertId": row["reviewer_id"],
        "expertAccess": row["reviewer_access"], "findings": [], "proposals": [], "messages": [],
        "verificationSubmissionId": row["verification_submission_id"],
        "expertWork": {
            "kind": row["expert_work_type"], "tier": row["expert_work_tier"],
            "price": row["expert_work_price"], "status": row["expert_work_status"],
            "deliverySummary": row["expert_delivery_summary"], "deliveryUrl": row["expert_delivery_url"],
        } if row["expert_work_type"] else None,
    }


def rate_limit(conn, kind: str, subject: str, limit: int, period: int, timestamp: int):
    count = conn.execute("SELECT COUNT(*) FROM rate_events WHERE kind=? AND subject=? AND created_at>?", (kind, subject, timestamp - period)).fetchone()[0]
    if count >= limit:
        raise HTTPException(429, "Too many requests. Please try again later.", headers={"Retry-After": str(period)})


def record_rate(conn, kind: str, subject: str, timestamp: int):
    conn.execute("INSERT INTO rate_events(kind,subject,created_at) VALUES (?,?,?)", (kind, subject, timestamp))
    conn.execute("DELETE FROM rate_events WHERE created_at<?", (timestamp - 24 * 60 * 60,))


def create_app(settings: Settings | None = None, *, mailer=None) -> FastAPI:
    # Configuration is resolved at startup, so importing the module is harmless.
    configured = settings.validate() if settings else None

    @asynccontextmanager
    async def lifespan(application):
        s = configured or Settings.from_env()
        application.state.settings = s
        application.state.db = Database(s.database_path)
        application.state.db.initialize()
        application.state.verification_store = SQLiteSubmissionStore(Path(s.verification_database_path))
        application.state.verification_planner = VerificationPlanner(built_in_registry())
        application.state.mailer = mailer or SMTPMailer(s)
        yield

    application = FastAPI(title="Antislop API", version="0.1.0", lifespan=lifespan)
    # CORS origin config is available without requiring a secret during import.
    # At startup Settings.from_env validates the same env values completely.
    import os
    from dotenv import load_dotenv
    load_dotenv()
    origins = configured.cors_origins if configured else tuple(x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://localhost:4173").split(",") if x.strip())
    application.add_middleware(CORSMiddleware, allow_origins=list(origins), allow_credentials=True,
                               allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["Content-Type"])

    @application.middleware("http")
    async def browser_security(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            # Required even for OTP endpoints: blocks cross-site request forgery
            # and login CSRF. Non-browser API clients must supply trusted Origin.
            origin = request.headers.get("origin", "").rstrip("/")
            if origin not in request.app.state.settings.cors_origins:
                return JSONResponse({"detail": "A trusted frontend Origin header is required."}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def current_user(request: Request):
        token = request.cookies.get(SESSION_COOKIE)
        if not token or len(token) > 200:
            raise HTTPException(401, "Sign in to continue.")
        s = request.app.state.settings
        with request.app.state.db.connection() as conn:
            row = conn.execute("SELECT u.*,a.status AS verification_status FROM sessions s JOIN users u ON u.id=s.user_id LEFT JOIN applications a ON a.user_id=u.id WHERE s.digest=? AND s.expires_at>?", (digest(s.secret, "session", token), now())).fetchone()
        if not row:
            raise HTTPException(401, "Your session has expired. Please sign in again.")
        if row["role"] == "team" and row["email"] not in s.staff_emails:
            raise HTTPException(403, "Staff access is no longer authorized.")
        return dict(row)

    def require_role(user, role):
        if user["role"] != role:
            raise HTTPException(403, f"This action requires the {role} workspace.")

    def session_cookie(response, token, s):
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=s.cookie_secure, samesite=s.cookie_samesite, path="/")

    def save_user_and_session(conn, email, name, role, s, timestamp, old_token=None, google_sub=None):
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if google_sub:
            bound = conn.execute("SELECT * FROM users WHERE google_sub=?", (google_sub,)).fetchone()
            if bound and bound["email"] != email:
                raise HTTPException(400, "This Google identity is linked to another email. Sign in by email and contact support.")
            if user and user["google_sub"] and user["google_sub"] != google_sub:
                raise HTTPException(400, "This email is linked to a different Google identity. Sign in by email.")
        if user:
            if user["role"] == "team" and email not in s.staff_emails:
                raise HTTPException(403, "Staff access is no longer authorized.")
            # A role field from a subsequent sign-in can never change identity.
            # Staff is bootstrapped only from operator-configured verified emails.
            if email in s.staff_emails and user["role"] != "team":
                conn.execute("UPDATE users SET role='team' WHERE id=?", (user["id"],))
                user = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        else:
            uid = identifier()
            assigned_role = "team" if email in s.staff_emails else role
            conn.execute("INSERT INTO users(id,email,name,role,created_at) VALUES (?,?,?,?,?)", (uid, email, name, assigned_role, timestamp))
            user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if google_sub and not user["google_sub"]:
            conn.execute("UPDATE users SET google_sub=? WHERE id=?", (google_sub, user["id"]))
        if old_token:
            conn.execute("DELETE FROM sessions WHERE digest=?", (digest(s.secret, "session", old_token),))
        conn.execute("DELETE FROM sessions WHERE expires_at<=?", (timestamp,))
        token = random_token()
        conn.execute("INSERT INTO sessions(digest,user_id,expires_at,created_at) VALUES (?,?,?,?)", (digest(s.secret, "session", token), user["id"], timestamp + SESSION_SECONDS, timestamp))
        result = dict(user)
        application_row = conn.execute("SELECT status FROM applications WHERE user_id=?", (user["id"],)).fetchone()
        result["verification_status"] = application_row["status"] if application_row else None
        return result, token

    def review_for(conn, rid, user, *, owner=False):
        row = conn.execute("SELECT r.*,u.role AS actor_role,a.status AS actor_verification_status FROM reviews r JOIN users u ON u.id=? LEFT JOIN applications a ON a.user_id=u.id WHERE r.id=?", (user["id"], rid)).fetchone()
        # Hide existence and all private review fields from unauthorized users.
        is_owner = bool(row and row["actor_role"] == "submitter" and row["owner_id"] == user["id"])
        is_reviewer = bool(row and row["actor_role"] == "coder" and row["reviewer_id"] == user["id"] and row["actor_verification_status"] == "approved")
        if not row or (not is_owner and (owner or not is_reviewer)):
            raise HTTPException(404, "Review not found.")
        return row

    def event(conn, user, text, rid=None):
        conn.execute("INSERT INTO events(id,actor_id,review_id,text,created_at) VALUES (?,?,?,?,?)", (identifier(), user["id"], rid, text, now()))

    @application.get("/api/health")
    def health():
        return {"status": "ok", "backend": "fastapi"}

    @application.get("/api/config")
    def config(request: Request):
        s = request.app.state.settings
        return {"backend": "fastapi", "mode": "live", "auth": {"email_otp": s.smtp_ready, "google": s.google_ready},
                "github": {"configured": False}, "payments": {"configured": False}, "access_email": "antislop@bee3.in",
                "task_categories": TASK_CATEGORIES}

    @application.post("/api/auth/otp/request")
    def request_otp(body: OTPRequest, request: Request):
        s = request.app.state.settings
        if not s.smtp_ready:
            raise HTTPException(503, "Email sign-in is unavailable until SMTP is configured. No email was sent.")
        timestamp, email = now(), str(body.email).lower()
        ip = request.client.host if request.client else "unknown"
        code = f"{secrets.randbelow(1_000_000):06d}"
        code_digest = digest(s.secret, "otp", email + ":" + code)
        with request.app.state.db.connection(write=True) as conn:
            rate_limit(conn, "otp-email", email, 5, 3600, timestamp)
            rate_limit(conn, "otp-ip", ip, 20, 3600, timestamp)
            previous = conn.execute("SELECT MAX(created_at) AS requested_at FROM rate_events WHERE kind='otp-email' AND subject=?", (email,)).fetchone()
            if previous["requested_at"] is not None and timestamp - previous["requested_at"] < 60:
                raise HTTPException(429, "Wait 60 seconds before requesting another code.", headers={"Retry-After": str(60 - (timestamp - previous["requested_at"]))})
            conn.execute("INSERT INTO otps(email,digest,expires_at,attempts,requested_at,name,role) VALUES (?,?,?,0,?,?,?) ON CONFLICT(email) DO UPDATE SET digest=excluded.digest,expires_at=excluded.expires_at,attempts=0,requested_at=excluded.requested_at,name=excluded.name,role=excluded.role", (email, code_digest, timestamp + OTP_SECONDS, timestamp, body.name, body.role))
            record_rate(conn, "otp-email", email, timestamp)
            record_rate(conn, "otp-ip", ip, timestamp)
        try:
            request.app.state.mailer.send_otp(email, code)
        except Exception:
            with request.app.state.db.connection(write=True) as conn:
                conn.execute("DELETE FROM otps WHERE email=? AND digest=?", (email, code_digest))
            raise HTTPException(503, "Email delivery failed. No usable verification code was issued. Please try again later.") from None
        return {"message": "Verification code sent.", "expires_in": OTP_SECONDS, "resend_after": 60}

    @application.post("/api/auth/otp/verify")
    def verify_otp(body: OTPVerify, request: Request, response: Response):
        s, timestamp = request.app.state.settings, now()
        email = str(body.email).lower()
        ip = request.client.host if request.client else "unknown"
        failure = None
        result = None
        # Both attempt counting and consumption are serialized across workers.
        # Raising outside the transaction ensures failed attempts stay recorded.
        with request.app.state.db.connection(write=True) as conn:
            rate_limit(conn, "verify-ip", ip, 30, 900, timestamp)
            record_rate(conn, "verify-ip", ip, timestamp)
            row = conn.execute("SELECT * FROM otps WHERE email=?", (email,)).fetchone()
            if not row or row["expires_at"] <= timestamp or row["attempts"] >= 5:
                failure = "The code is invalid or expired. Request a new code."
            elif not hmac.compare_digest(row["digest"], digest(s.secret, "otp", email + ":" + body.code)):
                conn.execute("UPDATE otps SET attempts=attempts+1 WHERE email=?", (email,))
                failure = "The code is invalid or expired. Request a new code."
            else:
                conn.execute("DELETE FROM otps WHERE email=?", (email,))
                result = save_user_and_session(conn, email, row["name"], row["role"], s, timestamp, request.cookies.get(SESSION_COOKIE))
        if failure:
            raise HTTPException(400, failure)
        user, token = result
        session_cookie(response, token, s)
        return {"user": public_user(user)}

    @application.get("/api/auth/me")
    def me(user=Depends(current_user)):
        return {"user": public_user(user)}

    @application.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            s = request.app.state.settings
            with request.app.state.db.connection(write=True) as conn:
                conn.execute("DELETE FROM sessions WHERE digest=?", (digest(s.secret, "session", token),))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"message": "Signed out."}

    @application.get("/api/auth/google/start")
    def google_start(request: Request, role: Literal["submitter", "coder"] = Query("submitter")):
        s = request.app.state.settings
        if not s.google_ready:
            raise HTTPException(503, "Google sign-in is unavailable until OAuth is configured.")
        state, verifier, nonce = random_token(), random_token(), random_token()
        timestamp = now()
        ip = request.client.host if request.client else "unknown"
        with request.app.state.db.connection(write=True) as conn:
            rate_limit(conn, "google-ip", ip, 20, 3600, timestamp)
            record_rate(conn, "google-ip", ip, timestamp)
            conn.execute("DELETE FROM oauth_states WHERE expires_at<=?", (timestamp,))
            conn.execute("INSERT INTO oauth_states(digest,verifier,nonce,role,expires_at) VALUES (?,?,?,?,?)", (digest(s.secret, "oauth", state), verifier, nonce, role, timestamp + 600))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params = {"client_id": s.google_client_id, "redirect_uri": s.google_redirect_uri,
                  "response_type": "code", "scope": "openid email profile", "state": state,
                  "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"}
        response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), status_code=302)
        # Top-level Google callback needs Lax even if the session uses Strict.
        response.set_cookie(OAUTH_COOKIE, state, max_age=600, httponly=True, secure=s.cookie_secure, samesite="lax", path="/api/auth/google")
        return response

    @application.get("/api/auth/google/callback")
    async def google_callback(request: Request, code: str | None = Query(None, max_length=4096),
                              state: str | None = Query(None, max_length=200), error: str | None = Query(None, max_length=200)):
        s = request.app.state.settings
        if not s.google_ready:
            raise HTTPException(503, "Google sign-in is not configured.")
        cookie = request.cookies.get(OAUTH_COOKIE, "")
        if not state or not cookie or not hmac.compare_digest(state, cookie):
            raise HTTPException(400, "Google sign-in state validation failed. Start sign-in again.")
        timestamp = now()
        with request.app.state.db.connection(write=True) as conn:
            row = conn.execute("SELECT * FROM oauth_states WHERE digest=? AND expires_at>?", (digest(s.secret, "oauth", state), timestamp)).fetchone()
            if not row:
                raise HTTPException(400, "Google sign-in expired or was already used. Start again.")
            oauth = dict(row)
            conn.execute("DELETE FROM oauth_states WHERE digest=?", (row["digest"],))
        if error or not code:
            raise HTTPException(400, "Google sign-in was cancelled or did not return a code.")
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                token_response = await client.post("https://oauth2.googleapis.com/token", data={
                    "client_id": s.google_client_id, "client_secret": s.google_client_secret,
                    "redirect_uri": s.google_redirect_uri, "grant_type": "authorization_code",
                    "code": code, "code_verifier": oauth["verifier"]})
                token_response.raise_for_status()
                tokens = token_response.json()
                header = jwt.get_unverified_header(tokens["id_token"])
                if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                    raise ValueError("Unsupported signing key")
                key_response = await client.get("https://www.googleapis.com/oauth2/v3/certs")
                key_response.raise_for_status()
                jwk = next(k for k in key_response.json()["keys"] if k.get("kid") == header["kid"] and k.get("kty") == "RSA")
                claims = jwt.decode(tokens["id_token"], jwt.PyJWK.from_dict(jwk).key, algorithms=["RS256"],
                                    audience=s.google_client_id, issuer=["https://accounts.google.com", "accounts.google.com"],
                                    options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]})
                if not hmac.compare_digest(str(claims["nonce"]), oauth["nonce"]):
                    raise ValueError("Invalid nonce")
                # Multi-audience tokens must explicitly identify this client.
                if (claims.get("azp") is not None and claims["azp"] != s.google_client_id) or (isinstance(claims.get("aud"), list) and len(claims["aud"]) > 1 and claims.get("azp") != s.google_client_id):
                    raise ValueError("Invalid authorized party")
                userinfo_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": "Bearer " + tokens["access_token"]})
                userinfo_response.raise_for_status()
                profile = userinfo_response.json()
                if profile.get("sub") != claims["sub"] or profile.get("email_verified") is not True or claims.get("email_verified") is not True:
                    raise ValueError("Unverified account")
                from pydantic import TypeAdapter
                email = str(TypeAdapter(EmailStr).validate_python(profile["email"])).lower()
                if str(claims.get("email", "")).lower() != email:
                    raise ValueError("Email mismatch")
                domain = email.rsplit("@", 1)[1]
                hosted_domain = str(claims.get("hd", "")).lower()
                # Google is authoritative for Gmail and verified Workspace mail.
                # A verified external email can outlive its mailbox ownership;
                # never use that claim to merge an account or bootstrap staff.
                if domain != "gmail.com" and not (hosted_domain and hosted_domain == domain and str(profile.get("hd", "")).lower() == hosted_domain):
                    raise HTTPException(400, "Google sign-in supports Gmail or verified Google Workspace. Use email OTP for this address.")
                name = str(profile.get("name") or email.split("@")[0])[:100]
        except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, StopIteration, TypeError):
            raise HTTPException(400, "Google identity verification failed. Start sign-in again.") from None
        with request.app.state.db.connection(write=True) as conn:
            user, token = save_user_and_session(conn, email, name, oauth["role"], s, now(), request.cookies.get(SESSION_COOKIE), google_sub=claims["sub"])
        response = RedirectResponse(s.frontend_url + "/#overview", status_code=302)
        session_cookie(response, token, s)
        response.delete_cookie(OAUTH_COOKIE, path="/api/auth/google")
        return response

    @application.get("/api/coder/applications/me")
    @application.get("/api/coder/applications")
    def my_application(request: Request, user=Depends(current_user)):
        require_role(user, "coder")
        with request.app.state.db.connection() as conn:
            row = conn.execute("SELECT a.*,u.email FROM applications a JOIN users u ON u.id=a.user_id WHERE a.user_id=?", (user["id"],)).fetchone()
        return {"application": public_application(row) if row else None}

    @application.post("/api/coder/applications")
    def submit_application(body: ApplicationInput, request: Request, user=Depends(current_user)):
        require_role(user, "coder")
        timestamp = now()
        with request.app.state.db.connection(write=True) as conn:
            rate_limit(conn, "application-user", user["id"], 20, 3600, timestamp)
            record_rate(conn, "application-user", user["id"], timestamp)
            data = (identifier(), user["id"], body.name, body.github, body.experience, body.specialty, body.portfolio, body.bio, timestamp, timestamp)
            conn.execute("INSERT INTO applications(id,user_id,name,github,experience,specialty,portfolio,bio,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,'pending',?,?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name,github=excluded.github,experience=excluded.experience,specialty=excluded.specialty,portfolio=excluded.portfolio,bio=excluded.bio,status='pending',notes='',decided_by=NULL,updated_at=excluded.updated_at", data)
            event(conn, user, "Coder application submitted for independent verification.")
            row = conn.execute("SELECT a.*,u.email FROM applications a JOIN users u ON u.id=a.user_id WHERE a.user_id=?", (user["id"],)).fetchone()
        return {"application": public_application(row)}

    @application.get("/api/staff/applications")
    def application_queue(request: Request, user=Depends(current_user)):
        require_role(user, "team")
        with request.app.state.db.connection() as conn:
            rows = conn.execute("SELECT a.*,u.email FROM applications a JOIN users u ON u.id=a.user_id ORDER BY a.updated_at DESC LIMIT 200").fetchall()
        return {"applications": [public_application(row) for row in rows]}

    @application.patch("/api/staff/applications/{aid}")
    def decide_application(aid: str, body: DecisionInput, request: Request, user=Depends(current_user)):
        require_role(user, "team")
        if body.decision != "approved" and not body.notes:
            raise HTTPException(422, "A decision note is required when requesting changes or declining.")
        with request.app.state.db.connection(write=True) as conn:
            row = conn.execute("SELECT * FROM applications WHERE id=?", (aid,)).fetchone()
            if not row:
                raise HTTPException(404, "Application not found.")
            if row["user_id"] == user["id"]:
                raise HTTPException(403, "You cannot verify your own application.")
            conn.execute("UPDATE applications SET status=?,notes=?,decided_by=?,updated_at=? WHERE id=?", (body.decision, body.notes, user["id"], now(), aid))
            event(conn, user, f"Coder application {aid} decision: {body.decision}.")
            updated = conn.execute("SELECT a.*,u.email FROM applications a JOIN users u ON u.id=a.user_id WHERE a.id=?", (aid,)).fetchone()
        return {"application": public_application(updated)}

    @application.get("/api/experts")
    def experts(request: Request, user=Depends(current_user)):
        with request.app.state.db.connection() as conn:
            rows = conn.execute("SELECT a.*,u.email FROM applications a JOIN users u ON u.id=a.user_id WHERE a.status='approved' AND u.role='coder' ORDER BY a.updated_at DESC LIMIT 200").fetchall()
        return {"experts": [{"id": r["user_id"], "name": r["name"], "title": r["specialty"], "skills": [r["specialty"]], "bio": r["bio"], "github": r["github"], "portfolio": r["portfolio"], "experience": r["experience"], "verified": True, "email": None, "rate": None, "initials": "".join(x[0] for x in r["name"].split()[:2])} for r in rows]}

    @application.post("/api/reviews", status_code=201)
    def create_review(body: ReviewInput, request: Request, user=Depends(current_user)):
        require_role(user, "submitter")
        rid, timestamp = identifier(), now()
        languages = body.verification_languages or (
            {VerificationLanguage.PYTHON} if "python" in body.stack.lower() else {VerificationLanguage.JAVASCRIPT}
        )
        capabilities = body.verification_capabilities or {
            VerificationCapability.SYNTAX,
            VerificationCapability.STATIC_ANALYSIS,
            VerificationCapability.AST_CFG,
            VerificationCapability.FORMAL_TYPE_SAFETY,
        }
        try:
            verification_request = SubmissionCreate(
                source=SourceSnapshot(repository_url=body.repo, commit_sha=body.sha),
                languages=languages,
                capabilities=capabilities,
                intended_behavior=body.scope,
                formal=body.formal,
            )
            plan = request.app.state.verification_planner.create_plan(verification_request)
            submission = request.app.state.verification_store.create(verification_request, plan)
            queued = request.app.state.verification_store.queue(submission.id)
            if queued is None:  # pragma: no cover - defensive store boundary.
                raise RuntimeError("verification submission could not be queued")
        except ValueError as error:
            raise HTTPException(422, f"Invalid verification request: {error}") from error
        expert_price = EXPERT_PRICING[body.expert_work.kind][body.expert_work.tier] if body.expert_work else 0
        expert_status = "requested" if body.expert_work else "not-requested"
        with request.app.state.db.connection(write=True) as conn:
            rate_limit(conn, "review-user", user["id"], 30, 3600, timestamp)
            record_rate(conn, "review-user", user["id"], timestamp)
            conn.execute("INSERT INTO reviews(id,owner_id,title,repo,sha,stack,scope,budget,deadline,visibility,category,verification_submission_id,expert_work_type,expert_work_tier,expert_work_price,expert_work_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, user["id"], body.title, body.repo, body.sha, body.stack, body.scope, body.budget, body.deadline.isoformat(), body.visibility, body.category, str(submission.id), body.expert_work.kind if body.expert_work else None, body.expert_work.tier if body.expert_work else None, expert_price, expert_status, timestamp))
            event(conn, user, "Review created and verification plan queued.", rid)
            row = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()
        return {"review": public_review(row), "verification": queued[0], "job": queued[1]}

    @application.get("/api/reviews/{rid}/verification")
    def review_verification(rid: str, request: Request, user=Depends(current_user)):
        with request.app.state.db.connection() as conn:
            review = review_for(conn, rid, user)
        submission_id = review["verification_submission_id"]
        if not submission_id:
            raise HTTPException(404, "No verification plan exists for this review.")
        try:
            submission = request.app.state.verification_store.get(uuid.UUID(submission_id))
        except ValueError as error:
            raise HTTPException(500, "Stored verification submission id is invalid.") from error
        if submission is None:
            raise HTTPException(404, "Verification plan is unavailable.")
        return {"submission": submission}

    @application.get("/api/reviews")
    def list_reviews(request: Request, category: TaskCategory | None = Query(None), user=Depends(current_user)):
        with request.app.state.db.connection() as conn:
            rows = conn.execute("SELECT r.* FROM reviews r JOIN users u ON u.id=? LEFT JOIN applications a ON a.user_id=u.id WHERE ((u.role='submitter' AND r.owner_id=u.id) OR (u.role='coder' AND a.status='approved' AND r.reviewer_id=u.id)) AND (? IS NULL OR r.category=?) ORDER BY r.created_at DESC LIMIT 200", (user["id"], category, category)).fetchall()
        return {"reviews": [public_review(row) for row in rows]}

    @application.get("/api/opportunities")
    def opportunities(request: Request, category: TaskCategory | None = Query(None), user=Depends(current_user)):
        require_role(user, "coder")
        with request.app.state.db.connection() as conn:
            approved = conn.execute("SELECT 1 FROM applications WHERE user_id=? AND status='approved'", (user["id"],)).fetchone()
            if not approved:
                raise HTTPException(403, "Your coder application must be approved before viewing opportunities.")
            rows = conn.execute("SELECT id,title,stack,budget,deadline,status,category,expert_work_type,expert_work_tier,expert_work_price FROM reviews WHERE reviewer_id IS NULL AND expert_work_type IS NOT NULL AND (? IS NULL OR category=?) ORDER BY created_at DESC LIMIT 200", (category, category)).fetchall()
        # Do not disclose private repo URLs or detailed briefs before assignment.
        return {"opportunities": [dict(row) for row in rows]}

    @application.get("/api/reviews/{rid}")
    def detail_review(rid: str, request: Request, user=Depends(current_user)):
        with request.app.state.db.connection() as conn:
            row = review_for(conn, rid, user)
            result = public_review(row)
            result["messages"] = [dict(x) for x in conn.execute("SELECT m.id,u.name AS 'from',m.text,m.created_at FROM messages m JOIN users u ON u.id=m.user_id WHERE m.review_id=? ORDER BY m.created_at,m.rowid LIMIT 200", (rid,)).fetchall()]
        return {"review": result}

    @application.post("/api/reviews/{rid}/assign")
    def assign_review(rid: str, body: AssignmentInput, request: Request, user=Depends(current_user)):
        require_role(user, "submitter")
        with request.app.state.db.connection(write=True) as conn:
            review = review_for(conn, rid, user, owner=True)
            if not review["expert_work_type"]:
                raise HTTPException(422, "Choose an expert deliverable before assigning a reviewer.")
            reviewer = conn.execute("SELECT u.id FROM users u JOIN applications a ON a.user_id=u.id WHERE u.id=? AND u.role='coder' AND a.status='approved'", (body.reviewer_id,)).fetchone()
            if not reviewer or reviewer["id"] == user["id"]:
                raise HTTPException(422, "Choose a verified coder other than yourself.")
            conn.execute("UPDATE reviews SET reviewer_id=?,reviewer_access='pending',expert_work_status='assigned' WHERE id=?", (reviewer["id"], rid))
            event(conn, user, "Verified coder selected for the requested expert deliverable. Repository access is pending.", rid)
            row = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()
        return {"review": public_review(row)}

    @application.post("/api/reviews/{rid}/expert-delivery")
    def submit_expert_delivery(rid: str, body: ExpertDeliveryInput, request: Request, user=Depends(current_user)):
        require_role(user, "coder")
        with request.app.state.db.connection(write=True) as conn:
            review = review_for(conn, rid, user)
            if not review["expert_work_type"]:
                raise HTTPException(409, "This review has no requested expert deliverable.")
            if review["expert_work_status"] not in {"assigned", "in-progress"}:
                raise HTTPException(409, "This expert deliverable is not ready for submission.")
            conn.execute("UPDATE reviews SET status='Expert delivery submitted',expert_work_status='completed',expert_delivery_summary=?,expert_delivery_url=? WHERE id=?", (body.summary, body.artifact_url, rid))
            event(conn, user, "Expert deliverable submitted for the requested review.", rid)
            row = conn.execute("SELECT * FROM reviews WHERE id=?", (rid,)).fetchone()
        return {"review": public_review(row)}

    @application.post("/api/reviews/{rid}/access-request")
    def access_request(rid: str, body: AccessInput, request: Request, user=Depends(current_user)):
        require_role(user, "submitter")
        with request.app.state.db.connection(write=True) as conn:
            row = review_for(conn, rid, user, owner=True)
            recipient = "antislop@bee3.in"
            if body.target == "reviewer":
                if not row["reviewer_id"]:
                    raise HTTPException(409, "Choose a verified coder first.")
                reviewer = conn.execute("SELECT u.email FROM users u JOIN applications a ON a.user_id=u.id WHERE u.id=? AND u.role='coder' AND a.status='approved'", (row["reviewer_id"],)).fetchone()
                if not reviewer:
                    raise HTTPException(409, "The selected coder's verification is no longer approved. Select a verified coder first.")
                recipient = reviewer["email"]
            event(conn, user, f"{body.target.title()} access handoff requested; permissions remain unverified.", rid)
        return {"status": "pending", "target": body.target, "recipient": recipient,
                "message": "Access handoff recorded. GitHub permissions have not been granted or verified; no email was sent."}

    @application.post("/api/reviews/{rid}/github/grant")
    @application.post("/api/reviews/{rid}/scan")
    def unavailable_integration(rid: str, request: Request, user=Depends(current_user)):
        require_role(user, "submitter")
        with request.app.state.db.connection() as conn:
            review_for(conn, rid, user, owner=True)
        raise HTTPException(503, "GitHub App and isolated review runner are not configured. No permissions changed and no scan started.")

    @application.get("/api/reviews/{rid}/messages")
    def list_messages(rid: str, request: Request, user=Depends(current_user)):
        with request.app.state.db.connection() as conn:
            review_for(conn, rid, user)
            rows = conn.execute("SELECT m.id,u.name AS 'from',m.text,m.created_at FROM messages m JOIN users u ON u.id=m.user_id WHERE m.review_id=? ORDER BY m.created_at,m.rowid LIMIT 200", (rid,)).fetchall()
        return {"messages": [dict(row) for row in rows]}

    @application.post("/api/reviews/{rid}/messages", status_code=201)
    def send_message(rid: str, body: MessageInput, request: Request, user=Depends(current_user)):
        timestamp, mid = now(), identifier()
        with request.app.state.db.connection(write=True) as conn:
            review_for(conn, rid, user)
            rate_limit(conn, "message-user", user["id"], 60, 60, timestamp)
            record_rate(conn, "message-user", user["id"], timestamp)
            conn.execute("INSERT INTO messages(id,review_id,user_id,text,created_at) VALUES (?,?,?,?,?)", (mid, rid, user["id"], body.text, timestamp))
            event(conn, user, "Review message sent.", rid)
        return {"message": {"id": mid, "from": user["name"], "text": body.text, "created_at": timestamp}}

    @application.get("/api/events")
    def events(request: Request, user=Depends(current_user)):
        with request.app.state.db.connection() as conn:
            rows = conn.execute("SELECT e.id,e.text,e.created_at FROM events e JOIN users u ON u.id=? LEFT JOIN applications a ON a.user_id=u.id LEFT JOIN reviews r ON r.id=e.review_id WHERE (e.review_id IS NULL AND e.actor_id=u.id) OR (u.role='submitter' AND r.owner_id=u.id) OR (u.role='coder' AND a.status='approved' AND r.reviewer_id=u.id) ORDER BY e.created_at DESC,e.rowid DESC LIMIT 100", (user["id"],)).fetchall()
        return {"events": [dict(row) for row in rows]}

    return application


app = create_app()
