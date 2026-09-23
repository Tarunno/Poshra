local typedefs = require "kong.db.schema.typedefs"

-- Verification needs the key and the expected claims; stripping headers needs
-- nothing, so those fields are required only when the plugin verifies.
local function required_unless_strip_only(field)
  return {
    conditional = {
      if_field = "config.strip_only",
      if_match = { eq = false },
      then_field = "config." .. field,
      then_match = { required = true },
    },
  }
end

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
          { public_key_b64 = { type = "string", referenceable = true } },
          { key_id = { type = "string" } },
          { issuer = { type = "string" } },
          { audience = { type = "string" } },
          -- No default: a mismatch with the service's cookie name would make
          -- every signed-in request look anonymous, silently.
          { access_cookie = { type = "string" } },
          -- Seconds of clock drift tolerated between signer and gateway.
          { leeway = { type = "integer", required = true, default = 30, between = { 0, 300 } } },
          -- When false, a request without a token continues anonymously,
          -- which is what public browsing needs.
          { require_authentication = { type = "boolean", required = true, default = false } },
          -- Strip spoofable identity headers without verifying a token. Used
          -- on the credential routes, where a valid access token cannot exist
          -- yet, so a forged header cannot reach the service there either.
          { strip_only = { type = "boolean", required = true, default = false } },
          { user_header = { type = "string", required = true, default = "X-User-Id" } },
          { role_header = { type = "string", required = true, default = "X-User-Role" } },
        },
      },
    },
  },
  entity_checks = {
    required_unless_strip_only("public_key_b64"),
    required_unless_strip_only("issuer"),
    required_unless_strip_only("audience"),
    required_unless_strip_only("access_cookie"),
  },
}
