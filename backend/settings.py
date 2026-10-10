"""Explicit deployment configuration. No shared development auth secrets."""
from dataclasses import dataclass
from urllib.parse import urlparse
import os

from dotenv import load_dotenv


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


@dataclass(frozen=True)
class Settings:
    secret: str
    database_path: str = "backend/data/antislop.sqlite3"
    environment: str = "development"
    frontend_url: str = "http://localhost:4173"
    cors_origins: tuple[str, ...] = ("http://localhost:4173",)
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    staff_emails: frozenset[str] = frozenset()
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    smtp_ssl: bool = False
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    @property
    def smtp_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def google_ready(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    def validate(self) -> "Settings":
        if len(self.secret) < 32:
            raise ValueError("SECRET_KEY must be configured with at least 32 random characters.")
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be lax, strict, or none.")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("SameSite=None requires COOKIE_SECURE=true.")
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must contain explicit trusted frontend origins.")
        for origin in self.cors_origins:
            u = urlparse(origin)
            if u.path not in {"", "/"} or u.query or u.fragment:
                raise ValueError("CORS_ORIGINS must be origins without paths, queries, or fragments.")
        for value in (self.frontend_url, *self.cors_origins, self.google_redirect_uri):
            u = urlparse(value)
            if u.scheme not in {"http", "https"} or not u.netloc or u.username or u.password:
                raise ValueError("Frontend, CORS, and callback URLs must be valid HTTP(S) URLs.")
            if self.environment == "production" and u.scheme != "https":
                raise ValueError("Production URLs must use HTTPS.")
        if urlparse(self.frontend_url).query or urlparse(self.frontend_url).fragment:
            raise ValueError("FRONTEND_URL cannot include query parameters or a fragment.")
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("Production sessions require COOKIE_SECURE=true.")
        if self.smtp_ssl and self.smtp_tls:
            raise ValueError("Choose SMTP_SSL or SMTP_TLS, not both.")
        if self.environment == "production" and self.smtp_ready and not (self.smtp_tls or self.smtp_ssl):
            raise ValueError("Production SMTP requires encrypted transport.")
        return self

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            secret=os.getenv("SECRET_KEY", ""),
            database_path=os.getenv("DATABASE_PATH", "backend/data/antislop.sqlite3"),
            environment=os.getenv("APP_ENV", "development"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:4173").rstrip("/"),
            cors_origins=tuple(x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://localhost:4173").split(",") if x.strip()),
            cookie_secure=env_bool("COOKIE_SECURE"), cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax").lower(),
            staff_emails=frozenset(x.strip().lower() for x in os.getenv("STAFF_EMAILS", "").split(",") if x.strip()),
            smtp_host=os.getenv("SMTP_HOST", ""), smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""), smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", ""), smtp_tls=env_bool("SMTP_TLS", True), smtp_ssl=env_bool("SMTP_SSL"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""), google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"),
        ).validate()
