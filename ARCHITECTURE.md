# antislop architecture

## Shape

Start as a modular web application with one relational database and an isolated job runner. Keep the API, UI, and workers separately deployable; do not split into microservices yet.

```text
Web UI -> API -> PostgreSQL
             |-> job queue -> isolated runner -> scan artifacts
             |-> object storage (logs, reports, attachments)
```

## Core modules

| Module | Responsibility |
| --- | --- |
| Identity | Login, roles, reviewer verification state. |
| Submissions | Repository/commit metadata, scope, and review brief. |
| Reviews | Automated runs, bounties, assignments, findings, and remediation state. |
| Runner | Clones a pinned commit and runs allowed tools in an ephemeral sandbox. |
| Payments | Mock escrow, reward, payout, and transaction states. |
| Evidence | Immutable logs, tool versions, report artifacts, and audit events. |

## Core records

`User`, `ReviewerProfile`, `Submission`, `Review`, `AutomatedRun`, `Bounty`, `Assignment`, `Finding`, `Remediation`, `Payment`, and `Artifact`.

A `Submission` references a repository URL and immutable commit SHA. A `Review` belongs to one submission; automated and expert findings share the same finding format.

## Review lifecycle

```text
submitted -> automated_reviewed -> bounty_open -> assigned
-> findings_submitted -> remediation_requested -> verified -> closed
```

Formal verification is a later review type. Its artifacts must record the contract/specification, assumptions, tool version, proof or test output, and unresolved gaps.

## Boundaries

- The API never executes untrusted repository code.
- Runners have no production credentials and use short-lived, restricted network access.
- Secrets are redacted before artifacts become visible to reviewers.
- Payment state is internal and mocked until a payment provider is introduced.
