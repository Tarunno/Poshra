-- Claim validation for Poshra access tokens.
--
-- A valid signature only proves the token was minted by the holder of the
-- private key. It says nothing about *which* issuer, for *which* audience, or
-- whether the token has expired, so those are checked here.
--
-- Pure Lua with no kong or ngx dependency, so it can be unit tested.

local _M = {}

-- Allow a little clock drift between the service that signs and the gateway
-- that verifies. Without it, a token can look expired a second early.
local DEFAULT_LEEWAY = 30

--- Validate the registered and Poshra-specific claims of a decoded token.
--
-- @param claims  table of decoded claims
-- @param opts    { issuer, audience, leeway }
-- @param now     current unix time
-- @return true on success, or nil plus a reason
function _M.validate(claims, opts, now)
  if type(claims) ~= "table" then
    return nil, "malformed token"
  end

  local leeway = opts.leeway or DEFAULT_LEEWAY

  if type(claims.exp) ~= "number" then
    return nil, "missing exp"
  end
  if now > claims.exp + leeway then
    return nil, "token expired"
  end

  -- A token issued in the future is either a clock problem or a forgery.
  if type(claims.iat) == "number" and claims.iat > now + leeway then
    return nil, "token issued in the future"
  end
  if type(claims.nbf) == "number" and now + leeway < claims.nbf then
    return nil, "token not yet valid"
  end

  if opts.issuer and claims.iss ~= opts.issuer then
    return nil, "unexpected issuer"
  end

  -- The audience binds a token to this API. Without it, a token minted for a
  -- different service by the same issuer would be accepted here.
  if opts.audience then
    local aud = claims.aud
    if type(aud) == "table" then
      local found = false
      for _, value in ipairs(aud) do
        if value == opts.audience then
          found = true
          break
        end
      end
      if not found then
        return nil, "unexpected audience"
      end
    elseif aud ~= opts.audience then
      return nil, "unexpected audience"
    end
  end

  if type(claims.sub) ~= "string" or claims.sub == "" then
    return nil, "missing subject"
  end

  return true
end

--- The identity a verified token conveys downstream.
function _M.identity(claims)
  return {
    id = claims.sub,
    role = type(claims.role) == "string" and claims.role or "buyer",
  }
end

return _M
