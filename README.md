# antislop

**Verification infrastructure for agent-written code.** antislop takes a GitHub repository pinned to an immutable commit, turns a requested review level into versioned verification runs, and returns findings with reproducible evidence.

It is built for the uncomfortable gap between “an agent produced code that looks plausible” and “we have evidence that this change is safe enough to merge.” The platform combines deterministic checks, bounded contracts, solver-backed theorem checks, and a separately configured agent-review boundary. Human experts can later build on the same evidence trail rather than starting from a blank page.

> Hackathon scope: this repository contains the verification backend only. Product UI, identity, bounty workflow, expert credentials, and payments are deliberately out of this slice; their integration shape is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## Why antislop

Agent-written code changes the review bottleneck: generating a patch is cheap, but establishing confidence in it is not. antislop is designed around a few non-negotiables:

- **Immutable inputs:** every submission names a GitHub URL and a full commit SHA—never a floating branch.
- **Reproducible evidence:** every completed run has a content-addressed attestation covering its command, policy, selected configuration, findings, runner identity, and emitted artifacts.
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
| `formal.theorem-proving` | Yes (preview) | Not yet | Z3 proved the submitted restricted integer theorem; when source-linked, the function's supported return expression is part of that proof. |
| `agent-review` | Provider-backed | Provider-backed | A configured trusted service returned structured, evidence-backed findings. |

Every run exposes an explicit `claim` with a level and status—not a generic green check. For example: `syntax-valid/satisfied`, `runtime-contract-held/counterexample`, or `theorem-proved/proved`. `formal.bounded` and `formal.contracts` remain runtime checks—not proofs. The theorem preview can link a narrow Python expression subset, but it does not prove arbitrary Python programs correct.

## End-to-end assurance showcase

The included `square()` sample exercises the complete path against an immutable GitHub commit: plan → queue → restricted checkout → Docker runner → evidence attestation. It produces two distinct, intentionally non-interchangeable outcomes:

| Check | Claim emitted | Evidence retained |
| --- | --- | --- |
| Executable contract cases | `runtime-contract-held/satisfied` | `findings.json`, container log, contract configuration, attestation hashes |
| Source-linked Z3 theorem | `theorem-proved/proved` | `proofs.json`, `findings.json`, container log, linked-source result, attestation hashes |

An API consumer receives the claim and evidence together:

```json
{
  "capability": "formal.theorem-proving",
  "status": "succeeded",
  "claim": {
    "level": "theorem-proved",
    "status": "proved",
    "summary": "Restricted integer theorem was proved."
  },
  "evidence": {
    "runner_image": "antislop-runner-python:0.1.0",
    "attestation": {
      "source_commit_sha": "<full SHA>",
      "plugin_id": "builtin.theorem-proving",
      "artifact_sha256": {
        "container.log": "<sha256>",
        "findings.json": "<sha256>",
        "proofs.json": "<sha256>"
      },
      "integrity_sha256": "<sha256>"
    }
  }
}
```

The same design fails informatively: a broken runtime assertion becomes `runtime-contract-held/counterexample` and retains replayable arguments; a satisfiable negated theorem becomes `theorem-proved/counterexample` and retains the solver model. A timeout, malformed artifact, unavailable runner, or nonzero plugin exit becomes `failed`—never an optimistic assurance claim.

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

After completion, antislop records an integrity attestation (`schema_version: v1`) containing SHA-256 hashes for the command, execution policy, normalized verification configuration, findings, and every emitted artifact. It also records the source commit, plugin/version, and local runner-image identity. The final `integrity_sha256` hashes that envelope. This is tamper-evident evidence binding, not yet a cryptographic signature or transparency log.

## Sandbox and evidence model

Verification code executes in Docker with an explicit security posture:

- Verification containers have **no network**, a **read-only source mount**, a **read-only root filesystem**, no Linux capabilities, `no-new-privileges`, a non-root UID, and bounded CPU, memory, PID, and wall-clock limits.
- The source checkout is a separate, unprivileged fetch step with only the network access needed to retrieve the already validated GitHub URL and SHA. It receives no credentials. Production deployment should place this behind GitHub-only egress.
- Runner images are built ahead of time and workers use `--pull never`; repositories cannot install arbitrary dependencies while being verified.
- Logs and structured `findings.json` artifacts are retained per plugin run. Proof runs also emit `proofs.json`; failed theorem claims retain the solver model. Runtime-contract counterexamples retain the target, case index, arguments, keyword arguments, and assertion case needed to reproduce them. SQLite is the current durable queue for a single worker; the storage interface is intentionally narrow so a production deployment can use Postgres and object storage.

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

## Workspace UI: submit to verification

The merged workspace UI provides submitter, coder/doer, and verification-staff workspaces with server-enforced sessions and role permissions. In live mode, a submitter supplies a GitHub URL, a **full 40-character commit SHA**, stack, scope, and a verification level. Creating the review persists the marketplace record **and queues an antislop verification plan** against the same immutable source snapshot.

Run the workspace API and static UI separately:

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm run dev
```

Set `apiBaseUrl` in `dist/config.js` to `http://127.0.0.1:8000`, configure `.env` from `.env.example`, then run `antislop-worker --database-path .antislop/antislop.sqlite3`. The review detail page shows the queued plan and assurance claims; the authenticated API exposes the complete evidence at `GET /api/reviews/{review_id}/verification` to the submitter or assigned approved reviewer.

## Submit and queue a verification plan

Create a submission against a pinned commit. Replace the SHA and repository with the change you want to verify.

```bash
curl --request POST http://127.0.0.1:8000/v1/submissions \
  --header 'Content-Type: application/json' \
  --data '{
    "source": {
      "repository_url": "https://github.com/nomercy77/antislop",
      "commit_sha": "d394b2c9c57b61d6e8eba59e1a2f5de399bbbbf7"
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

Poll the submission to read plugin status, explicit assurance claim, evidence, output tails, log paths, normalized findings, and the attestation digest:

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
    "left": {"var": "result"},
    "right": {"int": 0}
  }
}
```

When `source` is present, the preview links its `result` variable to a Python function only if the function has positional parameters matching the theorem variables and a single return expression made from integer constants, parameters, `+`, `-`, `*`, and unary `-`. Unsupported code is rejected as unlinked—not waved through. The sample's `square()` proof therefore establishes both that its supported return expression is `value * value` and that the returned result is non-negative over mathematical integers.

This is still not arbitrary-program verification: control flow, heap state, imports, exceptions, Python integer coercions, and behavior outside the restricted expression subset are not modeled. Counterexamples are saved in `proofs.json` with the exact model; contract counterexamples include executable input data in their finding evidence. The full runnable example is in [examples/theorem_sample_repo](examples/theorem_sample_repo).

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
- The theorem linker supports only single-expression integer functions. Future work needs a larger restricted source semantics, symbolic execution, or proof-producing translation before claiming broader implementation correctness.
- Private repositories, dependency builds, multi-worker queue coordination, GitHub App authentication, Postgres/object storage, and the marketplace UI are not yet included.
- Static and AST/CFG adapters are intentionally compact built-ins today. The plugin boundary is where richer analyzers, security scanners, fuzzers, model checkers, and expert-authored verification packages attach.

The backend architecture and longer-term verification roadmap are in [VERIFICATION_BACKEND.md](VERIFICATION_BACKEND.md); the broader marketplace shape is in [ARCHITECTURE.md](ARCHITECTURE.md).
