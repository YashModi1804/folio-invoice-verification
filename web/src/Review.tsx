import { useState } from "react";
import { Check, X } from "lucide-react";
import { request } from "./api";
import type { Invoice, Job } from "./types";
import { PUBLIC_PREVIEW } from "./preview";

export default function Review({
  job,
  token,
  draft,
  onDone,
  onError,
}: {
  job: Job;
  token: string;
  draft: Invoice | null;
  onDone: () => void;
  onError: (message: string) => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  async function decide(action: "approve" | "reject") {
    setBusy(true);
    try {
      await request(`/review-tasks/${job.job_id}/decision`, token, {
        method: "POST",
        body: JSON.stringify({ action, note, corrected_invoice: draft }),
      });
      onDone();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel section-gap">
      <div className="panel-head">
        <div>
          <h2>{PUBLIC_PREVIEW ? "Try a review decision" : "Your decision, on record"}</h2>
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
          onChange={(e) => setNote(e.target.value)}
          placeholder="What did you check or correct?"
        />
        <div className="toolbar">
          <button
            disabled={busy || note.trim().length < 3}
            onClick={() => void decide("reject")}
          >
            <X size={14} />
            Reject
          </button>
          <button
            className="primary"
            disabled={busy || note.trim().length < 3}
            onClick={() => void decide("approve")}
          >
            <Check size={14} />
            {busy ? "Saving…" : "Approve record"}
          </button>
        </div>
      </div>
    </section>
  );
}
