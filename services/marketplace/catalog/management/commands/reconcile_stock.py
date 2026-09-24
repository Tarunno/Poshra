"""Repair the catalog's stock from the ledger that owns it.

`sync_stock` pushes this service's levels *to* inventory, which is the right
direction when the catalog is the source — an artisan setting how many they
have. This is the opposite direction, and it is for the case where the copy
here is the one that is wrong.

It exists because for a while nothing decremented the catalog's count when a
piece sold: only the ledger moved, so a product page kept advertising stock
that was gone. Sales recorded from now on take the piece off the listing as
they arrive (sales/events.py), but the drift already in the table has to be
read back from inventory, because no amount of arithmetic over past sales can
recover it: an artisan who re-saved a listing mid-history typed an absolute
number that overwrote everything before it.

    python manage.py reconcile_stock --dry-run   # show what would change
    python manage.py reconcile_stock             # write it

Safe to run repeatedly, and safe to interrupt: each batch is its own
transaction, and a second run over an already-corrected listing is a no-op.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.inventory_client import InventoryUnavailable, channel, on_hand
from catalog.models import Product


class Command(BaseCommand):
    help = "Set each listing's stock to the quantity the inventory ledger holds."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the drift without writing anything.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="How many skus to ask for per GetStock call (default 100).",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1")

        # Ordered so the batches are stable between runs, which makes an
        # interrupted run easy to reason about.
        ids = list(Product.objects.order_by("id").values_list("id", flat=True))
        if not ids:
            self.stdout.write("no listings")
            return

        corrected = unknown = 0
        try:
            with channel() as stub:
                for start in range(0, len(ids), batch_size):
                    batch = ids[start : start + batch_size]
                    ledger = on_hand(stub, [str(pk) for pk in batch])
                    corrected_here, unknown_here = self._apply(batch, ledger, dry_run=dry_run)
                    corrected += corrected_here
                    unknown += unknown_here
        except InventoryUnavailable as error:
            # Half a repair is worse than none: stop and say so rather than
            # leaving the table in a state nobody can describe.
            raise CommandError(str(error)) from error

        verb = "would correct" if dry_run else "corrected"
        self.stdout.write(f"{len(ids)} listings checked, {verb} {corrected}")
        if unknown:
            # Almost always a listing created while the broker was down, whose
            # level was never announced. `sync_stock` is the fix for those, and
            # it pushes rather than pulls, so this command leaves them alone.
            self.stdout.write(
                self.style.WARNING(
                    f"{unknown} not in the ledger — left as they are; run sync_stock for those"
                )
            )

    @transaction.atomic
    def _apply(self, batch: list, ledger: dict[str, int], *, dry_run: bool) -> tuple[int, int]:
        """One batch, one transaction. Returns (corrected, missing from the ledger)."""
        corrected = unknown = 0
        products = Product.objects.select_for_update().filter(id__in=batch).only("id", "stock")

        for product in products:
            truth = ledger.get(str(product.id))
            if truth is None:
                unknown += 1
                continue
            if truth == product.stock:
                continue

            self.stdout.write(f"{product.id}  {product.stock} -> {truth}")
            corrected += 1
            if not dry_run:
                # update(), not save(): a post_save here would announce this
                # number straight back to the service it was just read from.
                Product.objects.filter(pk=product.pk).update(stock=truth)

        return corrected, unknown
