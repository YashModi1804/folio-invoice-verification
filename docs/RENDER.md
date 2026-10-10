# Render live demo

Folio's Render demo uses one free Docker web service and one free PostgreSQL instance
in the same region. The web process runs FastAPI and an embedded database-backed
worker. Source documents are stored in a private PostgreSQL table instead of the
web service's ephemeral filesystem. The Docker startup command applies Alembic
migrations before serving traffic.

This is a time-limited sales demo, not client production infrastructure. Render's
free web service sleeps when idle, so the first visit can be slow. The free database
has 1 GB of storage and expires 30 days after creation; it has no durable backup.
The instance created October 7, 2026 is scheduled to expire November 6, 2026.
Upgrade or export before then if records must be kept. The worker removes source
documents after seven days while preserving extraction and review audit records.

## Web service configuration

Deploy the public GitHub repository as a Docker web service on the free plan in
Oregon, matching the database. The following environment variables are required:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | The database's **internal** connection URL, kept secret in Render |
| `SOURCE_STORAGE` | `database` |
| `EMBEDDED_WORKER` | `true` |
| `PUBLIC_DEMO` | `true` |
| `PROVIDER` | `groq` for live extraction |
| `GROQ_MODEL` | A currently available vision-capable model validated with the provider |
| `GROQ_API_KEY` | Secret, entered directly in Render |
| `OPERATOR_TOKEN` | Unique, randomly generated secret of at least 32 characters |
| `LOCAL_FALLBACK_ENABLED` | `false` (Ollama is not hosted on the free service) |
| `MAX_FILE_BYTES` | `10485760` (10 MB) |

`GUEST_ENABLED=true` is an optional, separately approved public-trial switch.
It auto-creates private guest workspaces and leaves the operator token
private. Before enabling it, deploy the guest-workspace migration, confirm the
sample-only guest flow, and test two browsers for cross-workspace isolation.
The default guest caps are two live uploads per guest per rolling day, 20 site-wide per rolling day,
ten pending guest jobs, 5 MB and three pages per file. Increase only after
checking Groq's actual organization limits. Guests see four labeled synthetic
samples without inference, including HelixPoint. Guest access has no application expiry.
Each guest upload and its history become inaccessible after two hours; physical cleanup
runs while the service is awake. The free database still has its own expiry.
Do not claim deletion at the exact minute or across third-party systems.

Never add secrets to Git, `render.yaml`, screenshots, or Loom footage. The web
service refuses startup with the default local token or a missing live-provider key.
Use Render's internal database URL, and block public inbound database traffic.
`/health/ready` checks the database and worker; `/health/live` is liveness only.

## Acceptance check

1. Confirm the Render deploy is live and `/health/ready` returns HTTP 200 with all
   three components ready.
2. Sign in with the private operator token. Verify the temporary-demo banner.
3. Process a synthetic sample; confirm a terminal result, source-page evidence,
   verification ledger, and review history.
4. Upload one non-sensitive PDF and confirm the trace says `groq`, not `fixture`.
5. Reload after a web-service restart; records and retained source pages should
   still be available. Never use real customer invoices in this temporary demo.

The PostgreSQL storage and embedded worker are deployment adapters; for client
production, use a durable paid database, object storage, separate worker, backups,
tenant-aware access control, and a provider data-processing agreement.
