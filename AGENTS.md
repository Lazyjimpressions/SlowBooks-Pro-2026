# Agent operating instructions

These instructions apply to Codex, Claude Code, Cursor, and other coding
agents working in this repository.

## Required reading

Before changing code, read:

1. `docs/agent/START_HERE.md`
2. `docs/agent/CURRENT_STATE.md`
3. The domain document routed from `docs/agent/START_HERE.md`
4. Any implementation plan named by the active GitHub issue or user request

Do not rely on chat history or platform-specific memory as the source of
truth. Durable decisions belong in Git, tests, GitHub issues, and pull
requests.

## Non-negotiable rules

- Keep `origin/main` as a clean mirror of `upstream/main` after the documented
  one-time realignment. Do not merge fork-only application or operating-policy
  commits into it. Preserve prior fork work through archive tags and branches.
- Start every product contribution from current `upstream/main`, keep it small,
  and send it upstream before beginning dependent work. When upstream merges
  it, synchronize `origin/main` and retire the contribution branch.
- Preserve upstream compatibility and keep changes small enough to propose
  upstream unless a decision record explicitly marks them private-specific.
- Never commit real company databases, bank exports, customer/vendor data,
  credentials, tokens, logs, backups, or unsanitized screenshots.
- Never use a real company database in automated tests. Use in-memory data or
  synthetic fixtures.
- Imported bank rows are not accounting entries. Financial reports change
  only through balanced journal lines.
- A retry must not duplicate a bank row, move its balance twice, or post a
  second journal entry.
- Transfers must not be classified as income or expense.
- Reverse posted accounting entries; do not destructively rewrite history.
- Do not weaken closing-date, authentication, authorization, audit, or upload
  controls to make a workflow pass.
- Update relevant documentation and tests in the same change as behavior.

## Before work

Run `git status --short --branch`, confirm the intended checkout and branch,
fetch upstream when network access is authorized, and inspect upstream changes
that overlap the task. Preserve unrelated user changes.

## Completion

Run targeted tests first, then formatting, lint, and the proportionate broader
suite. Update `docs/agent/CURRENT_STATE.md` only with verified facts. Record a
material architecture decision in `docs/agent/decisions/` and link the GitHub
issue in the pull request.

Canonical LazyJimpressions operating policy belongs in the private
`slowbooks-ai-ops` repository. A locally installed `AGENTS.local.md` may point
agents there, but ignored files must not be the only copy of durable knowledge.
