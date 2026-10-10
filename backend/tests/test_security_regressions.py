"""Independent security contract regression checks. No external services used."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.security import SESSION_COOKIE
from backend.tests.test_api import (HEADERS, application_payload, begin_google,
                                   google_service, login, review_payload, service)


def test_single_use_otp_is_atomic_under_racing_clients(service):
    app, client, mailer, settings = service
    email = "race@example.com"
    assert client.post("/api/auth/otp/request", json={"email": email, "name": "Race", "role": "coder"}).status_code == 200
    body = {"email": email, "code": mailer.codes[email]}

    def verify(_):
        with TestClient(app, headers=HEADERS) as racing:
            return racing.post("/api/auth/otp/verify", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(verify, range(2))) == [200, 400]
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_logout_invalidates_stolen_copy_and_login_rotates_current_session(service, monkeypatch):
    app, client, mailer, settings = service
    user = login(client, mailer, "rotate@example.com")
    first = client.cookies.get(SESSION_COOKIE)
    timestamp = main.now()
    monkeypatch.setattr(main, "now", lambda: timestamp + 61)
    assert login(client, mailer, "rotate@example.com")["id"] == user["id"]
    second = client.cookies.get(SESSION_COOKIE)
    assert first != second
    with TestClient(app, headers=HEADERS) as replay:
        replay.cookies.set(SESSION_COOKIE, first)
        assert replay.get("/api/auth/me").status_code == 401
        replay.cookies.set(SESSION_COOKIE, second)
        assert replay.get("/api/auth/me").status_code == 200
        assert client.post("/api/auth/logout").status_code == 200
        assert replay.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("origin", ["null", "https://evil.example", "http://localhost:4173.evil.example", "http://localhost:4173/path"])
def test_csrf_origin_confusion_rejected(service, origin):
    app, client, mailer, settings = service
    login(client, mailer)
    assert client.post("/api/reviews", json=review_payload(), headers={"Origin": origin}).status_code == 403
    assert client.post("/api/auth/logout", headers={"Origin": origin}).status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_staff_and_outsider_cannot_inspect_or_mutate_private_review(service):
    app, client, mailer, settings = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as staff:
        login(owner, mailer, "owner@example.com")
        login(staff, mailer, "staff@example.com")
        rid = owner.post("/api/reviews", json=review_payload()).json()["review"]["id"]
        assert staff.get(f"/api/reviews/{rid}").status_code == 404
        assert staff.get(f"/api/reviews/{rid}/messages").status_code == 404
        assert staff.get("/api/reviews").json()["reviews"] == []
        assert staff.post(f"/api/reviews/{rid}/access-request", json={"target": "platform"}).status_code == 403
        assert staff.post(f"/api/reviews/{rid}/messages", json={"text": "Unauthorized"}).status_code == 404
        assert staff.post(f"/api/reviews/{rid}/scan").status_code == 403


def test_revoked_staff_allowlist_cannot_reuse_old_staff_session(service):
    app, client, mailer, settings = service
    login(client, mailer, "staff@example.com")
    token = client.cookies.get(SESSION_COOKIE)
    restricted = replace(settings, staff_emails=frozenset())
    with TestClient(main.create_app(restricted, mailer=mailer), headers=HEADERS) as revoked:
        revoked.cookies.set(SESSION_COOKIE, token)
        assert revoked.get("/api/staff/applications").status_code in {401, 403}


def test_reassignment_removes_prior_reviewers_private_access(service):
    app, client, mailer, settings = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as staff, TestClient(app, headers=HEADERS) as first, TestClient(app, headers=HEADERS) as second:
        login(owner, mailer, "owner@example.com")
        login(staff, mailer, "staff@example.com")
        coders = []
        for actor, email in [(first, "first@example.com"), (second, "second@example.com")]:
            user = login(actor, mailer, email, "coder")
            aid = actor.post("/api/coder/applications", json=application_payload()).json()["application"]["id"]
            assert staff.patch(f"/api/staff/applications/{aid}", json={"decision": "approved"}).status_code == 200
            coders.append(user)
        rid = owner.post("/api/reviews", json=review_payload()).json()["review"]["id"]
        assert owner.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coders[0]["id"]}).status_code == 200
        assert first.post(f"/api/reviews/{rid}/messages", json={"text": "Initial review conversation"}).status_code == 201
        assert owner.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coders[1]["id"]}).status_code == 200
        assert first.get(f"/api/reviews/{rid}").status_code == 404
        assert first.get(f"/api/reviews/{rid}/messages").status_code == 404
        assert first.post(f"/api/reviews/{rid}/messages", json={"text": "Stale assignment"}).status_code == 404
        assert first.get("/api/reviews").json()["reviews"] == []
        assert second.get(f"/api/reviews/{rid}").status_code == 200


def test_resubmitted_approved_application_requires_fresh_team_decision(service):
    app, client, mailer, settings = service
    with TestClient(app, headers=HEADERS) as coder, TestClient(app, headers=HEADERS) as staff:
        user = login(coder, mailer, "coder@example.com", "coder")
        login(staff, mailer, "staff@example.com")
        aid = coder.post("/api/coder/applications", json=application_payload()).json()["application"]["id"]
        staff.patch(f"/api/staff/applications/{aid}", json={"decision": "approved"})
        assert coder.get("/api/opportunities").status_code == 200
        assert len(coder.get("/api/experts").json()["experts"]) == 1
        resubmit = coder.post("/api/coder/applications", json={**application_payload(), "bio": "Updated experience that needs independent review again."}).json()["application"]
        assert resubmit["id"] == aid and resubmit["status"] == "pending"
        assert coder.get("/api/opportunities").status_code == 403
        assert coder.get("/api/experts").json()["experts"] == []


def test_google_multiple_audiences_without_matching_azp_rejected(google_service):
    app, client, settings, claims, observed = google_service
    state, query = begin_google(client, claims)
    claims["aud"] = [settings.google_client_id, "other-client"]
    claims["azp"] = "other-client"
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 400
    assert client.get("/api/auth/me").status_code == 401


def test_google_expired_state_rejected_before_token_exchange(google_service, monkeypatch):
    app, client, settings, claims, observed = google_service
    timestamp = main.now()
    state, query = begin_google(client, claims)
    monkeypatch.setattr(main, "now", lambda: timestamp + 601)
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 400
    assert "exchange" not in observed


def test_google_missing_nonce_is_rejected(google_service):
    app, client, settings, claims, observed = google_service
    state, query = begin_google(client, claims)
    del claims["nonce"]
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid-code", follow_redirects=False).status_code == 400
    assert client.get("/api/auth/me").status_code == 401


def test_cookie_flags_are_secure_in_production(service):
    app, client, mailer, settings = service
    production = replace(settings, environment="production", cookie_secure=True, frontend_url="https://antislop.bee3.in", cors_origins=("https://antislop.bee3.in",), google_redirect_uri="https://api.bee3.in/api/auth/google/callback")
    with TestClient(main.create_app(production, mailer=mailer), base_url="https://api.bee3.in", headers={"Origin": "https://antislop.bee3.in"}) as secure:
        assert secure.post("/api/auth/otp/request", json={"email": "secure@example.com", "name": "Secure", "role": "submitter"}).status_code == 200
        response = secure.post("/api/auth/otp/verify", json={"email": "secure@example.com", "code": mailer.codes["secure@example.com"]})
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
        assert "domain=" not in cookie


def test_verification_ip_throttle_and_malformed_session_fail_closed(service):
    app, client, mailer, settings = service
    for _ in range(30):
        assert client.post("/api/auth/otp/verify", json={"email": "none@example.com", "code": "123456"}).status_code == 400
    assert client.post("/api/auth/otp/verify", json={"email": "none@example.com", "code": "123456"}).status_code == 429
    client.cookies.set(SESSION_COOKIE, "x" * 201)
    assert client.get("/api/auth/me").status_code == 401
