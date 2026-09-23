"""The artisan sales read model.

Checkout owns orders. This is a different question asked of the same facts —
"what did *I* sell?" — and it belongs to the service that knows who made each
piece. It is built from the order events rather than queried from checkout,
because services do not read each other's databases.

The consequence is eventual consistency: a sale appears here a moment after the
order is placed. For a sales dashboard that is a fair trade for keeping the two
services independent.
"""

from django.db import models

from catalog.models import ArtisanProfile, Product


class SaleLine(models.Model):
    """One piece sold, as the order event described it.

    The title and unit price are copies, not lookups. A sale is a fact about a
    moment: if the artisan renames the listing or changes its price next week,
    what was sold last week must not change with it.
    """

    order_id = models.UUIDField()
    sku_id = models.UUIDField()

    # The listing may be archived or deleted later; the sale still happened, so
    # the link is optional and the copied fields carry the record.
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales"
    )
    artisan = models.ForeignKey(
        ArtisanProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales"
    )

    title = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_minor = models.BigIntegerField()
    line_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)

    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Delivery is at-least-once, so the same event can arrive twice.
            # This is what makes replaying it harmless.
            models.UniqueConstraint(
                fields=["order_id", "sku_id"], name="one_sale_line_per_sku_per_order"
            )
        ]
        indexes = [
            # Every query here is "this artisan, newest first".
            models.Index(fields=["artisan", "-occurred_at"], name="sales_artisan_recent_idx"),
        ]
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.title}"
