import { useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { request } from "./api";
import type { Invoice, Job } from "./types";
import { PUBLIC_PREVIEW } from "./preview";

export default function Review({
  job,
  token,
  draft,
  onDone,
}: {
  job: Job;
  token: string;
  draft: Invoice | null;
  onDone: () => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [savingAction, setSavingAction] = useState<"approve" | "reject" | null>(
    null,
  );
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  async function decide(action: "approve" | "reject") {
    if (submitting.current || saved || note.trim().length < 3) return;
    submitting.current = true;
    setBusy(true);
    setSavingAction(action);
    setError("");
    try {
      await request(`/review-tasks/${job.job_id}/decision`, token, {
        method: "POST",
        body: JSON.stringify({
          action,
          note: note.trim(),
          corrected_invoice: draft,
        }),
      });
      setSaved(true);
      await onDone();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="panel section-gap" aria-busy={busy}>
      <div className="panel-head">
        <div>
          <h2>
            {PUBLIC_PREVIEW
              ? "Try a review decision"
              : "Your decision, on record"}
          </h2>
          <p>
            {PUBLIC_PREVIEW
              ? "This sample decision stays in this browser tab and is not saved to a server."
              : "Approval accepts responsibility for any remaining discrepancies."}
          </p>
        </div>
      </div>
      <div className="review-form">
        <label htmlFor="review-note">
          Review note <span className="muted">· required</span>
        </label>
        <textarea
          id="review-note"
          value={note}
          maxLength={1000}
          minLength={3}
          required
          disabled={busy || saved}
          aria-describedby="review-note-help"
          onChange={(e) => setNote(e.target.value)}
          placeholder="What did you check or correct?"
        />
        <small id="review-note-help">
          Add at least 3 characters explaining your decision.
        </small>
        {error && (
          <p className="review-error" role="alert">
            {error}
          </p>
        )}
        {saved && <p role="status">Decision saved. Refreshing the record…</p>}
        <div className="toolbar">
          <button
            disabled={busy || saved || note.trim().length < 3}
            onClick={() => void decide("reject")}
          >
            <X size={14} />
            {busy && savingAction === "reject" ? "Saving…" : "Reject"}
          </button>
          <button
            className="primary"
            disabled={busy || saved || note.trim().length < 3}
            onClick={() => void decide("approve")}
          >
            <Check size={14} />
            {busy && savingAction === "approve" ? "Saving…" : "Approve record"}
          </button>
        </div>
      </div>
    </section>
  );
}
