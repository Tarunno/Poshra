import { CraftPatch } from "@/components/craft-patch";
import {
  KanthaRule,
  MakersHand,
  NeedleThread,
  Weave,
} from "@/components/motifs";

const promises = [
  { icon: Weave, text: "Handloom and handmade only — no factory reprints." },
  {
    icon: NeedleThread,
    text: "Listings written from your photo and a Bangla voice note.",
  },
  { icon: MakersHand, text: "Payouts reach the person who made the work." },
];

/**
 * Shared shell for sign in and sign up: a brand panel beside the form.
 * The panel is hidden on small screens, where the form is all that matters.
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="grid items-stretch gap-6 lg:grid-cols-[1fr_minmax(0,26rem)]">
      <section className="bg-tint-mint rounded-panel stitched relative hidden p-9 lg:flex lg:flex-col lg:justify-between">
        <div>
          <p className="font-bangla text-ink-mint text-lg">পসরা</p>
          <h2 className="mt-3 max-w-sm text-3xl leading-tight font-extrabold tracking-tight text-balance">
            A marketplace stitched around the maker.
          </h2>

          <ul className="mt-7 space-y-4">
            {promises.map(({ icon: Icon, text }) => (
              <li
                key={text}
                className="flex items-start gap-3 text-sm opacity-80"
              >
                <Icon className="mt-0.5 size-5 shrink-0" />
                <span className="max-w-xs">{text}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-8">
          <KanthaRule className="h-4 w-full opacity-50" />
          <CraftPatch className="mx-auto mt-6 w-56" />
        </div>
      </section>

      <div className="flex items-center">{children}</div>
    </div>
  );
}
