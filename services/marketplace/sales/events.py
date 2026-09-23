"""Turning an order event into sale lines.

Kept apart from the consumer so the interesting half can be tested without a
broker: this module is a pure function from an event payload to rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils.dateparse import parse_datetime

from catalog.models import Product
from sales.models import SaleLine

log = logging.getLogger(__name__)


class UnprocessableEvent(Exception):
    """The event can never be recorded, however many times it is retried."""


@dataclass(frozen=True)
class Line:
    sku_id: str
    title: str
    quantity: int
    unit_minor: int


def parse_order_created(payload: dict) -> tuple[str, datetime, str, list[Line]]:
    """Read the parts of the event this service needs.

    Anything else in the payload is ignored on purpose: a consumer that reads
    only what it uses does not break when the producer adds a field.
    """
    order_id = payload.get("order_id")
    if not order_id:
        raise UnprocessableEvent("no order_id")

    occurred_at = parse_datetime(payload.get("occurred_at") or "")
    if occurred_at is None:
        raise UnprocessableEvent("no usable occurred_at")

    currency = payload.get("currency") or "BDT"

    lines: list[Line] = []
    for raw in payload.get("items") or []:
        sku_id = raw.get("sku_id")
        quantity = raw.get("quantity")
        unit_minor = raw.get("unit_minor")
        if not sku_id or not isinstance(quantity, int) or not isinstance(unit_minor, int):
            raise UnprocessableEvent(f"malformed item in order {order_id}")
        lines.append(
            Line(
                sku_id=sku_id,
                title=raw.get("title") or "",
                quantity=quantity,
                unit_minor=unit_minor,
            )
        )

    if not lines:
        raise UnprocessableEvent(f"order {order_id} has no items")

    return order_id, occurred_at, currency, lines


@transaction.atomic
def record_order(payload: dict) -> int:
    """Write the sale lines for one order. Safe to call repeatedly.

    The event names a sku, not a maker — checkout has no idea who made what.
    Resolving it here is the point of the read model living in this service:
    it already owns the products and their artisans.
    """
    order_id, occurred_at, currency, lines = parse_order_created(payload)

    products = {
        str(product.id): product
        for product in Product.objects.select_related("artisan").filter(
            id__in=[line.sku_id for line in lines]
        )
    }

    written = 0
    for line in lines:
        product = products.get(line.sku_id)
        if product is None:
            # Sold, then the listing was deleted. The sale is still a fact, so
            # it is recorded with the title the buyer saw.
            log.warning("sale for unknown product", extra={"sku_id": line.sku_id})

        SaleLine.objects.update_or_create(
            order_id=order_id,
            sku_id=line.sku_id,
            defaults={
                "product": product,
                "artisan": product.artisan if product else None,
                "title": line.title or (product.title if product else "A piece"),
                "quantity": line.quantity,
                "unit_minor": line.unit_minor,
                "line_minor": line.unit_minor * line.quantity,
                "currency": currency,
                "occurred_at": occurred_at,
            },
        )
        written += 1

    return written
