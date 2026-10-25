"use client";

/** "Download as PDF": opens the browser's print dialog, where "Save as PDF" is one click. */
export default function PrintButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className={className ?? "min-h-11 rounded-[10px] bg-white px-4 py-2.5 text-sm font-bold text-ink"}
    >
      Download as PDF
    </button>
  );
}
