import Link from "next/link";
import type { ReactNode } from "react";

/** Logo bar from the mockups. `children` is the nav (hidden when printing). */
export default function Header({ children }: { children?: ReactNode }) {
  return (
    <header className="bg-ink text-white">
      <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-3 px-5 py-4 md:px-8 md:py-[18px]">
        <Link href="/" className="logo flex items-center gap-2.5 !text-white no-underline">
          <span className="logo-mark flex h-[30px] w-[30px] items-center justify-center rounded-lg bg-brand md:h-9 md:w-9 md:rounded-[10px]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
            </svg>
          </span>
          <span className="text-lg font-extrabold tracking-tight md:text-xl">AutoBrain</span>
        </Link>
        <span className="hidden border-l border-[#33444F] pl-3 text-[13px] text-[#B9C6CF] lg:block">
          Honest EV advice. No dealer pays us to say this.
        </span>
        {children ? <nav className="flex flex-wrap gap-2.5 print:hidden">{children}</nav> : null}
      </div>
    </header>
  );
}
