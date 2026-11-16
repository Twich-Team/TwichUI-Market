-- Diagnostic CPU attribution, not the uninstrumented acceptance benchmark.
-- "no-gc" is a bounded offline experiment only; production GC policy is untouched.
require("bit")
TwichUI={Workshop={}};GetTimePreciseSec=os.clock
for _,name in ipairs({"Data","BridgeCodec","BridgeSchema","BridgeValidate","Bridge"})do dofile(arg[1].."/TwichUI_Workshop/"..name..".lua")end
assert(loadfile(arg[2]))()
local B,J,S=TwichUI.Workshop.Bridge,TwichUI.Workshop.BridgeCodec,TwichUI.Workshop.BridgeValidate
local times,calls,units,stack={},{},{},{}
local previous=os.clock();local encode=J.Encode
local function account()
    local now=os.clock();local name=stack[#stack] or "reader_and_scheduler"
    times[name]=(times[name] or 0)+now-previous;previous=now
end
local function wrap(name,fn)
    return function(...)
        account();calls[name]=(calls[name] or 0)+1;stack[#stack+1]=name
        local value=fn(...);account();stack[#stack]=nil;return value
    end
end
J.Parse=wrap("json_parse",J.Parse);J.Encode=wrap("json_encode",J.Encode)
S.Header=wrap("manifest_semantics",S.Header);S.Record=wrap("record_semantics",S.Record)
local hash=J.Hash
J.Hash=function(...)
    local ctx=hash(...);ctx.Update=wrap("hash_update",ctx.Update);ctx.Finish=wrap("hash_finish",ctx.Finish);return ctx
end
local resume=coroutine.resume
coroutine.resume=function(co)
    local started,heap=os.clock(),collectgarbage("count")
    local ok,value=resume(co)
    local elapsed=math.floor((os.clock()-started)*1e6+.5)
    local phase=stack[#stack] or "reader_and_scheduler";local after=collectgarbage("count")
    local old=units[phase]
    if not old or elapsed>old.maximum_us then
        units[phase]=setmetatable({maximum_us=elapsed,heap_delta_bytes=math.floor((after-heap)*1024),
                                  collection_observed=after<heap},J.OBJECT)
    end
    return ok,value
end
collectgarbage("collect")
if arg[3]=="no-gc"then collectgarbage("stop")end
local base=collectgarbage("count")*1024
B.Begin(TwichUIMarketData);previous=os.clock()
for i=1,1000000 do local ok,why=B.Step(3);if why~="loading"then assert(ok);break end;assert(i<1000000)end
account()
local heap=collectgarbage("count")*1024-base
local stats=B.Status()
coroutine.resume=resume;collectgarbage("restart");collectgarbage("collect")
for k,n in pairs(times)do times[k]=math.floor(n*1e6+.5)end
J.Encode=encode
print("BRIDGE_PROFILE "..J.Encode(setmetatable({
    phase_exclusive_us=setmetatable(times,J.OBJECT),calls=setmetatable(calls,J.OBJECT),
    largest_units=setmetatable(units,J.OBJECT),heap_before_collection=math.floor(heap),
    no_gc_experiment=arg[3]=="no-gc",validation_us=math.floor(stats.validation_ms*1000+.5),
    worst_step_us=math.floor(stats.largest_slice_ms*1000+.5),steps=stats.slices},J.OBJECT)))
