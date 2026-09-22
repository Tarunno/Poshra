import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="bg-tint-rose rounded-panel stitched mx-auto max-w-xl p-10 text-center">
      <p className="font-bangla text-ink-rose text-sm">পসরা</p>
      <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
        This stall is empty.
      </h1>
      <p className="mt-3 text-sm opacity-75">
        The page you asked for does not exist, or the piece has been taken down.
      </p>
      <Button asChild className="mt-7 rounded-full px-6">
        <Link href="/shop">Browse the crafts</Link>
      </Button>
    </div>
  );
}
