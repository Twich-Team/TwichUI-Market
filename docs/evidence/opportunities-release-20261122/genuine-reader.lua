-- Operator acceptance of genuine staged data through unchanged production Lua.
-- No actual Forever process, Windows installation, or frame-time claim.
require('bit')
REPO='/addon/'
TwichUI={Workshop={}};GetTimePreciseSec=os.clock
for _,name in ipairs({'Data','BridgeCodec','BridgeSchema','BridgeValidate','SummarySchema','Summary','Bridge'}) do dofile(REPO..'TwichUI_Workshop/'..name..'.lua') end
local W=TwichUI.Workshop;local Q,J,B=W.Summary,W.BridgeCodec,W.Bridge
local currentLoads,historyLoads=0,0
C_AddOns={LoadAddOn=function(name)
 assert(name:match('^TwichUI_MarketPart[AB]%d%d$')or name:match('^TwichUI_MarketHistoryPart[AB]%d%d$'))
 if name:find('History',1,true)then historyLoads=historyLoads+1 else currentLoads=currentLoads+1 end
 assert(loadfile('/publication/'..name..'/Data.lua'))();return true
end}
assert(loadfile('/publication/TwichUI_MarketData/Data.lua'))()
B.Begin(TwichUIMarketData)
while Q.Pending()do Q.Step(3)end
assert(B.Status().ready);local h=B.Manifest();assert(h.synthetic==false and h.contract_version==3)
local count=0;local co=coroutine.create(function()assert(B.EachItem(function()count=count+1 end,function()coroutine.yield()end))end)
local resumes=0
while coroutine.status(co)~='dead' do
 if Q.Pending()then Q.Step(3)end
 local ok,why=coroutine.resume(co);assert(ok,why);resumes=resumes+1;assert(resumes<3000000)
end
while Q.Pending()do Q.Step(3)end
assert(historyLoads==0 and Q.Status().history_bytes==0,'current enumeration loaded history')
local item=assert(tonumber(os.getenv('EXPECTED_ITEM')));local key=assert(os.getenv('EXPECTED_VARIANT'));local price=assert(tonumber(os.getenv('EXPECTED_PRICE')))
local value,reason=B.Value(item,key,'recent')
while not value and reason=='loading' do Q.Step(3);value,reason=B.Value(item,key,'recent')end
assert(value and value.value==price,'genuine current value did not settle')
local unknown=B.Value(2147483647,string.rep('0',64),'recent')
while Q.Pending()do Q.Step(3);unknown=B.Value(2147483647,string.rep('0',64),'recent')end
assert((unknown==nil or unknown.value==nil) and not Q.Pending(),'missing value invented or did not settle')
assert(historyLoads==0 and Q.Status().history_bytes==0,'current value lookup loaded history')
local series,why=B.History(item,key,'recent',{days=60})
while not series and why=='loading' do Q.Step(3);series,why=B.History(item,key,'recent',{days=60})end
assert(series and series.source=='market_server' and #series.points>0,'genuine chart unavailable')
assert(historyLoads==1,'explicit chart loaded incorrect history count')
print(J.Encode(setmetatable({synthetic=false,real_game=false,contract_version=3,generation=h.generation_id,declared_exact_variants=h.record_count,enumerated_item_ids=count,current_partition_loads=currentLoads,history_loads_before_chart=0,history_loads_after_chart=historyLoads,chart_points=#series.points,verified_item=item,verified_variant=key,verified_recent_copper=price,missing_prices_settled=true,mode='unchanged production Lua reader on genuine native-staged data; not actual Forever'},J.OBJECT)))
