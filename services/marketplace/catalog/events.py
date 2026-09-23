"""Telling inventory what exists and how much of it.

The catalog owns what a piece *is*; the inventory service owns how many can be
sold. Those were two numbers kept in step by hand, which is how an order for a
freshly listed piece ended up failing with "unknown sku". This closes the gap:
saving a listing announces its level, and inventory consumes the announcement.

Delivery is best effort, not transactional. That is a deliberate difference
from the order outbox: losing an order event loses a sale nobody recorded,
while a stock level is small and fully derivable from this database, so a lost
event is repaired by the next save or by `manage.py sync_stock`. The reconciler
is what makes best effort acceptable.
"""

from __future__ import annotations

import atexit
import json
import logging
import uuid
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _producer():
    """One producer per process, created on first use.

    Import-time construction would make every management command and every test
    open a broker connection it never uses.
    """
    from confluent_kafka import Producer

    producer = Producer(
        {
            "bootstrap.servers": ",".join(settings.KAFKA_BROKERS),
            # Wait for every in-sync replica. A level that is not durable is a
            # level inventory may never learn.
            "acks": "all",
            "enable.idempotence": True,
            "linger.ms": 5,
        }
    )
    # Best effort has to at least try: flush what is queued before the process
    # goes away.
    atexit.register(lambda: producer.flush(5))
    return producer


def _delivered(error, message) -> None:
    if error is not None:
        log.error("stock event not delivered", extra={"error": str(error)})
    else:
        log.info(
            "stock event published",
            extra={"partition": message.partition(), "offset": message.offset()},
        )


def stock_payload(product) -> dict[str, Any]:
    """What inventory needs, and nothing else.

    A draft or archived piece announces zero rather than its count: it cannot
    be bought, and saying so here means a listing pulled from the shop stops
    being reservable even if something else still holds a reference to it.
    """
    from catalog.models import ProductStatus

    sellable = product.status == ProductStatus.PUBLISHED
    return {
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "sku_id": str(product.id),
        "quantity": product.stock if sellable else 0,
        "status": product.status,
    }


def publish_stock(product) -> None:
    """Announce one piece's level. Never raises: saving must not depend on Kafka."""
    if not settings.KAFKA_BROKERS:
        return  # not configured: tests, and the migration jobs

    payload = stock_payload(product)
    try:
        producer = _producer()
        producer.produce(
            settings.STOCK_TOPIC,
            # The key is the sku, so every change to one piece lands in the
            # same partition and arrives in the order it was made. Out of
            # order, an older count could overwrite a newer one.
            key=payload["sku_id"].encode(),
            value=json.dumps(payload).encode(),
            on_delivery=_delivered,
        )
        producer.poll(0)  # serve delivery callbacks without blocking the save
    except Exception as error:  # noqa: BLE001 — a broker problem is not a save problem
        log.error(
            "could not publish stock event",
            extra={"error": str(error), "sku_id": payload["sku_id"]},
        )


@receiver(post_save, sender="catalog.Product")
def announce_saved_product(sender, instance, **kwargs) -> None:
    # on_commit, so nothing is announced that a rolled-back transaction never
    # actually wrote.
    transaction.on_commit(lambda: publish_stock(instance))


@receiver(post_delete, sender="catalog.Product")
def announce_deleted_product(sender, instance, **kwargs) -> None:
    # A deleted listing cannot be sold, so its level goes to zero rather than
    # lingering as stock for a sku nothing can price.
    def zero() -> None:
        if not settings.KAFKA_BROKERS:
            return
        instance.status = "archived"
        publish_stock(instance)

    transaction.on_commit(zero)
