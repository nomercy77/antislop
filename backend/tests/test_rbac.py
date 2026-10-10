"""Role, resource boundary, and verification checks using mocked services."""
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.security import SESSION_COOKIE
from backend.tests.test_api import (HEADERS, application_payload, begin_google,
                                   google_service, login, review_payload, service)


@pytest.mark.parametrize("role", ["submitter", "coder"])
def test_verified_email_login_cannot_change_existing_account_role(service, monkeypatch, role):
    app, client, mailer, settings = service
    user = login(client, mailer, "fixed-role@example.com", role)
    timestamp = main.now()
    monkeypatch.setattr(main, "now", lambda: timestamp + 61)
    requested = "coder" if role == "submitter" else "submitter"
    again = login(client, mailer, "fixed-role@example.com", requested)
    assert again["id"] == user["id"] and again["role"] == role


def test_staff_signup_and_role_privilege_fields_cannot_be_self_selected(service):
    app, client, mailer, settings = service
    for payload in [
        {"email": "attacker@example.com", "name": "Attacker", "role": "team"},
        {"email": "attacker@example.com", "name": "Attacker", "role": "coder", "permissions": ["staff.review"]},
    ]:
        assert client.post("/api/auth/otp/request", json=payload).status_code == 422
    assert client.get("/api/auth/google/start?role=team", follow_redirects=False).status_code == 422
    assert client.get("/api/auth/me").status_code == 401


def test_google_signin_cannot_change_existing_account_role(google_service):
    app, client, settings, claims, observed = google_service
    state, query = begin_google(client, claims)
    assert client.get(f"/api/auth/google/callback?state={state}&code=valid", follow_redirects=False).status_code == 302
    before = client.get("/api/auth/me").json()["user"]
    start = client.get("/api/auth/google/start?role=submitter", follow_redirects=False)
    query = parse_qs(urlparse(start.headers["location"]).query)
    claims["nonce"] = query["nonce"][0]
    assert client.get(f"/api/auth/google/callback?state={query['state'][0]}&code=valid", follow_redirects=False).status_code == 302
    after = client.get("/api/auth/me").json()["user"]
    assert after["id"] == before["id"] and after["role"] == "coder"


@pytest.mark.parametrize("role,email", [("submitter", "submitter@example.com"), ("coder", "coder@example.com"), ("team", "staff@example.com")])
def test_mutation_role_matrix_and_private_data_boundary(service, role, email):
    app, client, mailer, settings = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as actor:
        owner_user = login(owner, mailer, "private-owner@example.com")
        rid = owner.post("/api/reviews", json=review_payload()).json()["review"]["id"]
        actor_user = login(actor, mailer, email, "coder" if role == "coder" else "submitter")
        assert actor_user["role"] == role
        permission = {"submitter": "create_review", "coder": "apply_verification", "team": "decide_verification"}
        capabilities = actor.get("/api/auth/me").json()["user"]["permissions"]
        assert permission[role] in capabilities
        assert all(value not in capabilities for name, value in permission.items() if name != role)
        assert actor.post("/api/reviews", json=review_payload()).status_code == (201 if role == "submitter" else 403)
        assert actor.post("/api/coder/applications", json=application_payload()).status_code == (200 if role == "coder" else 403)
        assert actor.get("/api/staff/applications").status_code == (200 if role == "team" else 403)
        assert actor.get(f"/api/reviews/{rid}").status_code == 404
        assert actor.get(f"/api/reviews/{rid}/messages").status_code == 404
        assert actor.post(f"/api/reviews/{rid}/messages", json={"text": "Unauthorized"}).status_code in {403, 404}
        expected = 404 if role == "submitter" else 403
        for path, body in [
            ("assign", {"reviewer_id": owner_user["id"]}),
            ("access-request", {"target": "platform"}),
            ("scan", {}),
            ("github/grant", {}),
        ]:
            assert actor.post(f"/api/reviews/{rid}/{path}", json=body).status_code == expected, path
        assert all(x["id"] != rid for x in actor.get("/api/reviews").json()["reviews"])


