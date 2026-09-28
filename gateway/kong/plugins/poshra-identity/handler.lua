-- Verify Poshra access tokens at the edge and hand services a trusted identity.
--
-- Services never parse tokens: the gateway checks the signature once, with the
-- public key, and injects `X-User-Id` and `X-User-Role`. Everything behind the
-- gateway can then treat those headers as fact, provided the network only
-- admits gateway traffic (NetworkPolicy; mTLS later).
--
-- Authentication is *optional* by default. Anonymous visitors must be able to
-- browse the shop, so a request without a token passes through; a request with
-- a broken or expired token is rejected, so the client knows to refresh.

local jwt_parser = require "kong.plugins.jwt.jwt_parser"
local claims_validator = require "kong.plugins.poshra-identity.claims"
local openssl_base64 = require "ngx.base64"

local kong = kong
local ngx = ngx

local Identity = {
  -- Above every bundled plugin, because scrubbing untrusted headers has to
  -- happen before anything reads them.
  --
  -- correlation-id runs at 100001 and, finding no X-Request-ID, generates a
  -- trusted one and sets it on the request. Underneath, that is
  -- ngx.req.set_header, which rewrites the live request -- so a plugin running
  -- after it cannot tell the gateway's own id from one the client sent, and
  -- clearing the header there deleted the trusted value instead of the forged
  -- one. Running first means the client's copy is gone before correlation-id
  -- looks, so the id it generates is the id the service logs and the id the
  -- client is handed.
  --
  -- Still above rate limiting (910), so limits can key on the user. The
  -- trade-off is that this now runs before the bundled auth plugins too; none
  -- are configured, and identity here is read from the token directly.
  PRIORITY = 100002,
  VERSION = "0.1.0",
}

-- Headers a client must never be able to set: they are the identity the
-- services trust. Stripped on every request, authenticated or not.
local SPOOFABLE_HEADERS = {
  "X-User-Id",
  "X-User-Role",
  "X-User-Email",
  -- A client that could set these would be telling the services which token
  -- it holds and what that token may do. Both are the gateway's to say.
  "X-Token-Id",
  "X-Token-Scope",
  "X-Consumer-Id",
  "X-Consumer-Username",
  -- The correlation id is the gateway's to decide; a client-supplied value
  -- would let anyone forge or collide with another request's logs. Stripping
  -- it only works because this plugin now runs before correlation-id -- see
  -- PRIORITY below.
  "X-Request-ID",
}

local function decode_public_key(conf)
  local pem = openssl_base64.decode_base64url(conf.public_key_b64)
  if not pem then
    -- Standard base64 (with + / and padding), which is what `base64 -w0` emits.
    pem = ngx.decode_base64(conf.public_key_b64)
  end
  return pem
end

local function token_from_request(conf)
  local auth = kong.request.get_header("authorization")
  if auth then
    local token = auth:match("^[Bb]earer%s+(.+)$")
    if token then
      return token
    end
  end
  -- Browsers send the session as an HttpOnly cookie; page JavaScript cannot
  -- read it, so it cannot attach an Authorization header either.
  local cookie = kong.request.get_header("cookie")
  if cookie then
    return cookie:match("[; ]?" .. conf.access_cookie .. "=([^;]+)")
  end
  return nil
end

local function unauthorized(message)
  return kong.response.exit(401, { message = message }, {
    -- Tells a client this is an authentication problem, not authorisation.
    ["WWW-Authenticate"] = 'Bearer realm="poshra", error="invalid_token"',
  })
end

function Identity:access(conf)
  for _, header in ipairs(SPOOFABLE_HEADERS) do
    kong.service.request.clear_header(header)
  end

  if conf.strip_only then
    -- Credential routes: nothing to verify yet, but forged headers must still
    -- not reach the service.
    return
  end

  local token = token_from_request(conf)
  if not token then
    if conf.require_authentication then
      return unauthorized("Authentication required")
    end
    return -- anonymous: public browsing keeps working
  end

  local jwt, err = jwt_parser:new(token)
  if err then
    kong.log.info("rejected malformed token: ", err)
    return unauthorized("Invalid token")
  end

  -- Reject an unexpected key id before spending a signature verification on
  -- it, and so a retired key cannot be used after rotation.
  if conf.key_id and jwt.header and jwt.header.kid ~= conf.key_id then
    kong.log.info("rejected token with unknown kid: ", tostring(jwt.header.kid))
    return unauthorized("Invalid token")
  end

  -- The algorithm comes from the token header, so it must be checked against
  -- what we expect. Accepting "none", or an HMAC algorithm verified with a
  -- public key, is the classic JWT forgery.
  if not jwt.header or jwt.header.alg ~= "RS256" then
    kong.log.info("rejected token with algorithm: ", tostring(jwt.header and jwt.header.alg))
    return unauthorized("Invalid token")
  end

  local public_key = decode_public_key(conf)
  if not public_key then
    kong.log.err("poshra-identity: public key is not valid base64")
    return kong.response.exit(500, { message = "An unexpected error occurred" })
  end

  if not jwt:verify_signature(public_key) then
    kong.log.info("rejected token with bad signature")
    return unauthorized("Invalid token")
  end

  local ok, reason = claims_validator.validate(jwt.claims, {
    issuer = conf.issuer,
    audience = conf.audience,
    leeway = conf.leeway,
  }, ngx.time())
  if not ok then
    kong.log.info("rejected token: ", reason)
    return unauthorized(reason == "token expired" and "Token expired" or "Invalid token")
  end

  local identity = claims_validator.identity(jwt.claims)
  kong.service.request.set_header(conf.user_header, identity.id)
  kong.service.request.set_header(conf.role_header, identity.role)
  -- Absent on a browser's token, so downstream code reads "no token id" as
  -- "a person at a keyboard" rather than as something missing.
  if identity.token_id then
    kong.service.request.set_header(conf.token_id_header, identity.token_id)
  end
  if identity.scope then
    kong.service.request.set_header(conf.token_scope_header, identity.scope)
  end
  -- Makes the user visible to logging and to rate limiting by user.
  kong.ctx.shared.poshra_user_id = identity.id
end

return Identity
