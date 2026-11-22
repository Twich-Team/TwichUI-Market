-- Actual native-published files, consumed by unchanged production modules.
local c=dofile(TESTS..'auction_mock.lua');local W=c.TwichUI.Workshop
local B,Q,J,P=W.Bridge,W.Summary,W.BridgeCodec,W.Pricing
local root=assert(os.getenv('WORKSHOP_SUMMARY_ARTIFACT'));local directory=assert(os.getenv('WORKSHOP_SUMMARY_PARTS'))
local function execute(path)local fn=assert(loadfile(path));setfenv(fn,c);fn()end
execute(root);local expected=assert(tonumber(os.getenv('WORKSHOP_PREPARED_EXPECTED_LAYOUT')))
assert(c.TwichUIMarketData.summary_version==(expected>0 and 2 or 1))
local h=J.Parse(c.TwichUIMarketData.manifest)
if expected>0 then assert(J.Parse(c.TwichUIMarketData.prepared).partitions_count==expected)end
local _,at=W.BridgeValidate.Time(h.generated_at);c.time=function()return at+60 end
c.GetTimePreciseSec=os.clock;c.UnitFactionGroup=function()return 'Horde'end
c.C_Item.GetItemInfo=function(id)return 'Synthetic '..id,'item:'..id,1,1,1,'Trade Goods','',1,'',134572,0 end
local events,loads={},{};c.C_Timer.After=function(_,fn)events[#events+1]=fn end
c.C_AddOns.LoadAddOn=function(name)
    assert(name:match('^TwichUI_MarketPart[AB]%d%d$')or name:match('^TwichUI_MarketCurrentPart[AB]%d%d$')or name:match('^TwichUI_MarketHistoryPart[AB]%d%d$'))
    loads[#loads+1]=name;execute(directory..'/'..name..'/Data.lua');return true
end
local function drain()
    for _=1,20000 do if #events==0 then assert(not Q.Pending());return end;local batch=events;events={};for _,fn in ipairs(batch)do fn()end end
    error('unbounded native artifact completion')
end
B.Begin(c.TwichUIMarketData);drain();assert((B.Status().prepared_version==1)==(expected>0)and #loads==0)
P.Price(2589);P.Price(10000);P.Price(123);drain()
assert(P.Price(2589).price==120 and P.Price(10000).price==120 and not P.Price(123)and P.PendingCount()==0)
assert(B.Status().history_loaded_parts==0);if expected>0 then assert(B.Status().decoded_current_rows==0)end
B.Variants(2589);drain();local variants=B.Variants(2589);assert(#variants==2)
local absent=J.SHA('not a delivered variant');B.Record(2589,absent,{current=true});drain()
local _,why=B.Record(2589,absent,{current=true});assert(why=='not_observed')
B.History(2589,P.BaseKey(2589));drain()
local history=assert(B.History(2589,P.BaseKey(2589)));assert(#history.points==#h.observations and history.points[#history.points].v==120)
local recipes={};for i=1,20 do recipes[i]={id=i,name='Synthetic '..i,prof=171,filled=true,outItem=10000+i%20,outMin=1,outMax=1,mats={{item=2589,qty=1+i%3}}}end
W.Session.AllRecipes=function()return recipes end
W.UI.Redraw=function()W.Session.Opportunities()end
local view=W.Session.Opportunities();drain();view=W.Session.Opportunities();assert(not view.calculating and view.summary.priced==20)
local full=W.Opps.Rows(recipes,view.lookup,view.rate,nil,W.Estimate.New(view.estimator.ctx))
local by={};for _,row in ipairs(full)do by[row.rec.id]=row.est end
for _,row in ipairs(view.all)do local e=by[row.rec.id];assert(row.est.cost==e.cost and row.est.sellLow==e.sellLow and row.est.profitLow==e.profitLow)end
local before=B.Status().prepared and B.Status().prepared.hashes;local lookups=B.Status().lookup_calls
W.Session.Opportunities();drain();assert(B.Status().lookup_calls==lookups,'warm catalog repeated reader lookups')
if before then assert(B.Status().prepared.hashes==before,'valid warm cache repeated verification')end
print('PASSED actual native layout '..expected..' publication -> production current/history readers -> incremental Opportunities; '..#h.observations..' days')
