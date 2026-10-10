"""Behavioral security tests; SMTP and Google are mocked, never live."""
from dataclasses import replace
from urllib.parse import parse_qs, urlparse
import json
import sqlite3
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend import main
from backend.categories import TASK_CATEGORIES
from backend.db import Database, SCHEMA
from backend.security import OTP_SECONDS, SESSION_COOKIE
from backend.settings import Settings

ORIGIN = "http://localhost:4173"
HEADERS = {"Origin": ORIGIN}


class CaptureMailer:
    def __init__(self):
        self.codes = {}
        self.fail = False

    def send_otp(self, recipient, code):
        if self.fail:
            raise RuntimeError("Simulated delivery failure")
        self.codes[recipient] = code


@pytest.fixture
def service(tmp_path):
    settings = Settings(secret="test-only-" + "x" * 48, database_path=str(tmp_path / "test.sqlite3"),
                        smtp_host="mock.invalid", smtp_from="signin@example.com",
                        staff_emails=frozenset({"staff@example.com"}))
    mailer = CaptureMailer()
    app = main.create_app(settings, mailer=mailer)
    with TestClient(app, headers=HEADERS) as client:
        yield app, client, mailer, settings


def login(client, mailer, email="submitter@example.com", role="submitter"):
    result = client.post("/api/auth/otp/request", json={"email": email, "name": email.split("@")[0], "role": role})
    assert result.status_code == 200, result.text
    response = client.post("/api/auth/otp/verify", json={"email": email, "code": mailer.codes[email]})
    assert response.status_code == 200, response.text
    return response.json()["user"]


def review_payload():
    return {"title": "Tenant boundary review", "repo": "https://github.com/example/private-app", "sha": "ab123cd",
            "stack": "TypeScript", "scope": "Verify tenant boundaries in all resource handlers.", "budget": 500,
            "deadline": "2026-12-01", "visibility": "private"}


def application_payload():
    return {"name": "Coder", "github": "https://github.com/coder", "experience": "3–5 years",
            "specialty": "Application security", "portfolio": "https://example.com/work",
            "bio": "I review authorization boundaries and provide regression tests.", "consent": True}


def test_config_and_unconfigured_integrations_are_explicit(service):
    app, client, mailer, settings = service
    config = client.get("/api/config").json()
    assert config["backend"] == "fastapi"
    assert config["github"]["configured"] is False
    assert "secret" not in json.dumps(config).lower()
    assert client.get("/api/auth/google/start").status_code == 503
    login(client, mailer)
    rid = client.post("/api/reviews", json=review_payload()).json()["review"]["id"]
    assert client.post(f"/api/reviews/{rid}/scan").status_code == 503
    assert client.post(f"/api/reviews/{rid}/github/grant").status_code == 503
    assert client.get(f"/api/reviews/{rid}").json()["review"]["access"] == "pending"


def test_otp_delivery_session_storage_and_replay(service):
    app, client, mailer, _ = service
    user = login(client, mailer)
    assert user["role"] == "submitter"
    assert client.get("/api/auth/me").json()["user"]["id"] == user["id"]
    token = client.cookies.get(SESSION_COOKIE)
    with app.state.db.connection() as conn:
        row = conn.execute("SELECT * FROM sessions").fetchone()
        assert row["digest"] != token
        assert conn.execute("SELECT COUNT(*) FROM otps").fetchone()[0] == 0
    replay = client.post("/api/auth/otp/verify", json={"email": user["email"], "code": mailer.codes[user["email"]]})
    assert replay.status_code == 400
    # Consumption cannot bypass the resend cooldown.
    assert client.post("/api/auth/otp/request", json={"email": user["email"], "name": "Again", "role": "coder"}).status_code == 429
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_otp_is_hmac_hashed_and_max_attempts_persist(service):
    app, client, mailer, settings = service
    email = "coder@example.com"
    assert client.post("/api/auth/otp/request", json={"email": email, "name": "Coder", "role": "coder"}).status_code == 200
    with app.state.db.connection() as conn:
        row = conn.execute("SELECT * FROM otps WHERE email=?", (email,)).fetchone()
        assert row["digest"] != mailer.codes[email]
        assert len(row["digest"]) == 64
    wrong = "000000" if mailer.codes[email] != "000000" else "111111"
    for _ in range(5):
        assert client.post("/api/auth/otp/verify", json={"email": email, "code": wrong}).status_code == 400
    # A new process / client still sees the exhausted OTP.
    with TestClient(main.create_app(settings, mailer=mailer), headers=HEADERS) as other:
        assert other.post("/api/auth/otp/verify", json={"email": email, "code": mailer.codes[email]}).status_code == 400
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT attempts FROM otps WHERE email=?", (email,)).fetchone()[0] == 5


