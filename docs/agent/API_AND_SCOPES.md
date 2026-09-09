# API and agent scopes

SlowBooks exposes its OpenAPI schema at runtime. Treat the running schema as
authoritative for endpoint details and this file as operating policy.

## Token roles

- `readonly`: reporting and inspection only.
- `bookkeeper`: ordinary accounting reads and writes.
- `admin`: broad read/write administration, with protected identity and
  closing-period operations still restricted for API-token principals.

Use the least-privileged token that can complete the task. Never place a token
in source, documentation, shell history examples, issue text, or test data.

```bash
export SLOWBOOKS_API_TOKEN='set outside the repository'
curl -H "Authorization: Bearer $SLOWBOOKS_API_TOKEN" \
  http://127.0.0.1:3001/api/system
```

## AI write policy

- Read and propose before writing.
- Use purpose-built posting endpoints when available.
- Include an idempotency key or source bank-row ID.
- Re-read affected records and accounting invariants after every write.
- Do not bypass a protected operation through direct database access.
- Never loosen a closing date or set its override password through an agent.

## Banking rule boundary

- `GET /api/bank-rules/proposal-draft/{proposal_id}` is read-only and offers a
  narrow rule after a direct income or expense proposal is approved.
- `POST /api/bank-rules` creates that rule only after a separate user or agent
  decision with bookkeeper write authority.
- `POST /api/bank-rules/apply` may create `proposed` review records and legacy
  category hints. It never approves a proposal or writes a journal entry.
- Posting still requires `POST /api/banking/proposals/{id}/post` after the
  proposal reaches `approved` through the configured review policy.
