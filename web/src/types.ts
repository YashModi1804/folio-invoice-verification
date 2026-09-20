export type Field = {
  value: string | null;
  confidence: number;
  evidence: { page_number: number; text: string }[];
};
export type Invoice = {
  vendor_name: Field;
  vendor_tax_id: Field;
  invoice_number: Field;
  invoice_date: Field;
  currency: Field;
  subtotal: Field;
  tax_amount: Field;
  shipping_amount: Field;
  discount_amount: Field;
  total_amount: Field;
  line_items: {
    description: string;
    quantity: string | null;
    unit_price: string | null;
    line_total: string | null;
  }[];
  ambiguous_document: boolean;
  tax_inclusive: boolean;
};
export type Check = {
  code: string;
  state: "PASS" | "FAIL" | "NOT_APPLICABLE";
  expected: string | null;
  observed: string | null;
  variance: string | null;
};
export type Telemetry = {
  fallback_reason?: string;
  provider: string;
  model: string;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: string | null;
  prompt_version: string;
  schema_version: string;
  pricing_version: string | null;
};
export type Job = {
  summary: {
    vendor_name: string | null;
    invoice_number: string | null;
    total_amount: string | null;
    currency: string | null;
  } | null;
  job_id: string;
  correlation_id: string;
  filename: string;
  status: string;
  page_count: number;
  mode: string;
  requested_provider: string;
  created_at: string;
  not_before: string | null;
  error: string | null;
  result: {
    invoice: Invoice;
    checks: Check[];
    route_reasons: string[];
    telemetry: Telemetry;
    math_validated: boolean | null;
  } | null;
};
export type Audit = {
  event: string;
  actor: string;
  created_at: string;
  details: {
    note?: string;
    changes?: Record<string, { before: unknown; after: unknown }>;
  };
};
export type Decision = {
  invoice: Invoice;
  checks: Check[];
  action: string;
  note: string;
  actor: string;
} | null;
export const labels: Record<string, string> = {
  QUEUED: "Queued",
  PROCESSING: "Processing",
  AUTO_APPROVED: "Verified",
  REQUIRES_HUMAN_REVIEW: "Needs review",
  HUMAN_APPROVED: "Human approved",
  REJECTED: "Rejected",
  FAILED: "Processing failed",
};
export const humanize = (value: string) =>
  value.replaceAll("_", " ").toLowerCase();
