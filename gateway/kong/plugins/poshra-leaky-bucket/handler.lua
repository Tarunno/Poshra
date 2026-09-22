local gcra = require "kong.plugins.poshra-leaky-bucket.gcra"
local resty_lock = require "resty.lock"

local ceil = math.ceil
local ngx_now = ngx.now
local update_time = ngx.update_time

local DICT_NAME = "poshra_leaky_bucket"
local LOCK_DICT_NAME = "poshra_leaky_bucket_locks"

local LeakyBucket = {
  -- Same slot as the bundled rate-limiting plugin: after authentication
  -- plugins, so identity headers are available when limiting by user.
  PRIORITY = 910,
  VERSION = "0.1.0",
}

local function identifier(conf)
  if conf.limit_by == "header" then
    local value = kong.request.get_header(conf.header_name)
    if value and value ~= "" then
      return "h:" .. value
    end
  end
  return "ip:" .. kong.client.get_forwarded_ip()
end

local function scope()
  local route = kong.router.get_route()
  if route then
    return route.id
  end
  local service = kong.router.get_service()
  return service and service.id or "global"
end

local function limiter_failed(conf, message, err)
  kong.log.err(message, err and (": " .. tostring(err)) or "")
  if conf.fault_tolerant then
    return
  end
  return kong.response.exit(500, { message = "An unexpected error occurred" })
end

function LeakyBucket:access(conf)
  local dict = ngx.shared[DICT_NAME]
  if not dict then
    return limiter_failed(conf, "shared dict '" .. DICT_NAME .. "' is not configured")
  end

  local key = scope() .. ":" .. identifier(conf)

  -- Read-modify-write must be atomic across nginx worker processes.
  local lock, err = resty_lock:new(LOCK_DICT_NAME, { timeout = 0.05, exptime = 1 })
  if not lock then
    return limiter_failed(conf, "failed to create lock", err)
  end
  local elapsed
  elapsed, err = lock:lock(key)
  if not elapsed then
    return limiter_failed(conf, "failed to acquire lock", err)
  end

  update_time()
  local now = ngx_now()
  local result = gcra.check(dict:get(key), now, conf.rate, conf.burst)

  if result.allowed then
    -- Expire the key once the bucket is empty; nothing to remember after that.
    local ok, set_err = dict:set(key, result.tat, ceil(result.reset) + 1)
    if not ok then
      lock:unlock()
      return limiter_failed(conf, "failed to store bucket state", set_err)
    end
  end
  lock:unlock()

  local headers
  if not conf.hide_client_headers then
    headers = {
      ["RateLimit-Limit"] = conf.burst,
      ["RateLimit-Remaining"] = result.remaining,
      ["RateLimit-Reset"] = ceil(result.reset),
    }
  end

  if not result.allowed then
    headers = headers or {}
    headers["Retry-After"] = ceil(result.retry_after)
    return kong.response.exit(429, { message = "API rate limit exceeded" }, headers)
  end

  if headers then
    kong.response.set_headers(headers)
  end
end

return LeakyBucket