def test_expired_otp_and_session_rejected(service, monkeypatch):
    app, client, mailer, _ = service
    email = "expires@example.com"
    timestamp = main.now()
    monkeypatch.setattr(main, "now", lambda: timestamp)
    assert client.post("/api/auth/otp/request", json={"email": email, "name": "Expires", "role": "submitter"}).status_code == 200
    monkeypatch.setattr(main, "now", lambda: timestamp + OTP_SECONDS)
    assert client.post("/api/auth/otp/verify", json={"email": email, "code": mailer.codes[email]}).status_code == 400
    monkeypatch.setattr(main, "now", lambda: timestamp)
    login(client, mailer, "session@example.com")
    with app.state.db.connection(write=True) as conn:
        conn.execute("UPDATE sessions SET expires_at=?", (timestamp - 1,))
    assert client.get("/api/auth/me").status_code == 401


def test_smtp_missing_or_failure_never_claims_sent(service):
    app, client, mailer, settings = service
    mailer.fail = True
    response = client.post("/api/auth/otp/request", json={"email": "fail@example.com", "name": "Fails", "role": "coder"})
    assert response.status_code == 503
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM otps").fetchone()[0] == 0
    with TestClient(main.create_app(replace(settings, smtp_host=""), mailer=mailer), headers=HEADERS) as unconfigured:
        assert unconfigured.get("/api/config").json()["auth"]["email_otp"] is False
        assert unconfigured.post("/api/auth/otp/request", json={"email": "none@example.com", "name": "None", "role": "coder"}).status_code == 503


def test_ip_and_email_rate_limits_persist(service, monkeypatch):
    app, client, _, settings = service
    timestamp = main.now()
    for i in range(5):
        monkeypatch.setattr(main, "now", lambda i=i: timestamp + i * 61)
        assert client.post("/api/auth/otp/request", json={"email": "limited@example.com", "name": "Limited", "role": "submitter"}).status_code == 200
    monkeypatch.setattr(main, "now", lambda: timestamp + 5 * 61)
    with TestClient(main.create_app(settings), headers=HEADERS) as other:
        assert other.post("/api/auth/otp/request", json={"email": "limited@example.com", "name": "Limited", "role": "submitter"}).status_code == 429


def test_staff_role_cannot_be_self_assigned(service, monkeypatch):
    app, client, mailer, _ = service
    assert client.post("/api/auth/otp/request", json={"email": "evil@example.com", "name": "Evil", "role": "team"}).status_code == 422
    first = login(client, mailer, "member@example.com", "coder")
    assert client.get("/api/staff/applications").status_code == 403
    timestamp = main.now()
    monkeypatch.setattr(main, "now", lambda: timestamp + 61)
    second = login(client, mailer, "member@example.com", "submitter")
    assert second["id"] == first["id"] and second["role"] == "coder"
    staff = login(client, mailer, "staff@example.com", "submitter")
    assert staff["role"] == "team"
    assert client.get("/api/staff/applications").status_code == 200


def test_origin_validation_and_cookie_flags(service):
    app, client, mailer, _ = service
    payload = {"email": "origin@example.com", "name": "Origin", "role": "submitter"}
    assert client.post("/api/auth/otp/request", json=payload, headers={"Origin": "https://evil.example"}).status_code == 403
    # Explicitly remove the default Origin header for a separate client.
    with TestClient(app) as missing:
        assert missing.post("/api/auth/otp/request", json=payload).status_code == 403
    assert client.post("/api/auth/otp/request", json=payload).status_code == 200
    response = client.post("/api/auth/otp/verify", json={"email": payload["email"], "code": mailer.codes[payload["email"]]})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=604800" in cookie
    assert response.headers["cache-control"] == "no-store"


