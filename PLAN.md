# antislop plan

## Product

antislop reviews agent-written code. It combines automated checks with a paid expert bounty workflow. Every review is tied to a commit so findings are reproducible.

## MVP

- Email login and two roles: submitter and reviewer.
- Submit a GitHub repository, commit/PR, build/test command, and short review brief.
- Run free automated checks: build/test status, static analysis, dependency/license scan, secret detection, and agent-assisted review.
- Let a submitter create a paid bounty with scope, reward, deadline, and acceptance criteria.
- Let verified reviewers claim work and submit structured findings.
- Track findings through response, remediation, and verification.
- Use a mock escrow/payment flow until real payments, identity, and tax requirements are designed.

## Later

- GitHub PR checks, webhooks, API, and CLI.
- Reviewer reputation, conflict-of-interest declarations, and dispute handling.
- Formal-verification engagements: versioned contracts, assumptions, proofs/tests, and known gaps.
- Real payments and payouts.

## Guardrails

- Never execute submitted code outside an isolated runner.
- Store commit SHA, tool versions, commands, and report artifacts with each review.
- Keep private submissions private; redact detected secrets from reports.
- A report states evidence and scope, never a blanket guarantee of correctness or security.
