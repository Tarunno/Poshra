import { ProductGridSkeleton } from "@/components/product-grid";
import { Skeleton } from "@/components/ui/skeleton";

export default function ShopLoading() {
  return (
    <div className="space-y-9">
      <Skeleton className="h-10 w-2/3 max-w-md" />
      <Skeleton className="h-11 w-full rounded-full" />
      <ProductGridSkeleton />
    </div>
  );
}