def test_independent_verification_changes_resubmit_and_assignment(service):
    app, client, mailer, _ = service
    coder = login(client, mailer, "coder@example.com", "coder")
    application = client.post("/api/coder/applications", json=application_payload()).json()["application"]
    assert application["status"] == "pending"
    aid = application["id"]
    assert client.patch(f"/api/staff/applications/{aid}", json={"decision": "approved"}).status_code == 403
    assert client.get("/api/opportunities").status_code == 403
    client.post("/api/auth/logout")
    owner = login(client, mailer, "owner@example.com")
    rid = client.post("/api/reviews", json=review_payload()).json()["review"]["id"]
    assert client.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coder["id"]}).status_code == 422
    client.post("/api/auth/logout")
    login(client, mailer, "staff@example.com")
    assert client.patch(f"/api/staff/applications/{aid}", json={"decision": "changes_requested"}).status_code == 422
    changed = client.patch(f"/api/staff/applications/{aid}", json={"decision": "changes_requested", "notes": "Add a relevant work sample"})
    assert changed.json()["application"]["status"] == "changes_requested"
    # Resume the coder using its existing server session, not another OTP.
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT status FROM applications WHERE id=?", (aid,)).fetchone()[0] == "changes_requested"
    client.patch(f"/api/staff/applications/{aid}", json={"decision": "approved", "notes": "Evidence verified"})
    experts = client.get("/api/experts").json()["experts"]
    assert experts[0]["id"] == coder["id"] and experts[0]["email"] is None
    # Restore owner session from its saved cookie in a new request context.
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT owner_id FROM reviews WHERE id=?", (rid,)).fetchone()[0] == owner["id"]


def test_review_private_access_assignment_messages_and_unconfigured_grants(service):
    app, client, mailer, settings = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as outsider, TestClient(app, headers=HEADERS) as coder, TestClient(app, headers=HEADERS) as staff:
        login(owner, mailer, "owner@example.com")
        outsider_user = login(outsider, mailer, "outsider@example.com")
        coder_user = login(coder, mailer, "reviewer@example.com", "coder")
        aid = coder.post("/api/coder/applications", json=application_payload()).json()["application"]["id"]
        login(staff, mailer, "staff@example.com")
        staff.patch(f"/api/staff/applications/{aid}", json={"decision": "approved", "notes": "Reviewed"})
        rid = owner.post("/api/reviews", json=review_payload()).json()["review"]["id"]
        for endpoint in (f"/api/reviews/{rid}", f"/api/reviews/{rid}/messages"):
            assert outsider.get(endpoint).status_code == 404
            assert coder.get(endpoint).status_code == 404
        assert outsider.get("/api/reviews").json()["reviews"] == []
        assert outsider.post(f"/api/reviews/{rid}/messages", json={"text": "Unauthorized"}).status_code == 404
        opportunity = coder.get("/api/opportunities").json()["opportunities"][0]
        assert opportunity["id"] == rid and "repo" not in opportunity and "scope" not in opportunity
        assigned = owner.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coder_user["id"]})
        assert assigned.json()["review"]["expertId"] == coder_user["id"]
        assert coder.get(f"/api/reviews/{rid}").status_code == 200
        assert coder.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": outsider_user["id"]}).status_code == 403
        access = owner.post(f"/api/reviews/{rid}/access-request", json={"target": "reviewer"}).json()
        assert access["recipient"] == coder_user["email"] and access["status"] == "pending"
        assert owner.post(f"/api/reviews/{rid}/access-request", json={"target": "platform"}).json()["recipient"] == "antislop@bee3.in"
        assert owner.post(f"/api/reviews/{rid}/access-confirm", json={}).status_code == 404
        assert coder.post(f"/api/reviews/{rid}/messages", json={"text": "Please grant repository access."}).status_code == 201
        assert owner.get(f"/api/reviews/{rid}/messages").json()["messages"][0]["text"] == "Please grant repository access."
        assert owner.post(f"/api/reviews/{rid}/scan").status_code == 503
        assert owner.get(f"/api/reviews/{rid}").json()["review"]["expertAccess"] == "pending"


