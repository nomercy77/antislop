# antislop

**Verification infrastructure for agent-written code.** antislop takes a GitHub repository pinned to an immutable commit, turns a requested review level into versioned verification runs, and returns findings with reproducible evidence.

It is built for the uncomfortable gap between “an agent produced code that looks plausible” and “we have evidence that this change is safe enough to merge.” The platform combines deterministic checks, bounded contracts, solver-backed theorem checks, and a separately configured agent-review boundary. Human experts can later build on the same evidence trail rather than starting from a blank page.

> Hackathon scope: this repository contains the verification backend only. Product UI, identity, bounty workflow, expert credentials, and payments are deliberately out of this slice; their integration shape is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## Why antislop

Agent-written code changes the review bottleneck: generating a patch is cheap, but establishing confidence in it is not. antislop is designed around a few non-negotiables:

- **Immutable inputs:** every submission names a GitHub URL and a full commit SHA—never a floating branch.
- **Reproducible evidence:** every capability resolves to a versioned plugin run with its command, logs, findings, and timestamps.
- **Isolation before execution:** the API plans work; a Docker worker runs untrusted repository code outside the API process.
- **Honest assurance labels:** syntax, static findings, bounded contracts, and theorem proofs are different claims. The result tells you which one you received.
- **Human/agent continuity:** automated evidence is structured so an expert task or agent review can cite it directly.

## What is shipped

| Capability | Python | JavaScript | What a passing result means |
| --- | --- | --- | --- |
| `syntax` | Yes | Yes | Source parses/compiles under the runner language tool. |
| `tests` | Yes | Yes | Submitter-specified commands exited successfully in the sandbox. |
| `static-analysis` | Yes | Yes | Built-in language rules completed; findings remain attached to the run. |
| `ast-cfg` | Yes | Yes | Built-in AST/control-flow rules completed and emitted any findings. |
| `formal.type-safety` | mypy | TypeScript `allowJs` / `checkJs` | The configured checker completed; type diagnostics are findings, not silently discarded. |
| `formal.bounded` | Yes | Yes | A finite set of declared/generated contract cases held within the recorded bound. |
| `formal.contracts` | Yes | Yes | Declared runtime contract cases and assertions held. |
| `formal.theorem-proving` | Yes (preview) | Not yet | Z3 proved the submitted restricted integer theorem, under its stated assumptions. |
| `agent-review` | Provider-backed | Provider-backed | A configured trusted service returned structured, evidence-backed findings. |

`formal.bounded` and `formal.contracts` are runtime checks—not proofs. `formal.theorem-proving` is a proof of a deliberately small declarative DSL, not proof that arbitrary Python implementation code equals that specification. Those distinctions are intentional and visible in the result model.

## System design

```text
                 GitHub repo + full commit SHA
                              |
                              v
 FastAPI  ->  capability planner  ->  durable job queue
   |                                      |
   |                                      v
   |                              pinned source checkout
   |                                      |
   |                                      v
   |                         isolated Docker plugin runs
   |                           |        |        |
   v                           v        v        v
 API / evidence             findings   logs   proof artifacts
                                      |
                                      v
                            expert task / agent review
```

The API resolves capabilities using plugin manifests (`id`, version, supported languages, configuration schema, state). It does not execute submitted code. The worker fetches the requested SHA once, then invokes the selected language runner once per plugin capability. Findings share a common shape—rule id, severity, message, path, line, and evidence—so an automated report and an expert review can use the same downstream model.

## Sandbox and evidence model

Verification code executes in Docker with an explicit security posture:

- Verification containers have **no network**, a **read-only source mount**, a **read-only root filesystem**, no Linux capabilities, `no-new-privileges`, a non-root UID, and bounded CPU, memory, PID, and wall-clock limits.
- The source checkout is a separate, unprivileged fetch step with only the network access needed to retrieve the already validated GitHub URL and SHA. It receives no credentials. Production deployment should place this behind GitHub-only egress.
- Runner images are built ahead of time and workers use `--pull never`; repositories cannot install arbitrary dependencies while being verified.
- Logs and structured `findings.json` artifacts are retained per plugin run. SQLite is the current durable queue for a single worker; the storage interface is intentionally narrow so a production deployment can use Postgres and object storage.

This is a useful trust boundary, not a claim that arbitrary hostile code is risk-free. It is designed to make execution constrained, attributable, and replaceable with stronger isolation as the platform evolves.

## Quick start

Requirements: Python 3.11+, Docker Desktop (or Docker Engine), and access to a public GitHub repository at a full commit SHA.

```bash
git clone https://github.com/nomercy77/antislop.git
cd antislop

python3 -m venv .venv
. .venv/bin/activate
python -m pip install '.[dev]'

docker build --tag antislop-runner-python:0.1.0 --file docker/python-runner.Dockerfile .
docker build --tag antislop-runner-javascript:0.1.0 --file docker/javascript-runner.Dockerfile .

pytest
uvicorn antislop.main:app --reload
```

The API documentation is then available at `http://127.0.0.1:8000/docs`. In a second terminal, start the worker:

```bash
. .venv/bin/activate
antislop-worker
```

Local state is stored in `.antislop/antislop.sqlite3`; per-run logs and artifacts are stored in `.antislop/artifacts/`.

## Submit and queue a verification plan

Create a submission against a pinned commit. Replace the SHA and repository with the change you want to verify.

