# syntax=docker/dockerfile:1
# Kong with Poshra's declarative config and custom plugins baked in, so the
# cluster needs no config mounts. Local development still bind-mounts these
# files (see deploy/compose/compose.yaml) for fast iteration.
FROM kong:3.9.3

USER root
COPY plugins/poshra-leaky-bucket /usr/local/share/lua/5.1/kong/plugins/poshra-leaky-bucket
COPY plugins/poshra-identity /usr/local/share/lua/5.1/kong/plugins/poshra-identity
COPY kong.yaml /kong/kong.yaml
RUN chown -R kong:0 /kong && chmod -R g=u /kong

USER kong
# Ask for A records before SRV. Kong's default order tries SRV first, and a
# resolver that answers unknown names with a parking address (many home and ISP
# resolvers do) then poisons upstream resolution.
ENV KONG_DNS_ORDER=A,CNAME,SRV,LAST \
    KONG_DATABASE=off \
    KONG_DECLARATIVE_CONFIG=/kong/kong.yaml \
    KONG_PLUGINS=bundled,poshra-leaky-bucket,poshra-identity \
    KONG_NGINX_HTTP_LUA_SHARED_DICT="poshra_leaky_bucket 10m; lua_shared_dict poshra_leaky_bucket_locks 1m"

# The gateway is where a request first exists, so it is where the trace should
# begin. Without these Kong loads the opentelemetry plugin but produces no
# spans of its own: the instrumentations are off by default, because each one
# costs something on every request.
ENV KONG_TRACING_INSTRUMENTATIONS=request,router,balancer,plugin_access,plugin_header_filter \
    KONG_TRACING_SAMPLING_RATE=1.0

