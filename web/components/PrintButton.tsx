"use client";

/** "Download as PDF": opens the browser's print dialog, where "Save as PDF" is one click. */
export default function PrintButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className={className ?? "btn btn-light !min-h-11 !rounded-[10px] !px-4 !py-2.5 !text-sm !font-bold"}
    >
      Download as PDF
    </button>
  );
}
