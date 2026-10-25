import Link from "next/link";
import Header from "@/components/Header";

export default function Landing() {
  return (
    <>
      <Header />
      <main className="mx-auto flex max-w-[720px] flex-col items-start gap-8 px-5 py-16 md:px-8 md:py-24">
        <h1 className="m-0 text-[32px] font-extrabold leading-[1.15] tracking-tight md:text-5xl">
          Honest EV advice for Mahindra and Tata buyers
        </h1>
        <Link
          href="/start"
          className="inline-flex min-h-12 items-center justify-center rounded-xl bg-brand px-8 py-3.5 text-base font-extrabold !text-white no-underline hover:bg-brand-dark"
        >
          Start
        </Link>
        <p className="m-0 text-[13px] text-muted">
          AutoBrain is independent of Tata and Mahindra. Prices are ex-showroom, as of the data release date.
        </p>
      </main>
    </>
  );
}