```bash
curl --request POST http://127.0.0.1:8000/v1/submissions \
  --header 'Content-Type: application/json' \
  --data '{
    "source": {
      "repository_url": "https://github.com/nomercy77/antislop",
      "commit_sha": "165387bccb83e23f9c80bf6ebe26a363dc93d3dd"
    },
    "languages": ["python"],
    "capabilities": ["static-analysis", "ast-cfg", "formal.contracts", "formal.theorem-proving"],
    "formal": {
      "contract_path": "examples/theorem_sample_repo/.antislop/contracts.json",
      "theorem_path": "examples/theorem_sample_repo/.antislop/theorems.json",
      "max_cases": 100
    }
  }'
```

The response contains a submission UUID and the planned plugin runs. Queue it with:

```bash
curl --request POST http://127.0.0.1:8000/v1/submissions/<submission-id>/queue
```

Poll the submission to read plugin status, evidence, output tails, log paths, and normalized findings:

```bash
curl http://127.0.0.1:8000/v1/submissions/<submission-id>
```

Discover the supported plugins and their configuration expectations through `GET /v1/capabilities`.

## Contracts: bounded, executable behavior

`formal.bounded` and `formal.contracts` share a restricted JSON contract format. A target identifies a callable, explicit cases and/or finite parameter domains, and JSON-safe assertions: `expected`, `type`, `minimum`, `maximum`, or `truthy`.

```json
{
  "targets": [
    {
      "module": "examples.theorem_sample_repo.math_utils",
      "function": "square",
      "cases": [
        {"args": [-2], "expected": 4},
        {"args": [0], "expected": 0},
        {"args": [3], "expected": 9}
      ]
    }
  ]
}
```

Python targets use an importable module and function. JavaScript targets use a repository-relative CommonJS module path and exported function. Finite parameter domains are expanded only up to `formal.max_cases` (1–10,000), making the bound explicit and reproducible. See [Python and JavaScript contract examples](examples/contracts).

## Theorem proving: precise, deliberately restricted claims

The Python preview uses Z3 to prove formulas over **unbounded mathematical integers**. It supports:

- integer variables;
- expressions: `add`, `sub`, `mul`, `neg`;
- propositions: `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `and`, `or`, `not`.

For each theorem, antislop asks Z3 whether `assumptions AND NOT(conclusion)` is satisfiable. `unsat` is recorded as proved; a satisfying model becomes a counterexample finding; `unknown` is reported as non-proof.

```json
{
  "id": "square_is_nonnegative",
  "source": {"path": "examples/theorem_sample_repo/math_utils.py", "symbol": "square"},
  "variables": {"value": "int"},
  "assumptions": [],
  "conclusion": {
    "op": "ge",
    "left": {"op": "mul", "args": [{"var": "value"}, {"var": "value"}]},
    "right": {"int": 0}
  }
}
```

The `source` field is traceability metadata in this preview. The solver proves the declarative theorem; it does **not** derive the formula from, or establish equivalence with, arbitrary Python source. That is the next formal-methods boundary to cross, and it should only be claimed once there is a restricted program semantics or proof-producing translation. The full runnable example is in [examples/theorem_sample_repo](examples/theorem_sample_repo).

## Agent review boundary

`agent-review` is intentionally provider-agnostic. Configure a trusted model service with:

```bash
export ANTISLOP_AGENT_REVIEW_URL='https://reviewer.example/v1/review'
export ANTISLOP_AGENT_REVIEW_TOKEN='...'
```

The worker sends the immutable source reference, a source bundle capped at 256 KB, and an instruction to treat all repository content as untrusted data. It excludes `.git`, dependency directories, virtual environments, and bytecode caches. The provider must return structured findings:

```json
{
  "findings": [
    {
      "rule_id": "agent.unvalidated-input",
      "message": "Request body reaches a shell command without validation.",
      "severity": "high",
      "path": "src/app.py",
      "line": 42,
      "evidence": "..."
    }
  ]
}
```

The provider runs outside the untrusted-code Docker sandbox and gets no Docker access. If it is not configured, the job fails explicitly instead of fabricating a review. Agent output is evidence for review, not proof and not an automatic approval decision.

## Project map

| Path | Purpose |
| --- | --- |
| `src/antislop/main.py` | FastAPI submission, capability, and queue endpoints. |
| `src/antislop/plugins/` | Plugin manifests, registry, and safe command construction. |
| `src/antislop/sandbox.py` | Pinned checkout and Docker isolation boundary. |
| `src/antislop/worker.py` | Queue consumer and plugin-run lifecycle. |
| `docker/tools/` | Language-specific syntax, analysis, contract, and theorem adapters. |
| `examples/contracts/` | Python and JavaScript runtime-contract examples. |
| `examples/theorem_sample_repo/` | End-to-end contract and Z3-theorem sample. |
| `VERIFICATION_BACKEND.md` | Backend protocol, expert workflow, and longer-term roadmap. |
| `ARCHITECTURE.md` | Broader product architecture: marketplace, evidence, and payments. |

## Current limitations and next steps

- JavaScript theorem proving is not implemented; the Z3 theorem plugin currently targets Python submissions only.
- The theorem DSL proves statements, not arbitrary code/spec equivalence. Future work needs a restricted source subset, symbolic execution, or proof-producing translation before claiming implementation correctness.
- Private repositories, dependency builds, multi-worker queue coordination, GitHub App authentication, Postgres/object storage, and the marketplace UI are not yet included.
- Static and AST/CFG adapters are intentionally compact built-ins today. The plugin boundary is where richer analyzers, security scanners, fuzzers, model checkers, and expert-authored verification packages attach.

The backend architecture and longer-term verification roadmap are in [VERIFICATION_BACKEND.md](VERIFICATION_BACKEND.md); the broader marketplace shape is in [ARCHITECTURE.md](ARCHITECTURE.md).
