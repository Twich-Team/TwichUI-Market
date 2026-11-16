-- Offline CPU/allocation probe only. Inputs are benchmark-owned, generated
-- assignment-only artifacts. Never run against installed player data.
require("bit")
local root,artifact,repeatLoad=assert(arg[1]),assert(arg[2]),arg[3]=="repeat"
local began=os.clock()
TwichUI={Workshop={}}
TwichUIDB={profile="preserved"}
TwichUIWorkshopDB={markets={localScan={items={[2589]="original"},h2={[2589]="local-history"}}}}
GetTimePreciseSec=os.clock
os.execute=function()error("unexpected OS action")end
io.popen=function()error("unexpected process action")end
CreateFrame=function()error("unexpected frame")end
C_AuctionHouse=setmetatable({},{__index=function()return function()error("unexpected auction action")end end})
for _,name in ipairs({"Data","BridgeCodec","BridgeSchema","BridgeValidate","Bridge"})do dofile(root.."/TwichUI_Workshop/"..name..".lua")end
local moduleUS=math.floor((os.clock()-began)*1e6+.5)
local B,J=TwichUI.Workshop.Bridge,TwichUI.Workshop.BridgeCodec
local function us(n)return math.floor(n*1e6+.5)end
local function gc()
    local at=os.clock();collectgarbage("collect");return us(os.clock()-at)
end
gc();local base=collectgarbage("count")*1024
began=os.clock();local assign=assert(loadfile(artifact));local compileUS=us(os.clock()-began)
began=os.clock();assign();local assignmentUS=us(os.clock()-began);assign=nil
assert(M15_EXECUTED==nil,"server text escaped the assignment-only payload")
gc();local payloadHeap=collectgarbage("count")*1024-base
local function drain(raw)
    local at=os.clock();local previous=B.Status();local worst,steps,peak,collections=0,0,collectgarbage("count")*1024,0
    local oldHeap=peak
    B.Begin(raw)
    for i=1,10000000 do
        local started=os.clock();local ok,why=B.Step(3);local elapsed=us(os.clock()-started)
        worst=math.max(worst,elapsed);steps=steps+1
        local heap=collectgarbage("count")*1024;peak=math.max(peak,heap);if heap<oldHeap then collections=collections+1 end;oldHeap=heap
        if why~="loading" then assert(ok,why);break end
        assert(B.Status().generation==previous.generation,"partial generation published")
        assert(i<10000000,"unbounded validation")
    end
    return {validation_total_us=us(os.clock()-at),worst_step_us=worst,steps=steps,peak_heap_bytes=math.floor(peak),
        observed_heap_decreases=collections}
end
local result=drain(TwichUIMarketData)
result.explicit_gc_us=gc()
result.retained_heap_bytes=math.floor(collectgarbage("count")*1024-base)
result.payload_heap_bytes=math.floor(payloadHeap)
result.module_load_us=moduleUS;result.compile_us=compileUS;result.assignment_us=assignmentUS
result.generation_id=B.Status().generation;result.indexed_records=B.Status().records;result.indexed_items=B.Status().items
result.resumes=B.Status().resumes or 0
local h=B.Manifest();assert(h.synthetic and result.indexed_records==h.record_count)
local probes={1,math.ceil(h.record_count/2),h.record_count}
local lookups,histories={},{}
for _,position in ipairs(probes)do
    local expected=J.Parse(TwichUIMarketData.records[position])
    began=os.clock();local r=assert(B.Record(expected.item_id,expected.variant_key));lookups[#lookups+1]=us(os.clock()-began)
    assert(J.Encode(r)==TwichUIMarketData.records[position],"exact record changed")
    began=os.clock();local history=assert(B.History(r.item_id,r.variant_key,"recent",{days=60}));histories[#histories+1]=us(os.clock()-began)
    assert(#history.points==#r.daily and history.generation==h.generation_id)
    for i,p in ipairs(history.points)do
        local d=r.daily[i];local o=h.observations[d.observation_ref+1]
        assert(p.at==o.observed_at and p.state==d.state)
        if d.recent_copper==J.NULL then assert(p.v==nil)else assert(d.recent_copper=="100" and p.copper=="100" and p.v==100)end
    end
end
result.lookup_us=setmetatable(lookups,J.ARRAY);result.history_us=setmetatable(histories,J.ARRAY)
gc();local navigationHeap=collectgarbage("count")*1024
began=os.clock()
for loop=1,2 do
    for i=1,math.min(100,h.record_count)do
        local r=J.Parse(TwichUIMarketData.records[i])
        assert(B.Record(r.item_id,r.variant_key));assert(B.History(r.item_id,r.variant_key,"recent",{days=60}))
    end
end
result.navigation_reads_us=us(os.clock()-began);gc()
result.cache_growth_bytes=math.floor(collectgarbage("count")*1024-navigationHeap);result.cache_entries=B.Status().cache_entries
assert(result.cache_entries<=24)
if repeatLoad then
    assert(loadfile(artifact))()
    result.repeat_validation_us=drain(TwichUIMarketData).validation_total_us
    gc();result.repeat_retained_heap_bytes=math.floor(collectgarbage("count")*1024-base)
    assert(B.Status().generation==h.generation_id)
end
-- Corruption still runs through the full reader and keeps its preceding snapshot.
local bad={transport_version=1,manifest=TwichUIMarketData.manifest,receipt=TwichUIMarketData.receipt,records={}}
for i,text in ipairs(TwichUIMarketData.records)do bad.records[i]=text end
bad.records[1]=bad.records[1].."x";B.Begin(bad)
for i=1,10000000 do local ok,why=B.Step(3);if why~="loading"then assert(not ok);break end;assert(i<10000000)end
assert(B.Status().generation==h.generation_id)
assert(TwichUIWorkshopDB.markets.localScan.items[2589]=="original" and TwichUIWorkshopDB.markets.localScan.h2[2589]=="local-history" and TwichUIDB.profile=="preserved")
result.corruption_rejected=true;result.local_data_unchanged=true
print("BRIDGE_LUA "..J.Encode(setmetatable(result,J.OBJECT)))
