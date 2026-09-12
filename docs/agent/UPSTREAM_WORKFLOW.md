# Upstream workflow

## Remotes

- `origin`: `Lazyjimpressions/SlowBooks-Pro-2026`
- `upstream`: `VonHoltenCodes/SlowBooks-Pro-2026`

After the one-time archived-fork transition, `origin/main` is a clean mirror of
`upstream/main`. It is not an integration branch and must not accumulate
fork-only application code or LazyJimpressions operating policy. The private
`slowbooks-ai-ops` repository is the canonical home for that policy.

Refresh the mirror before starting work:

```bash
git fetch upstream --prune
git switch main
git merge --ff-only upstream/main
git push origin main
git switch -c fix/descriptive-name upstream/main
```

Never develop directly on `main`. Before opening or updating an upstream PR,
rebase the contribution branch on current `upstream/main`, rerun the relevant
tests, and push it to `origin`. If upstream moves quickly enough that a rebase
would obscure review, create a fresh branch from upstream and cherry-pick only
the contribution commits.

The existing divergent fork is a one-time exception. Preserve it with verified
archive tags before realigning `origin/main`; use `--force-with-lease`, never an
unqualified force push, and perform that transition as its own reviewed action.

## Pull requests

- For a material design, discuss the problem in an upstream issue before
  writing a broad solution. Evidence-backed, narrow fixes may go directly to a
  draft upstream PR.
- Use one branch and one upstream PR per independently mergeable change. Avoid
  stacking a second feature on an unmerged contribution.
- Keep generic code and synthetic tests isolated from private AI policy and
  business mappings.
- Reference the issue and state database, security, compatibility, and test
  impact. Follow the maintainer's evidence and release-gate conventions.
- Let the upstream maintainer merge, rebase, or cherry-pick into the official
  release branch. We do not have or need direct push access to upstream.
- After upstream accepts the work, fetch it back through `upstream/main`,
  fast-forward `origin/main`, verify authorship, and delete the contribution
  branch. Do not keep a duplicate fork patch.
- If upstream declines or materially redesigns a proposal, record the outcome
  privately before deciding whether a minimal long-lived extension is truly
  necessary.

## Working cadence

1. Fetch upstream at the start of every work session.
2. Read recent upstream commits and active release branches in the affected
   area before coding.
3. Select one small, independently useful issue.
4. Branch from current `upstream/main`; add code, synthetic evidence, and tests.
5. Open the upstream PR early and respond to review on the same branch.
6. Do not begin dependent product work until the maintainer resolves the PR.
7. When merged, synchronize both fork and local `main`, then choose the next
   issue from the new upstream state.
