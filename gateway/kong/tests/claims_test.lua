-- Unit tests for access-token claim validation. Run: make kong-test
package.path = "/kong/plugins/?.lua;" .. package.path
local claims = require "poshra-identity.claims"

local passed, failed = 0, 0
local function test(name, fn)
  local ok, err = pcall(fn)
  if ok then
    passed = passed + 1
    print("  ok    " .. name)
  else
    failed = failed + 1
    print("  FAIL  " .. name .. "\n        " .. tostring(err))
  end
end

local NOW = 1790000000
-- In Lua, `{ exp = nil }` is an empty table, so a nil override cannot remove a
-- default. This sentinel says "drop this claim" explicitly.
local NONE = setmetatable({}, { __tostring = function() return "NONE" end })
local OPTS = { issuer = "poshra-marketplace", audience = "poshra-api", leeway = 30 }

local function valid(overrides)
  local c = {
    iss = "poshra-marketplace",
    aud = "poshra-api",
    sub = "0ed6221f-cf81-4dd6-a72f-ee8151d12180",
    role = "artisan",
    iat = NOW - 10,
    exp = NOW + 600,
  }
  for k, v in pairs(overrides or {}) do
    c[k] = (v ~= NONE) and v or nil
  end
  return c
end

local function rejects(overrides, expected)
  local ok, reason = claims.validate(valid(overrides), OPTS, NOW)
  assert(not ok, "expected rejection")
  assert(reason == expected, "expected '" .. expected .. "', got '" .. tostring(reason) .. "'")
end

print("claims")

test("accepts a well-formed token", function()
  assert(claims.validate(valid(), OPTS, NOW))
end)

test("rejects a token from another issuer", function()
  rejects({ iss = "evil-issuer" }, "unexpected issuer")
end)

test("rejects a token minted for another audience", function()
  -- Same issuer, different service: without this check, a token for the
  -- internal ops API would open the storefront API too.
  rejects({ aud = "poshra-ops" }, "unexpected audience")
end)

test("accepts an audience list that contains ours", function()
  assert(claims.validate(valid({ aud = { "other", "poshra-api" } }), OPTS, NOW))
end)

test("rejects an audience list without ours", function()
  rejects({ aud = { "other", "third" } }, "unexpected audience")
end)

test("rejects an expired token", function()
  rejects({ exp = NOW - 31 }, "token expired")
end)

test("tolerates clock drift within the leeway", function()
  assert(claims.validate(valid({ exp = NOW - 10 }), OPTS, NOW))
end)

test("rejects a token issued in the future", function()
  rejects({ iat = NOW + 120 }, "token issued in the future")
end)

test("honours nbf", function()
  rejects({ nbf = NOW + 120 }, "token not yet valid")
end)

test("rejects a token with no expiry", function()
  rejects({ exp = NONE }, "missing exp")
end)

test("rejects a token with no subject", function()
  rejects({ sub = "" }, "missing subject")
end)

test("rejects a non-table payload", function()
  local ok, reason = claims.validate("not-a-table", OPTS, NOW)
  assert(not ok and reason == "malformed token")
end)

test("identity carries the subject and role", function()
  local id = claims.identity(valid())
  assert(id.id == "0ed6221f-cf81-4dd6-a72f-ee8151d12180")
  assert(id.role == "artisan")
end)

test("identity falls back to buyer when the role claim is missing", function()
  -- A token without a role must not grant more than the least privileged one.
  assert(claims.identity(valid({ role = NONE })).role == "buyer")
end)

print(string.format("\n%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
