import Link from "next/link";
import Header from "@/components/Header";
import OptionCard from "@/components/OptionCard";

const SearchIcon = (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);
const CompareIcon = (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 4v16M17 4v16M3 8l4-4 4 4M13 16l4 4 4-4" />
  </svg>
);

/** Second question, for electric cars: find one, or compare cars the buyer has already shortlisted. */
export default function EvStartPage() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-[720px] px-5 pb-20 pt-8 md:px-8 md:pt-12">
        <Link href="/start" className="mb-4 inline-block text-[15px] font-bold">
          &larr; Back
        </Link>
        <h1 className="m-0 mb-2 text-[28px] font-extrabold tracking-tight md:text-4xl">What would you like to do?</h1>
        <p className="m-0 mb-8 text-base text-muted">No car knowledge needed for either one.</p>

        <div className="grid gap-4 sm:grid-cols-2">
          <OptionCard
            title="Find the right EV for me"
            description="Tell us about your life and answer a few easy questions. We build a shortlist you can trust."
            icon={SearchIcon}
            href="/find"
          />
          <OptionCard
            title="Compare EVs I have shortlisted"
            description="Pick two or three cars and see them side by side, with where each one leads."
            icon={CompareIcon}
            href="/compare"
          />
        </div>
      </main>
    </>
  );
}
