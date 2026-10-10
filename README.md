# antislop

**Evidence-first code verification for the age of AI-generated software.** antislop turns a GitHub repository pinned to an immutable commit into a review workflow that combines programmatic checks, bounded mathematical claims, agent review, and accountable human expertise.

AI can produce a plausible patch in seconds; proving that it is safe, complete, and aligned with the intended behavior is the hard part. antislop is built to clean up that gap. Instead of a generic “looks good” verdict, it separates what was parsed, analyzed, executed, bounded, contract-checked, solver-proved, or reviewed by a verified expert—and retains the evidence for each claim.

The repository contains both the modular verification engine and the FastAPI-backed product workflow: authenticated submitter, coder/doer, and verification-staff workspaces; pinned review creation; durable verification jobs; expert assignment; and structured expert delivery. Payments, GitHub App grants, and public deployment are intentionally still mock or configuration-dependent boundaries, never silently represented as complete.

## Why antislop

Agent-written code changes the review bottleneck: generating a patch is cheap, but establishing confidence in it is not. antislop is designed around a few non-negotiables:

- **Immutable inputs:** every submission names a GitHub URL and a full commit SHA—never a floating branch.
- **Reproducible evidence:** every completed run has a content-addressed attestation covering its command, policy, selected configuration, findings, runner identity, and emitted artifacts.
- **Isolation before execution:** the API plans work; a Docker worker runs untrusted repository code outside the API process.
- **Honest assurance labels:** syntax, static findings, bounded contracts, and theorem proofs are different claims. The result tells you which one you received.
- **Human/agent continuity:** automated evidence is structured so an expert task or agent review can cite it directly.

## From AI code to a defensible merge decision

```text
GitHub URL + immutable commit SHA
              |
              v
   automated evidence plan (selected assurance level)
              |
      +-------+--------+----------------+
      |                |                |
      v                v                v
 static / AST      contracts &       configured
 type analysis     bounded checks    agent review
                       |
                       v
                restricted Z3 proof
                where applicable
                       |
                       v
      evidence, claims, counterexamples, attestations
                       |
                       v
      verified expert: tests, contracts, or full review
                       |
                       v
            merge decision with an audit trail
```

antislop is not trying to pretend that one tool can “verify code.” It composes layers with explicit scope:

| Layer | What it contributes | What it deliberately does not claim |
| --- | --- | --- |
| Syntax, static analysis, AST/CFG and type checks | Fast, deterministic signals for broken structure, dangerous patterns, reachable control-flow concerns, and declared type inconsistencies. | That the program meets its full business specification. |
| Sandboxed tests and runtime contracts | Executable evidence for specified cases, pre/postconditions, and regressions under recorded bounds. | A universal proof beyond the executed cases and supported contract model. |
| Theorem proving preview | Z3-backed proofs for a restricted, source-linked Python integer-expression subset; solver counterexamples are retained when a theorem fails. | Proof of arbitrary Python or JavaScript programs, heap behavior, imports, exceptions, or unmodeled runtime semantics. |
| Agent review | Structured findings from an explicitly configured provider, attached to the same pinned source and evidence record. | An independent mathematical proof or an unconfigured model response. |
| Verified human review | Functional tests, formal contracts, or manual code review delivered by an approved expert against the same immutable revision. | Automatic GitHub access, payment, or identity proof beyond the platform’s current verification process. |

## Product workflow

1. **Submit a review:** a code owner supplies a GitHub repository, a full 40-character commit SHA, scope, language, assurance level, and optionally an expert deliverable.
2. **Plan and queue verification:** FastAPI validates the request, builds a versioned capability plan, persists it, and queues the work without running untrusted code in the API process.
3. **Execute in a constrained worker:** the worker checks out the requested revision and runs only selected plugin capabilities inside language-specific Docker runners.
4. **Make results inspectable:** the review shows planned and completed runs, findings, assurance claims, artifacts, and integrity attestation rather than a single opaque score.
5. **Escalate with context:** an approved coder can be assigned to write functional tests, formal contracts, or a manual full review. Their structured delivery stays attached to the same review record.

Expert work is tiered, server-priced, and optional: functional tests ($75/$150), formal contracts ($150/$300), and manual review ($100/$250) for standard/deep scope. These are mock commercial terms today—no charge, escrow, or payout is executed—but the authorization and delivery lifecycle is real application state.

### Deterministic proof first; expert judgment where it matters

Antislop is designed to remove the repeatable bulk of review before it reaches an expert. A selected plan deterministically runs the same syntax, static, AST/CFG, type, test, contract, bounded, and supported theorem checks against the same pinned commit. It records the exact plugin version, command policy, configuration, logs, findings, proof artifacts, counterexamples, and integrity hashes. Re-running the same supported plan against the same source is therefore an evidence-producing operation, not a new subjective review.

This changes the human task from “read everything and rediscover obvious failures” to higher-value work: define the right contract, challenge assumptions that the bounded model does not cover, add adversarial functional tests, interpret a solver counterexample, and judge product, security, and operational intent. When a restricted theorem is provable, the expert inherits the proof and its stated assumptions. When it is not, the expert inherits the recorded counterexample or failure evidence. The platform does not replace expert judgment; it gives experts a deterministic evidence base and reserves their time for the ambiguity that tools cannot honestly resolve.

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

### Current development backend URLs

- Local API: `http://127.0.0.1:8000`
- Current Cloudflare development tunnel: `https://ballet-customers-campbell-volvo.trycloudflare.com`
- Tunnel health check: `https://ballet-customers-campbell-volvo.trycloudflare.com/api/health`

The Cloudflare URL is an account-less quick tunnel for the currently running local process. It changes when the tunnel stops or restarts and is not a production endpoint. Set the frontend API base URL to the tunnel origin only while that process is running; production deployments should use a named tunnel or hosted API with an explicit CORS allowlist.

### Human expert work, grounded in the automated evidence

When creating a review, a submitter can request an optional human deliverable in addition to the selected automated checks. The API—not the browser—sets the fixed mock price and persists the exact request. Only approved coders can browse these opportunities, be assigned, view the private review, and submit a delivery summary plus an optional HTTPS artifact URL.

| Deliverable | Standard | Deep |
| --- | ---: | ---: |
| Functional tests | $75 | $150 |
| Formal contracts | $150 | $300 |
| Full manual review | $100 | $250 |

The coder dashboard shows assigned deliverables and their lifecycle (`requested → assigned → completed`). This is deliberately a payment-safe showcase: no card charge, escrow, payout, or GitHub permission is implied by assignment. Human reviewers receive the same pinned SHA and automated verification record, so tests, contracts, and review notes can refer to concrete evidence rather than an unpinned repository state.

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
