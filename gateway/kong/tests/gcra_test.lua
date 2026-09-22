-- Unit tests for the GCRA algorithm. Run: make kong-test
package.path = "/kong/plugins/?.lua;" .. package.path
local gcra = require "poshra-leaky-bucket.gcra"

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

local function near(a, b) return math.abs(a - b) < 1e-6 end

-- Send `n` requests at time `now`, returning the final TAT and results.
local function burst_at(tat, now, n, rate, burst)
  local results = {}
  for i = 1, n do
    local r = gcra.check(tat, now, rate, burst)
    if r.allowed then tat = r.tat end
    results[i] = r
  end
  return tat, results
end

print("gcra")

test("empty bucket allows exactly `burst` requests at once", function()
  local _, results = burst_at(nil, 100, 12, 5, 10)
  for i = 1, 10 do assert(results[i].allowed, "request " .. i .. " should pass") end
  assert(not results[11].allowed and not results[12].allowed, "11th and 12th should be rejected")
end)

test("remaining counts down from burst - 1 to 0", function()
  local _, results = burst_at(nil, 100, 10, 5, 10)
  assert(results[1].remaining == 9, "first remaining=" .. results[1].remaining)
  assert(results[10].remaining == 0, "last remaining=" .. results[10].remaining)
end)

test("retry_after is the exact time until one slot leaks out", function()
  local tat = burst_at(nil, 100, 10, 5, 10)
  local r = gcra.check(tat, 100, 5, 10)
  assert(not r.allowed)
  assert(near(r.retry_after, 0.2), "retry_after=" .. r.retry_after) -- 1/rate
end)

test("after waiting 1/rate exactly one more request fits", function()
  local tat = burst_at(nil, 100, 10, 5, 10)
  local r1 = gcra.check(tat, 100.2, 5, 10)
  assert(r1.allowed, "first after wait should pass")
  local r2 = gcra.check(r1.tat, 100.2, 5, 10)
  assert(not r2.allowed, "second after wait should be rejected")
end)

test("steady traffic at the rate is never rejected", function()
  local tat, now = nil, 100
  for _ = 1, 1000 do
    local r = gcra.check(tat, now, 5, 1)
    assert(r.allowed, "rejected at t=" .. now)
    tat, now = r.tat, now + 0.2
  end
end)

test("burst = 1 enforces strict spacing", function()
  local r1 = gcra.check(nil, 100, 10, 1)
  local r2 = gcra.check(r1.tat, 100.05, 10, 1)
  assert(r1.allowed and not r2.allowed)
  assert(near(r2.retry_after, 0.05), "retry_after=" .. r2.retry_after)
end)

test("an idle bucket fully drains", function()
  local tat = burst_at(nil, 100, 10, 5, 10)
  local _, results = burst_at(tat, 102, 10, 5, 10) -- 10 * 0.2s = 2s to drain
  for i = 1, 10 do assert(results[i].allowed, "request " .. i .. " after drain") end
end)

test("rejections do not change the stored state", function()
  local tat = burst_at(nil, 100, 10, 5, 10)
  local r = gcra.check(tat, 100, 5, 10)
  assert(not r.allowed and r.tat == tat)
end)

test("reset is the time until the bucket is empty", function()
  local tat = burst_at(nil, 100, 10, 5, 10)
  local r = gcra.check(tat, 100, 5, 10)
  assert(near(r.reset, 2.0), "reset=" .. r.reset)
end)

test("real Unix timestamps: float error does not lose a slot (regression)", function()
  local now = 1790000000.123 -- ~2026 epoch seconds; doubles have ~2.4e-7 s precision here
  local tat, results = burst_at(nil, now, 11, 5, 10)
  assert(results[1].remaining == 9, "first remaining=" .. results[1].remaining)
  for i = 1, 10 do assert(results[i].allowed, "request " .. i .. " should pass") end
  assert(not results[11].allowed, "11th should be rejected")
  local r = gcra.check(tat, now + 0.2, 5, 10)
  assert(r.allowed and r.remaining == 0, "one slot after 1/rate, remaining=" .. r.remaining)
end)

print(string.format("\n%d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
