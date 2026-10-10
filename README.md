# antislop

Backend foundations for reproducible code verification of Python and JavaScript repositories.

The first FastAPI slice accepts a GitHub repository pinned to a commit and resolves requested verification capabilities into versioned plugin runs. Syntax checks and configured tests are executable in Docker; the other capabilities are intentionally advertised as planned until their adapters exist.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install '.[dev]'
uvicorn antislop.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API schema. Run tests with:

```bash
pytest
```

## Run verification jobs

Build the trusted runner images once. The worker never pulls images while processing a job.

```bash
docker build --tag antislop-runner-python:0.1.0 --file docker/python-runner.Dockerfile .
docker build --tag antislop-runner-javascript:0.1.0 --file docker/javascript-runner.Dockerfile .
```

Start the API, create and queue a submission, then run the worker separately:

```bash
antislop-worker
```

Jobs are stored in `.antislop/antislop.sqlite3`; logs are retained under `.antislop/artifacts/`. The worker fetches the submitted GitHub commit in a limited fetch container; that stage has network access but no credentials, and production should route it through a GitHub-only egress proxy. Verification containers then run with no network, a read-only repository mount, no Linux capabilities, a non-root user, and CPU, memory, PID, and time limits. Repositories that need dependencies not already in the runner image will fail rather than installing arbitrary packages during verification.

## Formal checks

`formal.type-safety` uses mypy for Python and the TypeScript checker in JavaScript-checking mode. `formal.bounded` and `formal.contracts` use the same restricted JSON contract format. The submitter includes its repository-relative `formal.contract_path` and `formal.max_cases` in the request.

Each contract target declares a callable, explicit cases and/or finite parameter values, and optional JSON-safe assertions (`expected`, `type`, `minimum`, `maximum`, or `truthy`). Python targets use `module` and `function`; JavaScript targets use a repository-relative CommonJS `module` path and exported `function`. See [examples/contracts](examples/contracts).

These are bounded/runtime results—not general proofs. A pass means all recorded cases and assertions held within the selected bounds.

## Agent review provider

Set `ANTISLOP_AGENT_REVIEW_URL` and `ANTISLOP_AGENT_REVIEW_TOKEN` for the trusted service that invokes your chosen model. antislop sends the immutable source reference, a byte-bounded source bundle, and explicit instructions to treat source text as untrusted data. The provider must return:

```json
{
  "findings": [
    {"rule_id": "agent.example", "message": "Evidence-backed finding", "severity": "medium", "path": "src/app.py", "line": 12}
  ]
}
```

The provider runs outside the Docker code sandbox and has no Docker access. Without this configuration, an agent-review job fails explicitly rather than pretending review occurred.

The verification architecture and roadmap are in [VERIFICATION_BACKEND.md](VERIFICATION_BACKEND.md).
