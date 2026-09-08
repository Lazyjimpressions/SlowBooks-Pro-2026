# ADR 0002: Separate import, proposal, approval, and posting

**Status:** Accepted  
**Date:** 2026-09-07

## Decision

An imported bank row is statement evidence, not a journal entry. Deterministic
rules may classify known patterns; AI may propose intent and mappings; a
guarded domain service must validate and post the balanced entry only after the
configured approval policy permits it.

Posting must atomically link the source row to exactly one journal transaction
and be safe to retry.

## Consequences

- Financial reports remain based on validated double-entry data.
- AI can automate routine work without receiving unconstrained ledger access.
- Suggestions can be corrected without rewriting posted history.
- The system needs explicit proposal, approval, posting, transfer, and reversal
  APIs before high-autonomy operation.
