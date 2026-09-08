# Upstream workflow

## Remotes

- `origin`: `Lazyjimpressions/SlowBooks-Pro-2026`
- `upstream`: `VonHoltenCodes/SlowBooks-Pro-2026`

Local `main` is a clean mirror of `upstream/main`:

```bash
git fetch upstream --prune
git switch main
git merge --ff-only upstream/main
git push origin main
git switch -c feat/descriptive-name
```

Never develop directly on `main`. Rebase a feature branch on the refreshed
upstream baseline before final review.

## Pull requests

- Open a draft PR against the fork while work is active.
- Keep generic fixes isolated from private AI policy.
- Reference the issue and state database, security, and compatibility impact.
- After local review, open a focused upstream PR containing only material the
  upstream project can adopt without our private repository.
- If upstream accepts the change, drop the corresponding fork-only patch.
- If upstream diverges, record the decision and keep the patch narrowly scoped.
