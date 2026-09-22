local typedefs = require "kong.db.schema.typedefs"

return {
  name = "poshra-leaky-bucket",
  fields = {
    { protocols = typedefs.protocols_http },
    { consumer = typedefs.no_consumer },
    {
      config = {
        type = "record",
        fields = {
          -- Steady rate the bucket leaks at, in requests per second.
          { rate = { type = "number", required = true, gt = 0 } },
          -- Requests allowed back to back when the bucket is empty.
          { burst = { type = "integer", required = true, default = 1, between = { 1, 100000 } } },
          -- Who shares a bucket: the client IP, or a trusted identity header
          -- (e.g. X-User-Id once the gateway authenticates users).
          { limit_by = { type = "string", required = true, default = "ip", one_of = { "ip", "header" } } },
          { header_name = { type = "string", required = true, default = "X-User-Id" } },
          { hide_client_headers = { type = "boolean", required = true, default = false } },
          -- If the limiter itself fails (lock timeout, missing shared dict),
          -- let traffic through rather than turning a limiter bug into an outage.
          { fault_tolerant = { type = "boolean", required = true, default = true } },
        },
      },
    },
  },
}
