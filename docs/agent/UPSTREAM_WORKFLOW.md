# Upstream workflow

## Remotes

- `origin`: `Lazyjimpressions/SlowBooks-Pro-2026`
- `upstream`: `VonHoltenCodes/SlowBooks-Pro-2026`

Local `main` is the reviewed integration branch for the public fork. It remains
based on upstream and may be ahead while fork PRs await focused upstream
submission; it is not expected to be byte-for-byte identical to upstream.
Before new work, inspect both directions of divergence and integrate any new
upstream commits deliberately:

```bash
git fetch upstream --prune
git switch main
git rev-list --left-right --count upstream/main...main
git merge --no-edit upstream/main
git push origin main
git switch -c feat/descriptive-name
```

Never develop directly on `main`. Rebase a feature branch on the refreshed fork
`main` before final review. Never reset fork commits merely to make the branch
match upstream; reconcile them through reviewed merges or focused upstream PRs.

## Pull requests

- Open a draft PR against the fork while work is active.
- Keep generic fixes isolated from private AI policy.
- Reference the issue and state database, security, and compatibility impact.
- After local review, open a focused upstream PR containing only material the
  upstream project can adopt without our private repository.
- If upstream accepts the change, drop the corresponding fork-only patch.
- If upstream diverges, record the decision and keep the patch narrowly scoped.
