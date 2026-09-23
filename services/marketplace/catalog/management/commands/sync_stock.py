"""Republish every sellable piece's level.

The safety net behind best-effort publishing. Saving a listing announces its
level, but a broker outage at that moment loses the announcement; running this
brings inventory back into step with the catalog, because the catalog is the
source these levels are derived from.

Safe to run whenever: the events are the same ones a save would send, keyed by
sku, and inventory's SetStock is idempotent.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.events import publish_stock
from catalog.models import Product


class Command(BaseCommand):
    help = "Send every product's stock level to the inventory service."

    def handle(self, *args, **options):
        if not settings.KAFKA_BROKERS:
            raise SystemExit("KAFKA_BROKERS is required")

        products = Product.objects.all().only("id", "stock", "status")
        count = 0
        for product in products.iterator():
            publish_stock(product)
            count += 1

        # produce() only queues; without this the process can exit with events
        # still in the buffer.
        from catalog.events import _producer

        _producer().flush(30)
        self.stdout.write(f"published {count} stock levels to {settings.STOCK_TOPIC}")
