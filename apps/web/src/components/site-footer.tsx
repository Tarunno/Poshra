import { PoshraMark } from "@/components/logo";
import {
  Hoop,
  KanthaRule,
  MakersHand,
  NeedleThread,
  PottersWheel,
  Weave,
  Spool,
} from "@/components/motifs";

const crafts = [
  { icon: Weave, label: "Jamdani weaving" },
  { icon: NeedleThread, label: "Nakshi kantha" },
  { icon: PottersWheel, label: "Terracotta" },
  { icon: Hoop, label: "Embroidery" },
  { icon: Spool, label: "Handloom cotton" },
  { icon: MakersHand, label: "Made by hand" },
];

export function SiteFooter() {
  return (
    <footer className="mx-auto w-full max-w-6xl px-4 pb-14">
      <KanthaRule className="h-4 w-full opacity-70" />

      <div className="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-5">
        {crafts.map(({ icon: Icon, label }) => (
          <span
            key={label}
            className="flex items-center gap-2 text-sm opacity-70"
          >
            <Icon className="size-5" />
            {label}
          </span>
        ))}
      </div>

      <p className="mt-8 flex items-center justify-center gap-2 text-center text-sm opacity-60">
        <PoshraMark className="size-5" />
        <span className="font-bangla">পসরা</span> · Poshra — handmade in
        Bangladesh, sold worldwide.
      </p>
    </footer>
  );
}
