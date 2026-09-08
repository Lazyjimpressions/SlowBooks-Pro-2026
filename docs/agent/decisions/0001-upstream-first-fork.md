# ADR 0001: Maintain an upstream-first public fork

**Status:** Accepted  
**Date:** 2026-09-07

## Decision

Keep `Lazyjimpressions/SlowBooks-Pro-2026` as a public, upstream-compatible
fork. Keep local `main` aligned with `upstream/main`, develop on feature
branches, and propose generic corrections upstream as focused pull requests.

Store private business policy and proprietary AI operations in the separate
private `Lazyjimpressions/slowbooks-ai-ops` repository.

## Consequences

- Upstream updates remain reviewable and inexpensive to integrate.
- Generic fixes can become part of official releases.
- Private mappings and business data never enter the public fork.
- Fork-only patches must remain small and documented when upstream declines
  them.