@pytest.mark.parametrize("change", [{"repo": "https://evil.example/repo"}, {"repo": "https://github.com/a/b?token=secret"}, {"repo": "https://github.com/a/.."}, {"sha": "PR #42"}, {"budget": "500"}, {"owner_id": "someone-else"}])
def test_review_rejects_invalid_or_privilege_fields(service, change):
    _, client, mailer, _ = service
    login(client, mailer)
    payload = {**review_payload(), **change}
    assert client.post("/api/reviews", json=payload).status_code == 422


def test_application_email_and_status_are_server_owned(service):
    _, client, mailer, _ = service
    login(client, mailer, "coder@example.com", "coder")
    assert client.post("/api/coder/applications", json={**application_payload(), "email": "staff@example.com"}).status_code == 422
    assert client.post("/api/coder/applications", json={**application_payload(), "status": "approved"}).status_code == 422


def test_staff_revocation_blocks_existing_sessions_and_new_login(service, monkeypatch):
    app, client, mailer, settings = service
    login(client, mailer, "staff@example.com")
    session = client.cookies.get(SESSION_COOKIE)
    revoked_settings = replace(settings, staff_emails=frozenset())
    with TestClient(main.create_app(revoked_settings, mailer=mailer), headers={**HEADERS, "Cookie": f"{SESSION_COOKIE}={session}"}) as revoked:
        assert revoked.get("/api/staff/applications").status_code == 403
        assert revoked.get("/api/auth/me").status_code == 403
        timestamp = main.now()
        monkeypatch.setattr(main, "now", lambda: timestamp + 61)
        assert revoked.post("/api/auth/otp/request", json={"email": "staff@example.com", "name": "Staff", "role": "submitter"}).status_code == 200
        assert revoked.post("/api/auth/otp/verify", json={"email": "staff@example.com", "code": mailer.codes["staff@example.com"]}).status_code == 403


def test_resubmission_resets_approval_and_keeps_application_id(service):
    app, client, mailer, _ = service
    with TestClient(app, headers=HEADERS) as coder, TestClient(app, headers=HEADERS) as staff:
        login(coder, mailer, "resubmitter@example.com", "coder")
        original = coder.post("/api/coder/applications", json=application_payload()).json()["application"]
        login(staff, mailer, "staff@example.com")
        assert staff.patch(f"/api/staff/applications/{original['id']}", json={"decision": "approved", "notes": "Approved"}).status_code == 200
        resubmitted = coder.post("/api/coder/applications", json={**application_payload(), "bio": "Updated evidence of reviewing security boundaries and integration tests."}).json()["application"]
        assert resubmitted["id"] == original["id"]
        assert resubmitted["status"] == "pending" and resubmitted["notes"] == ""
        assert coder.get("/api/opportunities").status_code == 403


def test_task_catalog_all_categories_create_and_filter(service):
    app, client, mailer, _ = service
    catalog = client.get("/api/config").json()["task_categories"]
    assert catalog == list(TASK_CATEGORIES)
    assert catalog == [
        {"id": "security", "label": "Security"},
        {"id": "frontend-ux", "label": "Frontend & UX"},
        {"id": "backend-api", "label": "Backend & APIs"},
        {"id": "performance", "label": "Performance"},
        {"id": "testing-qa", "label": "Testing & QA"},
        {"id": "devops-cloud", "label": "DevOps & Cloud"},
        {"id": "data-ai", "label": "Data & AI"},
        {"id": "architecture", "label": "Architecture & Refactoring"},
        {"id": "general", "label": "General review"},
    ]
    login(client, mailer)
    for item in catalog:
        created = client.post("/api/reviews", json={**review_payload(), "title": item["label"], "category": item["id"]})
        assert created.status_code == 201
        review = created.json()["review"]
        assert review["category"] == item["id"]
        assert client.get(f"/api/reviews/{review['id']}").json()["review"]["category"] == item["id"]
    assert len(client.get("/api/reviews").json()["reviews"]) == len(catalog)
    for item in catalog:
        filtered = client.get("/api/reviews", params={"category": item["id"]}).json()["reviews"]
        assert len(filtered) == 1 and filtered[0]["category"] == item["id"]


