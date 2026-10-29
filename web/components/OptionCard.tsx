import Link from "next/link";
import type { ReactNode } from "react";

const BASE =
  "choice-card group flex w-full flex-col gap-2 rounded-[18px] border border-line bg-white p-5 text-left md:p-6";

/** A big tappable choice for the first screens: an icon, a title, one line of help and an optional badge. */
export default function OptionCard({
  title, description, icon, badge, href, onClick, disabled = false, selected = false,
}: {
  title: string;
  description: string;
  icon: ReactNode;
  badge?: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  selected?: boolean;
}) {
  const inner = (
    <>
      <span className="flex items-center justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky text-brand" aria-hidden="true">
          {icon}
        </span>
        {badge ? <span className="rounded-full bg-chip px-3 py-1 text-[12px] font-bold text-muted">{badge}</span> : null}
      </span>
      <span className="text-xl font-extrabold text-ink">{title}</span>
      <span className="text-[15px] text-muted">{description}</span>
      {href && !disabled ? (
        <span className="mt-1 text-[15px] font-bold text-brand">
          Choose <span aria-hidden="true" className="btn-arrow">&rarr;</span>
        </span>
      ) : null}
    </>
  );
  const ring = selected ? " !border-brand !bg-sky" : "";
  if (href && !disabled) {
    return (
      <Link href={href} className={`${BASE}${ring} !text-ink no-underline`}>
        {inner}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} disabled={disabled && !onClick} aria-pressed={onClick ? selected : undefined} className={`${BASE}${ring}`}>
      {inner}
    </button>
  );
}
