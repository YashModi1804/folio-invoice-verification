import { useRef, useState } from "react";
import {
  ArrowRight,
  CheckCheck,
  FileText,
  ScanLine,
  Upload,
  TriangleAlert,
} from "lucide-react";
import { request } from "./api";
import type { Job } from "./types";

export default function Intake({
  token,
  onCreated,
  onError,
  provider,
  fallback,
  maxPages,
  maxFileMb,
  publicPreview,
}: {
  token: string;
  onCreated: (job: Job) => void;
  onError: (message: string) => void;
  provider: string;
  fallback: boolean;
  maxPages: number;
  maxFileMb: number;
  publicPreview: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  async function upload(file?: File) {
    if (!file || busy) return;
    if (file.size > maxFileMb * 1024 * 1024) {
      onError(`Please choose a document smaller than ${maxFileMb} MB.`);
      return;
    }
    setBusy(true);
    try {
      const data = new FormData();
      data.append("file", file);
      onCreated(
        await request<Job>("/documents", token, {
          method: "POST",
          body: data,
          headers: { "Idempotency-Key": crypto.randomUUID() },
        }),
      );
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  async function sample(kind: string) {
    setBusy(true);
    try {
      onCreated(
        await request<Job>(`/samples/${kind}`, token, { method: "POST" }),
      );
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="intake">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>A document in. A decision out.</h2>
            <p>Extract the details. Verify the numbers. Keep the evidence.</p>
          </div>
        </div>
        {publicPreview ? (
          <div className="dropzone preview-dropzone">
            <div className="upload-icon"><ScanLine size={20} /></div>
            <h3>Start with a synthetic invoice</h3>
            <p>Choose a scenario below to inspect evidence, math checks, and review routing.</p>
            <small>Private document uploads are available in the hosted API installation.</small>
          </div>
        ) : (
          <div
            className={`dropzone ${dragging ? "drag" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void upload(e.dataTransfer.files[0]);
          }}
        >
          <div className="upload-icon">
            <Upload size={20} />
          </div>
          <h3>Drop an invoice here</h3>
          <p>PDF, PNG, JPG or WEBP · Up to {maxFileMb} MB / {maxPages} pages</p>
          <button disabled={busy} onClick={() => input.current?.click()}>
            <Upload size={14} />
            {busy ? "Adding document…" : "Choose a document"}
          </button>
          <input
            ref={input}
            type="file"
            hidden
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            onChange={(e) => void upload(e.target.files?.[0])}
          />
          </div>
        )}
        <p
          style={{
            padding: "0 22px 18px",
            fontSize: 10,
            color: "var(--muted)",
          }}
        >
          {publicPreview
            ? "Public preview: precomputed synthetic extraction. No inference, uploads, or server persistence."
            : provider === "fixture"
            ? "Sample mode is active. Custom documents need a configured live provider."
            : provider === "ollama"
              ? "Local AI active. Documents stay on this machine; no cloud API call."
              : provider === "groq"
                ? "Groq capacity is reserved before extraction. Longer invoices are planned page by page and held for review if coverage is incomplete."
              : fallback
                ? `${provider === "groq" ? "Groq" : "Gemini"} processes uploads. If unavailable, local AI is attempted once and clearly labeled.`
                : "Live provider active. Documents are sent to the configured model."}
        </p>
      </section>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>See the guardrails at work</h2>
            <p>Synthetic fixtures · No model call · Real validation workflow</p>
          </div>
          <ScanLine size={19} className="muted" />
        </div>
        <div className="samples">
          {[
            {
              id: "clean",
              title: "The clean invoice",
              copy: "Complete fields. Numbers that reconcile.",
              icon: CheckCheck,
            },
            {
              id: "variance",
              title: "The $50 discrepancy",
              copy: "A printed total that does not add up.",
              icon: TriangleAlert,
            },
            {
              id: "uncertain",
              title: "The uncertain date",
              copy: "Correct math. One field still needs a human.",
              icon: FileText,
            },
            {
              id: "helixpoint",
              title: "The enterprise invoice",
              copy: "18 lines across two pages. A $125 total error is held for review.",
              icon: TriangleAlert,
            },
          ].map((item) => (
            <button
              className="sample"
              key={item.id}
              disabled={busy}
              onClick={() => void sample(item.id)}
            >
              <span className="sample-icon">
                <item.icon size={18} />
              </span>
              <span className="sample-copy">
                <strong>{item.title}</strong>
                <small>{item.copy}</small>
              </span>
              <ArrowRight size={15} />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
