import { existsSync } from "node:fs";
import path from "node:path";
import HeroCar from "./HeroCar";

/** Put a licensed photo of an EV (no visible brand) at web/public/hero-ev.jpg and the landing page shows it with a slow zoom. */
const PHOTO = "hero-ev.jpg";

export default function HeroImage() {
  if (!existsSync(path.join(process.cwd(), "public", PHOTO))) return <HeroCar />;
  return (
    <div className="hero-photo relative aspect-[16/9] w-full overflow-hidden rounded-[22px] border border-line bg-ink md:aspect-[21/9]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/${PHOTO}`} alt="An electric car" className="hero-photo-img h-full w-full object-cover" />
    </div>
  );
}
