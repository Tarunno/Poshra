import { ProductGridSkeleton } from "@/components/product-grid";
import { Skeleton } from "@/components/ui/skeleton";

export default function ShopLoading() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-10 w-2/3 max-w-md" />
      <Skeleton className="h-11 w-full rounded-full" />
      <div className="grid gap-8 lg:grid-cols-[17rem_1fr]">
        <Skeleton className="rounded-panel h-[28rem]" />
        <ProductGridSkeleton />
      </div>
    </div>
  );
}
