# ADR 0005: Use a clean mirror and upstream contribution branches

**Status:** Accepted  
**Date:** 2026-09-12

## Context

The original fork accumulated an AI banking prototype while upstream changed
rapidly and replaced the underlying banking architecture. Keeping a second
application line makes every upstream release a merge project and encourages
work against assumptions that may already have changed.

PR #130 demonstrated a better collaboration loop: isolate one generally useful
change, provide real-shape synthetic evidence, let the maintainer integrate it
into the active release branch, and consume the result from upstream. The
maintainer preserved both LazyJimpressions commits and authorship on the
v2.13.0 release branch.

## Decision

- After a separately reviewed one-time realignment, keep public-fork `main`
  byte-for-byte aligned with upstream `main`.
- Preserve the completed v2.9.4 prototype and its documentation through archive
  tags and branches; do not merge that application history forward.
- Create every public product change from current `upstream/main` on a focused
  branch in the LazyJimpressions fork.
- Open small upstream pull requests early. Do not stack dependent features or
  build a parallel roadmap ahead of unresolved upstream work.
- Allow the upstream maintainer to merge, rebase, or cherry-pick the commits
  into their release process. Once accepted, consume the official result and
  remove the duplicate fork branch.
- Keep private business mappings, model policy, deployment notes, and canonical
  cross-agent operating knowledge in `slowbooks-ai-ops`.
- Treat a long-lived fork-only code delta as an exception requiring a new ADR.

## Consequences

- Upstream fixes remain cheap to consume and our work is tested against the
  architecture that will actually ship.
- We contribute to the shared product rather than maintaining a competing one.
- `origin/main` cannot also serve as our private integration branch.
- Experimental AI work must stay in short-lived branches or the private
  orchestration repository until it can be proposed as a focused upstream
  capability.
- Direct access to upstream `main` is unnecessary; accepted PRs are the merge
  path and preserve contribution history.
- Database reconstruction remains separately gated on a stable upstream release
  containing the Bank of America importer.

## Supersedes

This ADR supersedes ADR 0001's September 9 clarification that fork `main` may
remain permanently ahead of upstream. ADR 0004's accounting and fresh-database
decisions remain in force.
