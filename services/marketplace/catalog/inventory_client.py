"""Reading the stock ledger back from the service that owns it.

The catalog normally only *writes* levels, by announcing them on Kafka. This is
the one direction that goes the other way, and it exists for repair: when the
catalog's copy of a level has drifted, the ledger is the only thing that knows
what it should be.

Nothing that serves a request calls this. A product page reads this service's
own copy on purpose — a storefront that needs inventory to render is a
storefront that goes down when inventory does.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import grpc
from django.conf import settings

from poshra.inventory.v1 import inventory_pb2, inventory_pb2_grpc


class InventoryUnavailable(Exception):
    """The ledger could not be read, so nothing should be written."""


@contextmanager
def channel() -> Iterator[inventory_pb2_grpc.InventoryServiceStub]:
    """A stub for the duration of one command. Plaintext: this never leaves the cluster."""
    if not settings.INVENTORY_ADDR:
        raise InventoryUnavailable("INVENTORY_ADDR is not set")

    with grpc.insecure_channel(settings.INVENTORY_ADDR) as connection:
        yield inventory_pb2_grpc.InventoryServiceStub(connection)


def on_hand(stub, sku_ids: Sequence[str], *, timeout: float = 10.0) -> dict[str, int]:
    """How many of each sku exist, held or not.

    `available + reserved`, not `available` alone: a piece held by a live
    reservation has not been sold, and the catalog's number mirrors what the
    artisan has, which is what SetStock is given when a listing is saved.
    Counting only what is free would drop a piece from the listing the moment
    someone opened a checkout, and put it back if they walked away.

    Skus the ledger has never heard of are absent from the reply, and stay
    absent here rather than being reported as zero — see the command for why
    that distinction is worth keeping.
    """
    try:
        reply = stub.GetStock(inventory_pb2.GetStockRequest(sku_ids=list(sku_ids)), timeout=timeout)
    except grpc.RpcError as error:  # noqa: PERF203 — the batch is the unit of failure
        raise InventoryUnavailable(f"GetStock failed: {error.code().name}") from error

    return {level.sku_id: level.available + level.reserved for level in reply.levels}
