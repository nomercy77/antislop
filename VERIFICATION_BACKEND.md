# Modular verification backend

## Goal

Given a GitHub repository pinned to a commit, run selected verification work for Python and JavaScript and return reproducible evidence. A submitter chooses a verification level; an expert can add tests, review code, or author contracts.

## Scope

This document covers backend contracts, workers, plugins, and persisted evidence only. It does not define screens, workflows, or frontend state. A contributor can integrate a UI later against the capability catalog and request/result contracts below.

## Verification levels

| Level | Automated work | Expert work |
| --- | --- | --- |
| Baseline | Syntax/compile check, dependency and test discovery, configured tests | — |
| Analysis | Static analysis plus AST/control-flow rules | Review findings when needed |
| Expert review | Automated evidence supplied to the task | Code review or functional tests |
| Formal checks | Type-safety, bounded checks, contract harnesses, and property-style checks | Write or approve contracts, bounds, and tests |

Pricing and UI may group these levels later, but the backend schedules individual capabilities rather than tiers.

## Submission contract

A submission contains:

- GitHub repository URL and immutable commit SHA.
- Selected languages (`python`, `javascript`) and requested capabilities.
- Optional build/test commands, paths in scope, and intended behavior.
- A review/task brief and, for paid work, acceptance criteria.

Language detection can suggest choices, but the pinned SHA and selected languages are the source of truth for a run.

## Plugin model

All automated checks implement one interface. Plugins are versioned, declare their supported languages and capabilities, and do not write to product tables directly.

```text
Plugin manifest: id, version, languages, capabilities, config schema
Run input:      source snapshot, normalized config, execution policy
Run output:     status, findings, evidence/artifact references, tool metadata
```

Initial plugin families:

- `syntax`: Python compilation and JavaScript syntax/module checks.
- `tests`: discover and run explicitly configured Python or JavaScript tests.
- `static-analysis`: language-specific lint, type, dependency, and security checks.
- `ast-cfg`: AST and control-flow rules; each rule emits locations and evidence.
- `formal.type-safety`: check Python annotations and JavaScript type declarations/annotations where present; report unsupported or dynamically untyped boundaries.
- `formal.bounded`: explore declared or generated inputs/states within recorded bounds and emit counterexamples when found.
- `formal.contracts`: execute versioned preconditions, postconditions, invariants, and property-style checks.
- `agent-review`: produce a review draft grounded in the source snapshot and other evidence; it never closes a finding or marks a contract proved.

The orchestrator resolves a requested capability into compatible plugins. It can run independent plugins in parallel, records every plugin version/configuration, and normalizes outputs into the existing `Finding` and `Artifact` records.

## Execution path

```text
submission (repo + SHA + choices)
  -> verification plan
  -> queued plugin runs
  -> isolated workers
  -> findings and evidence
  -> expert task, if requested
  -> remediation verification against a new SHA
```

Workers clone only the pinned commit into an ephemeral sandbox. They have no production credentials, bounded CPU/memory/time/disk, and restricted network access. The API, plugin registry, queue, artifact storage, and PostgreSQL remain outside the sandbox.

## Expert workflow

An expert task is linked to a submission and the evidence already produced. The expert may submit:

- Functional tests, including expected behavior and reproduction commands.
- Code-review findings with severity, evidence, and remediation guidance.
- A contract package: target functions, specification, assumptions, harness/tests, and known gaps.

An agent may propose tests or contracts, but an expert must approve authored high-assurance artifacts before they are presented as expert work. All expert artifacts are versioned and tied to the source SHA.

## Contracts and formal-methods boundary

The first Python/JavaScript release includes the formal checks that are already practical for dynamic languages: type-safety checks where type information exists, finite/bounded state or input exploration, and executable preconditions, postconditions, invariants, and properties. Each check records its supported language subset and concrete bounds. A passing run means the stated property held for the recorded assumptions, environment, and bounds.

The formal plugin family may later add restricted specifications and proof backends. A verification report may call something *proved* only when it stores the exact contract, engine/tool version, assumptions, proof output, and unresolved gaps. Dynamic code outside the supported subset remains a type-checked, bounded, or runtime-verified result.

## Minimal data additions

Add `VerificationPlan`, `PluginRun`, `ContractPackage`, and `ExpertTask` records. `PluginRun` links a plugin version and normalized configuration to artifacts/findings. `ContractPackage` links a specification and harness to a source SHA; `ExpertTask` records the requested work and its submitted artifact.

## Delivery order

1. Define the submission schema, capability selection, plugin manifest, plan resolver, and isolated-runner protocol.
2. Ship Python/JavaScript syntax, configured tests, and one static-analysis plugin per language.
3. Add normalized findings/evidence and remediation reruns at a new commit SHA.
4. Add type-safety, bounded, and runtime-contract plugins with explicit supported subsets and claim labels.
5. Add expert functional-test and code-review tasks; defer proof backends until the supported contract subset is explicit.

## Success criteria for the first slice

- A pinned Python or JavaScript repository can complete a baseline plan in an isolated runner.
- Each result identifies source SHA, plugin/tool version, command, status, and artifacts.
- A reviewer can turn evidence into a test or finding and a submitter can request a rerun after remediation.
- Unsupported language features or verification claims fail explicitly; they are never silently labeled verified.
