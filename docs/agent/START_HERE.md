# Start here

This directory is the durable operating memory shared by every coding agent.
Chat history and vendor-specific memory can help, but they do not override the
repository.

## Reading order

1. Root `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. The relevant domain file:
   - Banking or imports: `ACCOUNTING_INVARIANTS.md` and `BANKING_AUTOMATION.md`
   - API agents: `API_AND_SCOPES.md`
   - GitHub, releases, or pull requests: `UPSTREAM_WORKFLOW.md`
   - Credentials or business data: `SECURITY_AND_DATA.md`
5. The implementation plan linked by the active issue
6. Applicable existing product documentation and tests

## Sources of truth

- Code and migrations define current behavior.
- Tests define executable invariants.
- `CURRENT_STATE.md` records verified state, not aspirations.
- Architecture decision records explain durable choices.
- GitHub issues describe pending work; pull requests describe active changes.
- `ROADMAP.md` gives sequence, not a claim that work is implemented.

If sources conflict, inspect the running code and tests, correct the stale
document in the same change, and explain the discrepancy in the pull request.

## Session handoff

Do not commit raw session transcripts. Before ending material work:

- leave the working tree understandable;
- update the implementation plan and current state where behavior changed;
- record commands and verification in the pull request;
- put remaining tasks in the linked GitHub issue.