@pytest.mark.parametrize("category", ["unknown", "Security", "frontend", ["security", "testing-qa"], None])
def test_unknown_or_multiple_task_categories_rejected(service, category):
    _, client, mailer, _ = service
    login(client, mailer)
    assert client.post("/api/reviews", json={**review_payload(), "category": category}).status_code == 422
    assert client.get("/api/reviews?category=unknown").status_code == 422


def test_legacy_post_defaults_general_and_filtered_list_keeps_acl(service):
    app, client, mailer, _ = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as outsider:
        login(owner, mailer, "category-owner@example.com")
        legacy = owner.post("/api/reviews", json=review_payload()).json()["review"]
        assert legacy["category"] == "general"
        login(outsider, mailer, "category-outsider@example.com")
        outsider.post("/api/reviews", json={**review_payload(), "category": "security"})
        assert outsider.get("/api/reviews?category=general").json()["reviews"] == []
        own_security = outsider.get("/api/reviews?category=security").json()["reviews"]
        assert len(own_security) == 1 and own_security[0]["id"] != legacy["id"]


def test_opportunity_category_filter_keeps_private_fields_hidden(service):
    app, client, mailer, _ = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as coder, TestClient(app, headers=HEADERS) as staff:
        login(owner, mailer, "owner@example.com")
        for category in ("security", "testing-qa"):
            assert owner.post("/api/reviews", json={**review_payload(), "category": category}).status_code == 201
        login(coder, mailer, "coder@example.com", "coder")
        aid = coder.post("/api/coder/applications", json=application_payload()).json()["application"]["id"]
        login(staff, mailer, "staff@example.com")
        staff.patch(f"/api/staff/applications/{aid}", json={"decision": "approved", "notes": "Verified"})
        filtered = coder.get("/api/opportunities?category=security").json()["opportunities"]
        assert len(filtered) == 1 and filtered[0]["category"] == "security"
        assert "repo" not in filtered[0] and "scope" not in filtered[0]
        assert len(coder.get("/api/opportunities").json()["opportunities"]) == 2
        assert coder.get("/api/opportunities?category=unknown").status_code == 422


def test_legacy_database_category_migration_preserves_data_and_is_idempotent(tmp_path):
    path = str(tmp_path / "legacy.sqlite3")
    legacy_schema = SCHEMA.replace(" category TEXT NOT NULL DEFAULT 'general',\n", "")
    assert " category TEXT" not in legacy_schema
    with sqlite3.connect(path) as conn:
        conn.executescript(legacy_schema)
        conn.execute("INSERT INTO users(id,email,name,role,created_at) VALUES ('u1','legacy@example.com','Legacy','submitter',1)")
        conn.execute("INSERT INTO reviews(id,owner_id,title,repo,sha,stack,scope,budget,deadline,visibility,status,created_at) VALUES ('r1','u1','Legacy review','https://github.com/example/legacy','abcd123','Python','Existing scope must stay intact.',700,'2026-12-01','private','Expert review',2)")
        before = conn.execute("SELECT title,repo,scope,budget,status FROM reviews WHERE id='r1'").fetchone()
    db = Database(path)
    db.initialize()
    with db.connection(write=True) as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id='r1'").fetchone()
        assert row["category"] == "general"
        assert tuple(row[key] for key in ("title", "repo", "scope", "budget", "status")) == before
        conn.execute("UPDATE reviews SET category='architecture' WHERE id='r1'")
    db.initialize()
    with db.connection() as conn:
        assert conn.execute("SELECT category FROM reviews WHERE id='r1'").fetchone()[0] == "architecture"
        assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1


@pytest.mark.parametrize("change", [{"secret": "short"}, {"cors_origins": ("*",)}, {"cookie_samesite": "none", "cookie_secure": False}, {"environment": "production", "cookie_secure": False}, {"cors_origins": ("http://localhost:4173/path",)}])
def test_deployment_rejects_unsafe_auth_config(tmp_path, change):
    with pytest.raises(ValueError):
        main.create_app(replace(Settings(secret="x" * 48, database_path=str(tmp_path / "unused.db")), **change))


