"""Server-only email delivery and short-lived authentication primitives."""
from email.message import EmailMessage
import hashlib
import hmac
import secrets
import smtplib
import ssl

from .settings import Settings

SESSION_COOKIE = "antislop_session"
OAUTH_COOKIE = "antislop_oauth_state"
SESSION_SECONDS = 7 * 24 * 60 * 60
OTP_SECONDS = 10 * 60


def digest(secret: str, namespace: str, value: str) -> str:
    return hmac.new(secret.encode(), f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()


def random_token() -> str:
    return secrets.token_urlsafe(32)


class SMTPMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_otp(self, recipient: str, code: str):
        s = self.settings
        message = EmailMessage()
        message["Subject"] = "Your Antislop sign-in code"
        message["From"] = s.smtp_from
        message["To"] = recipient
        message.set_content(f"Your Antislop sign-in code is {code}.\n\nIt expires in 10 minutes. If you did not request this, ignore this email.\nAntislop will never ask you to share this code with a reviewer.")
        client_class = smtplib.SMTP_SSL if s.smtp_ssl else smtplib.SMTP
        kwargs = {"host": s.smtp_host, "port": s.smtp_port, "timeout": 15}
        if s.smtp_ssl:
            kwargs["context"] = ssl.create_default_context()
        with client_class(**kwargs) as client:
            if s.smtp_tls:
                client.starttls(context=ssl.create_default_context())
            if s.smtp_username:
                client.login(s.smtp_username, s.smtp_password)
            client.send_message(message)
