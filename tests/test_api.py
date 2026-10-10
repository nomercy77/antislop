from fastapi.testclient import TestClient

from antislop.main import create_app


def submission_payload() -> dict[str, object]:
    return {
        "source": {
            "repository_url": "https://github.com/example/verified-service",
            "commit_sha": "a" * 40,
        },
        "languages": ["python"],
        "capabilities": ["syntax", "formal.type-safety", "formal.bounded"],
        "test_commands": ["pytest"],
        "intended_behavior": "Validate invoice totals.",
    }


def test_submission_creates_a_deterministic_plugin_plan() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/submissions", json=submission_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "planned"
    assert [run["capability"] for run in body["plan"]["runs"]] == [
        "formal.bounded",
        "formal.type-safety",
        "syntax",
    ]
    assert {run["plugin_id"] for run in body["plan"]["runs"]} == {"builtin.formal", "builtin.syntax"}
    assert all(run["status"] == "planned" for run in body["plan"]["runs"])


def test_queued_submission_does_not_execute_in_the_api_process() -> None:
    client = TestClient(create_app())
    created = client.post("/v1/submissions", json=submission_payload()).json()

    response = client.post(f"/v1/submissions/{created['id']}/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert all(run["status"] == "queued" for run in body["plan"]["runs"])


def test_rejects_non_github_repository() -> None:
    client = TestClient(create_app())
    payload = submission_payload()
    payload["source"]["repository_url"] = "https://example.com/owner/repository"  # type: ignore[index]

    response = client.post("/v1/submissions", json=payload)

    assert response.status_code == 422
