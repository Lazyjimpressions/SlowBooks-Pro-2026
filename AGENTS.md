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

- Keep `main` based on and deliberately reconciled with `upstream/main`; it may
  remain ahead with reviewed fork commits. Develop on feature branches and
  never discard fork work merely to make the refs identical.
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

Local private notes belong in `AGENTS.local.md` or `private-data/`; both are
ignored and must never carry canonical project knowledge.
