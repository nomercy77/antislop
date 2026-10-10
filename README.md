# antislop

Backend foundations for reproducible code verification of Python and JavaScript repositories.

The first FastAPI slice accepts a GitHub repository pinned to a commit, resolves requested verification capabilities into versioned plugin runs, and stores the resulting plan in memory. It does **not** clone or execute untrusted code yet.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn antislop.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API schema. Run tests with:

```bash
pytest
```

The verification architecture and roadmap are in [VERIFICATION_BACKEND.md](VERIFICATION_BACKEND.md).
