"""The ASGI surface: one MCP endpoint and one health check.

`/mcp` is the whole protocol. An MCP client POSTs JSON-RPC to it — initialize,
then tools/list, then tools/call — and the transport answers either with a
single JSON body or with an SSE stream, depending on what the call needs. It
is one URL rather than the two the older HTTP+SSE transport used, which is why
it survives a gateway and a load balancer without sticky sessions.

Stateless on purpose. Each request carries everything it needs, so any replica
can answer any call and a pod restart costs nobody their session. The price is
that the server cannot push notifications to a client between calls, which a
catalog nobody is subscribed to does not need.
"""

from __future__ import annotations

import logging
import os

from mcp.server.transport_security import TransportSecuritySettings

from app.catalog import CatalogClient
from app.config import Config, ConfigError
from app.logging import configure_logging
from app.server import build_server
from app.shopper import CheckoutClient, TokenStillLive
from app.telemetry import configure_tracing

configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)

try:
    config = Config.load()
except ConfigError as error:
    log.error("bad configuration", extra={"error": str(error)})
    raise

# Without a CHECKOUT_URL the cart tools are not registered, so a deployment
# that has no checkout advertises three tools rather than six that fail.
checkout = (
    CheckoutClient(config.checkout_url, config.request_timeout) if config.checkout_url else None
)
still_live = TokenStillLive(config.catalog_url, config.request_timeout)

server = build_server(
    CatalogClient(config.catalog_url, config.request_timeout),
    checkout,
    still_live,
    storefront_url=config.storefront_url,
)


app = server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    # Answer with a plain JSON body unless a call genuinely needs to stream.
    # Kong buffers responses by default, and an SSE stream behind a buffering
    # proxy arrives as one lump at the end — which we have already been bitten
    # by once on the assistant's route.
    json_response=True,
    transport_security=TransportSecuritySettings(
        # Off when nothing is listed: in the cluster the gateway is the only
        # way in, and a list that has to be right for the service to answer at
        # all is a list that will be wrong at three in the morning.
        enable_dns_rebinding_protection=bool(config.allowed_hosts or config.allowed_origins),
        allowed_hosts=config.allowed_hosts,
        allowed_origins=config.allowed_origins,
    ),
)

configure_tracing("mcp-storefront", app)
log.info("mcp-storefront ready", extra={"catalog": config.catalog_url})
