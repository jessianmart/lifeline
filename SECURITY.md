# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private reporting:
**repo → Security → "Report a vulnerability"** (Private Vulnerability Reporting). We'll
acknowledge within a few days and coordinate a fix and disclosure.

Areas most worth scrutiny are the **cloud mode**: the Supabase adapters (`lifeline/cloud.py`),
the RLS policies (`lifeline/schema.sql`), and the remote MCP server / OAuth Resource Server
(`lifeline/mcp_server.py`).

## Threat model (by design)

- **Local mode** trusts the local filesystem (the `.lifeline/` store). There is **no signing** —
  a local actor with write access can forge entries. This is intentional (local = trusted).
- **Cloud mode**: AI writes are **HITL** (they enter as proposals; a human approves); **RLS**
  isolates tenants (`owner = auth.uid()`); the ledger table is **append-only at the database**.
  Never commit secrets — credentials live in a `.env` (gitignored).

## Supported versions

The latest `lifeline-context` published on PyPI. This is **alpha** software (pre-1.0).
