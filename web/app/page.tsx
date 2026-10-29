import Link from "next/link";
import Header from "@/components/Header";
import HeroImage from "@/components/HeroImage";

export default function Landing() {
  return (
    <>
      <Header />
      <main className="mx-auto flex max-w-[960px] flex-col gap-8 px-5 py-10 md:px-8 md:py-16">
        <HeroImage />
        <div className="flex max-w-[720px] flex-col items-start gap-6">
          <h1 className="m-0 text-[32px] font-extrabold leading-[1.15] tracking-tight md:text-5xl">
            Honest EV advice for first-time buyers
          </h1>
          <p className="m-0 text-base text-muted md:text-lg">
            No car knowledge needed. Tell us about your life, answer a few easy questions, and get a shortlist you can trust.
          </p>
          <Link
            href="/start"
            className="btn btn-primary"
          >
            Start
            <span aria-hidden="true" className="btn-arrow">→</span>
          </Link>
          <p className="m-0 text-[13px] text-muted">
            AutoBrain is independent of Tata and Mahindra. Prices are ex-showroom, as of the data release date.
          </p>
        </div>
      </main>
    </>
  );
}
