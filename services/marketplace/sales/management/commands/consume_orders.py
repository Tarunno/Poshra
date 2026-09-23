"""Consume order events into the sales read model.

Runs as its own deployment, not inside the web server: a consumer that shares a
process with gunicorn would be scaled by request traffic rather than by the
number of partitions, and would stop consuming whenever the web tier restarts.
"""

from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException
from django.conf import settings
from django.core.management.base import BaseCommand

from sales.events import UnprocessableEvent, record_order

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Read poshra.orders.created.v1 and build the artisan sales read model."

    def add_arguments(self, parser):
        parser.add_argument("--topic", default=settings.ORDERS_TOPIC)
        parser.add_argument("--group", default=settings.SALES_CONSUMER_GROUP)
        parser.add_argument(
            "--once",
            action="store_true",
            help="Drain what is already there and exit, instead of following the topic.",
        )

    def handle(self, *args, **options):
        if not settings.KAFKA_BROKERS:
            raise SystemExit("KAFKA_BROKERS is required")

        consumer = Consumer(
            {
                "bootstrap.servers": ",".join(settings.KAFKA_BROKERS),
                "group.id": options["group"],
                # Committing after the write, never before: an offset committed
                # early turns a crash into a sale nobody recorded.
                "enable.auto.commit": False,
                # A new group reads the topic from the start, so deploying this
                # for the first time backfills every order already placed.
                "auto.offset.reset": "earliest",
            }
        )
        consumer.subscribe([options["topic"]])

        running = True

        def stop(*_: Any) -> None:
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        log.info("consuming orders", extra={"topic": options["topic"], "group": options["group"]})

        idle_polls = 0
        try:
            while running:
                message = consumer.poll(1.0)
                if message is None:
                    idle_polls += 1
                    if options["once"] and idle_polls > 3:
                        break
                    continue
                idle_polls = 0

                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(message.error())

                if self._handle(message):
                    # Only now is this offset safe to record.
                    consumer.commit(message=message, asynchronous=False)
        finally:
            # Leaves the group cleanly, so the partitions move to another
            # member immediately instead of after the session times out.
            consumer.close()

    def _handle(self, message) -> bool:
        """Record one event. Returns False only when it should be retried."""
        backoff = 0.5
        while True:
            try:
                payload = json.loads(message.value())
            except (TypeError, ValueError) as error:
                # Malformed stays malformed. Blocking the partition on it would
                # stop every later sale behind it.
                log.error(
                    "dropping unreadable event",
                    extra={"error": str(error), "offset": message.offset()},
                )
                return True

            try:
                written = record_order(payload)
            except UnprocessableEvent as error:
                log.error(
                    "dropping unprocessable event",
                    extra={"error": str(error), "offset": message.offset()},
                )
                return True
            except Exception as error:  # noqa: BLE001 — the database is down, or similar
                log.error(
                    "retrying event",
                    extra={"error": str(error), "offset": message.offset(), "backoff": backoff},
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

            log.info(
                "recorded sale",
                extra={
                    "lines": written,
                    "partition": message.partition(),
                    "offset": message.offset(),
                },
            )
            return True
