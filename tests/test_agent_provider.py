from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from threading import Thread

from antislop.agent_review import HttpAgentReviewProvider
from antislop.models import SourceSnapshot


class ReviewHandler(BaseHTTPRequestHandler):
    authorization = ""
    payload: dict[str, object] = {}

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler.
        ReviewHandler.authorization = self.headers["Authorization"]
        ReviewHandler.payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        response = json.dumps(
            {"findings": [{"rule_id": "agent.http", "message": "provider finding", "severity": "low"}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_http_agent_provider_sends_a_bounded_source_bundle(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text("def value() -> int:\n    return 1\n")
    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
        provider = HttpAgentReviewProvider(f"http://127.0.0.1:{server.server_port}/review", "test-token")
        findings, summary = provider.review(
            SourceSnapshot(
                repository_url="https://github.com/example/verified-service",
                commit_sha="a" * 40,
            ),
            tmp_path,
        )
    finally:
        server.shutdown()
        thread.join()

    assert ReviewHandler.authorization == "Bearer test-token"
    assert ReviewHandler.payload["files"][0]["path"] == "service.py"  # type: ignore[index]
    assert findings[0].rule_id == "agent.http"
    assert "finding_count" in summary
