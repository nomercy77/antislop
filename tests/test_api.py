from fastapi.testclient import TestClient

from antislop.main import create_app
from antislop.services.store import InMemorySubmissionStore


def submission_payload() -> dict[str, object]:
    return {
        "source": {
            "repository_url": "https://github.com/example/verified-service",
            "commit_sha": "a" * 40,
        },
        "languages": ["python"],
        "capabilities": ["syntax", "tests"],
        "test_commands": ["pytest"],
        "intended_behavior": "Validate invoice totals.",
    }


def test_submission_creates_a_deterministic_plugin_plan() -> None:
    client = TestClient(create_app(InMemorySubmissionStore()))

    response = client.post("/v1/submissions", json=submission_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "planned"
    assert [run["capability"] for run in body["plan"]["runs"]] == [
        "syntax",
        "tests",
    ]
    assert {run["plugin_id"] for run in body["plan"]["runs"]} == {"builtin.syntax", "builtin.tests"}
    assert all(run["status"] == "planned" for run in body["plan"]["runs"])


def test_queued_submission_does_not_execute_in_the_api_process() -> None:
    client = TestClient(create_app(InMemorySubmissionStore()))
    created = client.post("/v1/submissions", json=submission_payload()).json()

    response = client.post(f"/v1/submissions/{created['id']}/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["submission"]["status"] == "queued"
    assert body["job"]["status"] == "queued"
    assert all(run["status"] == "queued" for run in body["submission"]["plan"]["runs"])


def test_rejects_non_github_repository() -> None:
    client = TestClient(create_app(InMemorySubmissionStore()))
    payload = submission_payload()
    payload["source"]["repository_url"] = "https://example.com/owner/repository"  # type: ignore[index]

    response = client.post("/v1/submissions", json=payload)

    assert response.status_code == 422


def test_accepts_type_safety_verification() -> None:
    client = TestClient(create_app(InMemorySubmissionStore()))
    payload = submission_payload()
    payload["capabilities"] = ["formal.type-safety"]

    response = client.post("/v1/submissions", json=payload)

    assert response.status_code == 201


def test_requires_formal_configuration_for_bounded_checks() -> None:
    client = TestClient(create_app(InMemorySubmissionStore()))
    payload = submission_payload()
    payload["capabilities"] = ["formal.bounded"]

    response = client.post("/v1/submissions", json=payload)

    assert response.status_code == 422


def test_accepts_all_executable_capabilities_with_formal_configuration() -> None:
    client = TestClient(create_app(InMemorySubmissionStore()))
    payload = submission_payload()
    payload["capabilities"] = [
        "static-analysis",
        "ast-cfg",
        "formal.type-safety",
        "formal.bounded",
        "formal.contracts",
        "agent-review",
    ]
    payload["formal"] = {"contract_path": "verification/contracts.json", "max_cases": 12}

    response = client.post("/v1/submissions", json=payload)

    assert response.status_code == 201
    assert len(response.json()["plan"]["runs"]) == 6
