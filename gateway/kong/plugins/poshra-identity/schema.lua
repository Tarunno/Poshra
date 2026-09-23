local typedefs = require "kong.db.schema.typedefs"

return {
  name = "poshra-identity",
  fields = {
    { protocols = typedefs.protocols_http },
    { consumer = typedefs.no_consumer },
    {
      config = {
        type = "record",
        fields = {
          -- The verifying half of the signing pair, base64-encoded so it
          -- survives a single-line environment variable. Supplied through
          -- Kong's env vault, never committed.
          { public_key_b64 = { type = "string", required = true, referenceable = true } },
          { key_id = { type = "string" } },
          { issuer = { type = "string", required = true } },
          { audience = { type = "string", required = true } },
          -- Deliberately has no default: a mismatch with the service would make
          -- every signed-in request look anonymous, silently.
          { access_cookie = { type = "string", required = true } },
          -- Seconds of clock drift tolerated between signer and gateway.
          { leeway = { type = "integer", required = true, default = 30, between = { 0, 300 } } },
          -- When false, a request without a token continues anonymously, which
          -- is what public browsing needs.
          { require_authentication = { type = "boolean", required = true, default = false } },
          { user_header = { type = "string", required = true, default = "X-User-Id" } },
          { role_header = { type = "string", required = true, default = "X-User-Role" } },
        },
      },
    },
  },
}
