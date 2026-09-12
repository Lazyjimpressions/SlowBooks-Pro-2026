# ADR 0001: Maintain an upstream-first public fork

**Status:** Accepted  
**Date:** 2026-09-07

## Decision

Keep `Lazyjimpressions/SlowBooks-Pro-2026` as a public, upstream-compatible
fork. Keep local `main` based on and deliberately reconciled with
`upstream/main`; it may remain ahead with reviewed fork commits. Develop on
feature branches and propose generic corrections upstream as focused pull
requests.

Store private business policy and proprietary AI operations in the separate
private `Lazyjimpressions/slowbooks-ai-ops` repository.

## Consequences

- Upstream updates remain reviewable and inexpensive to integrate.
- Generic fixes can become part of official releases.
- Private mappings and business data never enter the public fork.
- Fork-only patches must remain small and documented when upstream declines
  them.

## Clarification — September 9, 2026

"Upstream-first" means continuously reviewing and integrating upstream, not
resetting the fork integration branch to a byte-identical mirror. Fork commits
remain on `main` until upstream accepts them or a later reviewed decision
replaces them.

## Superseded — September 12, 2026

ADR 0005 replaces the ahead-of-upstream integration-branch model with a clean
mirror plus focused upstream contribution branches. The completed fork history
remains preserved by archive tag rather than carried on active `main`.
