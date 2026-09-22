-- Generic Cell Rate Algorithm (GCRA): a leaky bucket used as a meter.
--
-- Instead of a queue or a counter, each key stores one number: the
-- "theoretical arrival time" (TAT), i.e. when the bucket would be empty again
-- if requests kept arriving at exactly the allowed rate.
--
--   T   = 1 / rate          emission interval: time one request "fills" the bucket
--   cap = T * burst         bucket capacity, expressed as time
--
-- A request is allowed if, after adding it, the bucket holds at most `cap`
-- worth of time: max(tat, now) + T - now <= cap.
--
-- Pure function with no ngx/kong dependencies, so it can be unit tested.

local max = math.max
local floor = math.floor

-- Tolerance in seconds. Real timestamps are ~1.8e9 s, where a double only has
-- ~2.4e-7 s of precision, so (now + T) - now is not exactly T. 1 microsecond
-- absorbs that error and is far below any meaningful rate-limit timescale.
local EPSILON = 1e-6

local _M = {}

-- @param tat    stored theoretical arrival time (seconds), or nil for a new key
-- @param now    current time (seconds, fractional)
-- @param rate   allowed requests per second (> 0)
-- @param burst  requests allowed back to back from an empty bucket (>= 1)
-- @return table {
--   allowed     = boolean,
--   tat         = new TAT to store (only meaningful when allowed),
--   remaining   = requests that could still be sent right now,
--   retry_after = seconds until a request would be allowed (0 if allowed),
--   reset       = seconds until the bucket is completely empty,
-- }
function _M.check(tat, now, rate, burst)
  local interval = 1 / rate
  local capacity = interval * burst
  local new_tat = max(tat or now, now) + interval
  local fill = new_tat - now

  if fill > capacity + EPSILON then
    local current_fill = fill - interval
    return {
      allowed = false,
      tat = tat,
      remaining = 0,
      retry_after = fill - capacity,
      reset = current_fill,
    }
  end

  return {
    allowed = true,
    tat = new_tat,
    remaining = floor((capacity - fill + EPSILON) / interval),
    retry_after = 0,
    reset = fill,
  }
end

return _M