@pytest.fixture
def google_service(tmp_path, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "test-key"
    settings = Settings(secret="x" * 48, database_path=str(tmp_path / "google.sqlite3"),
                        google_client_id="client.example", google_client_secret="fake-client-secret")
    response_claims = {}
    observed = {}

    class FakeResponse:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, data):
            observed["exchange"] = data
            return FakeResponse({"id_token": jwt.encode(response_claims, private_key, algorithm="RS256", headers={"kid": "test-key"}), "access_token": "mock-access-token"})
        async def get(self, url, **kwargs):
            if url.endswith("/certs"):
                return FakeResponse({"keys": [jwk]})
            return FakeResponse({"sub": "google-user", "email": "google@gmail.com", "email_verified": True, "name": "Google member", **observed.get("profile", {})})

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)
    app = main.create_app(settings)
    with TestClient(app, headers=HEADERS) as client:
        yield app, client, settings, response_claims, observed


def begin_google(client, claims):
    response = client.get("/api/auth/google/start?role=coder", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    claims.update({"iss": "https://accounts.google.com", "aud": "client.example", "sub": "google-user",
                   "exp": int(time.time()) + 600, "iat": int(time.time()), "nonce": query["nonce"][0],
                   "email": "google@gmail.com", "email_verified": True})
    return query["state"][0], query


def test_google_oidc_code_state_pkce_nonce_and_session(google_service):
    app, client, _, claims, observed = google_service
    state, query = begin_google(client, claims)
    response = client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False)
    assert response.status_code == 302, response.text
    assert response.headers["location"] == ORIGIN + "/#overview"
    assert observed["exchange"]["code_verifier"]
    assert client.get("/api/auth/me").json()["user"]["role"] == "coder"
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 400


@pytest.mark.parametrize("change", [{"iss": "https://evil.example"}, {"aud": "wrong-client"}, {"nonce": "wrong-nonce"}, {"email_verified": False}, {"email": "other@example.com"}, {"exp": 1}])
def test_google_rejects_invalid_identity_claims(google_service, change):
    app, client, _, claims, _ = google_service
    state, _ = begin_google(client, claims)
    claims.update(change)
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 400
    assert client.get("/api/auth/me").status_code == 401
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_google_state_and_bootstrap_role_rejected(google_service):
    app, client, _, claims, _ = google_service
    assert client.get("/api/auth/google/start?role=team", follow_redirects=False).status_code == 422
    begin_google(client, claims)
    assert client.get("/api/auth/google/callback?state=attacker-state&code=valid-code", follow_redirects=False).status_code == 400


def test_google_external_verified_email_does_not_merge_or_bootstrap(google_service):
    app, client, _, claims, observed = google_service
    state, _ = begin_google(client, claims)
    claims["email"] = "staff@example.com"
    observed["profile"] = {"email": "staff@example.com"}
    # Even email_verified=true does not prove current external mailbox ownership.
    response = client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False)
    assert response.status_code == 400 and "email OTP" in response.json()["detail"]
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_google_stable_subject_prevents_another_identity_rebinding(google_service):
    app, client, _, claims, observed = google_service
    state, _ = begin_google(client, claims)
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 302
    client.post("/api/auth/logout")
    second, _ = begin_google(client, claims)
    claims["sub"] = "another-google-user"
    observed["profile"] = {"sub": "another-google-user"}
    assert client.get(f"/api/auth/google/callback?state={second}&code=valid-code", follow_redirects=False).status_code == 400
    assert client.get("/api/auth/me").status_code == 401


def test_google_workspace_requires_matching_hosted_domain(google_service):
    app, client, _, claims, observed = google_service
    state, _ = begin_google(client, claims)
    claims.update({"email": "member@company.example", "hd": "company.example"})
    observed["profile"] = {"email": "member@company.example", "hd": "company.example"}
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 302
    assert client.get("/api/auth/me").json()["user"]["email"] == "member@company.example"
