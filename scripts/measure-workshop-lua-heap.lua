-- Separate sampled-heap probe of the paired production-consumer benchmark.
-- The hook adds overhead: never use this run's timings as performance evidence.
-- Run from the paired addon's tests directory, with REPO and artifact env set.
local peak, samples = 0, 0
local function sample()
    peak = math.max(peak, collectgarbage('count'))
    samples = samples + 1
end
sample()
debug.sethook(sample, '', 10000)
dofile('bench_workshop_summary.lua')
debug.sethook()
sample()
local before_gc = collectgarbage('count')
collectgarbage('collect')
print(string.format('{"synthetic":true,"real_game":false,"instrumented_timings_invalid":true,"sample_instruction_interval":10000,"samples":%d,"sampled_peak_lua_heap_kib":%d,"heap_before_final_gc_kib":%d,"heap_after_final_gc_kib":%d}', samples, math.floor(peak), math.floor(before_gc), math.floor(collectgarbage('count'))))
