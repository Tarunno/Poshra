# syntax=docker/dockerfile:1
# Kong with Poshra's declarative config and custom plugins baked in, so the
# cluster needs no config mounts. Local development still bind-mounts these
# files (see deploy/compose/compose.yaml) for fast iteration.
FROM kong:3.9.3

USER root
COPY plugins/poshra-leaky-bucket /usr/local/share/lua/5.1/kong/plugins/poshra-leaky-bucket
COPY kong.yaml /kong/kong.yaml
RUN chown -R kong:0 /kong && chmod -R g=u /kong

USER kong
ENV KONG_DATABASE=off \
    KONG_DECLARATIVE_CONFIG=/kong/kong.yaml \
    KONG_PLUGINS=bundled,poshra-leaky-bucket \
    KONG_NGINX_HTTP_LUA_SHARED_DICT="poshra_leaky_bucket 10m; lua_shared_dict poshra_leaky_bucket_locks 1m"
