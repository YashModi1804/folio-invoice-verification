import { ArrowUpRight } from "lucide-react";

export default function SamplePreviewFallback({
  publicPreview,
}: {
  publicPreview: boolean;
}) {
  if (publicPreview) return null;
  return (
    <div className="sample-fallback">
      <a
        href="https://yashmodi1804.github.io/folio-invoice-verification/"
        target="_blank"
        rel="noopener noreferrer"
      >
        Explore sample preview <ArrowUpRight size={14} aria-hidden="true" />
      </a>
      <small>
        Synthetic examples. No uploads or server storage. Opens in a new tab.
      </small>
    </div>
  );
}