@pytest.mark.parametrize("status", ["changes_requested", "rejected", "pending"])
def test_revoked_or_resubmitted_coder_loses_assigned_private_access(service, status):
    app, client, mailer, settings = service
    with TestClient(app, headers=HEADERS) as owner, TestClient(app, headers=HEADERS) as coder, TestClient(app, headers=HEADERS) as staff:
        login(owner, mailer, "owner@example.com")
        coder_user = login(coder, mailer, "coder@example.com", "coder")
        aid = coder.post("/api/coder/applications", json=application_payload()).json()["application"]["id"]
        login(staff, mailer, "staff@example.com")
        assert staff.patch(f"/api/staff/applications/{aid}", json={"decision": "approved"}).status_code == 200
        verified_user = coder.get("/api/auth/me").json()["user"]
        assert verified_user["verification_status"] == "approved"
        assert "read_assigned_reviews" in verified_user["permissions"]
        assert "send_review_messages" in verified_user["permissions"]
        rid = owner.post("/api/reviews", json=review_payload()).json()["review"]["id"]
        assert owner.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coder_user["id"]}).status_code == 200
        assert coder.get(f"/api/reviews/{rid}").status_code == 200
        assert coder.post(f"/api/reviews/{rid}/access-request", json={"target": "reviewer"}).status_code == 403
        assert coder.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coder_user["id"]}).status_code == 403
        assert coder.patch(f"/api/staff/applications/{aid}", json={"decision": "approved"}).status_code == 403
        assert coder.post(f"/api/reviews/{rid}/messages", json={"text": "Before revocation"}).status_code == 201
        with app.state.db.connection(write=True) as conn:
            conn.execute("INSERT INTO events(id,actor_id,review_id,text,created_at) VALUES (?,?,?,?,?)", ("private-owned-event", coder_user["id"], rid, "Private repository sensitive detail", main.now()))
        if status == "pending":
            assert coder.post("/api/coder/applications", json=application_payload()).status_code == 200
        else:
            assert staff.patch(f"/api/staff/applications/{aid}", json={"decision": status, "notes": "Additional verification required"}).status_code == 200
        revoked_user = coder.get("/api/auth/me").json()["user"]
        assert revoked_user["verification_status"] == status
        assert "apply_verification" in revoked_user["permissions"]
        assert "read_assigned_reviews" not in revoked_user["permissions"]
        assert "send_review_messages" not in revoked_user["permissions"]
        assert coder.get(f"/api/reviews/{rid}").status_code in {403, 404}
        assert coder.get(f"/api/reviews/{rid}/messages").status_code in {403, 404}
        assert coder.post(f"/api/reviews/{rid}/messages", json={"text": "Stale approval"}).status_code in {403, 404}
        assert coder.get("/api/reviews").json()["reviews"] == []
        assert coder.get("/api/reviews?category=general").json()["reviews"] == []
        assert coder.get("/api/opportunities").status_code == 403
        events = coder.get("/api/events").json()["events"]
        assert not any(x["id"] == "private-owned-event" or "Private repository sensitive detail" in x["text"] for x in events)
        assert owner.get(f"/api/reviews/{rid}").status_code == 200
        assert staff.get(f"/api/reviews/{rid}").status_code == 404
        assert owner.post(f"/api/reviews/{rid}/assign", json={"reviewer_id": coder_user["id"]}).status_code == 422
        assert owner.post(f"/api/reviews/{rid}/access-request", json={"target": "reviewer"}).status_code in {409, 422}


def test_staff_allowlist_revocation_applies_to_existing_cookie(service):
    app, client, mailer, settings = service
    login(client, mailer, "staff@example.com")
    token = client.cookies.get(SESSION_COOKIE)
    with TestClient(main.create_app(replace(settings, staff_emails=frozenset()), mailer=mailer), headers=HEADERS) as revoked:
        revoked.cookies.set(SESSION_COOKIE, token)
        assert revoked.get("/api/staff/applications").status_code in {401, 403}
        assert revoked.get("/api/auth/me").status_code in {401, 403}


def test_anonymous_valid_payloads_cannot_mutate_or_read_accounts(service):
    app, client, mailer, settings = service
    assert client.post("/api/reviews", json=review_payload()).status_code == 401
    assert client.post("/api/coder/applications", json=application_payload()).status_code == 401
    assert client.get("/api/reviews").status_code == 401
    assert client.get("/api/staff/applications").status_code == 401
    assert client.get("/api/events").status_code == 401
