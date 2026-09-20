# ERP integration contract

Folio is deliberately ERP-neutral. It produces one stable JSON export that a small connector
can map to an ERP's supplier, bill, purchase-order, or expense endpoints.

## Safe handoff flow

1. Poll `GET /api/v1/jobs` or receive an application event in a future deployment.
2. Fetch `GET /api/v1/jobs/{job_id}/erp-export` only after Folio reports an approved status.
3. Use `idempotency_key` as the destination's external idempotency value.
4. Create the ERP record using the exported supplier, invoice, amount, and line-item fields.
5. Call `POST /api/v1/jobs/{job_id}/erp-export/acknowledgements` with the destination system
   name and external record ID. Repeating the same acknowledgement is idempotent.

Folio never exports review-required, rejected, or failed records. It does not make outbound
requests by default; clients keep control over credentials, field mapping, retry policy, and
the target system of record.

## Example acknowledgement

```json
{
  "system": "Odoo",
  "external_record_id": "BILL-401"
}
```

The acknowledgement appears in Folio's immutable audit trail, alongside the originating job,
verification checks, and any reviewer decision.
