-- File-backed hook for the existing Opportunities benchmark. No reader/service replacement.
local X={};local c,W,J,B,P,Q,h,cfg,stats
local function read(path)local f=assert(io.open(path,'rb'));local v=f:read('*a');f:close();return v end
local function clock()return os.clock()*1000 end
function X.setup(client)
    c=client;W=c.TwichUI.Workshop;J,B,P,Q=W.BridgeCodec,W.Bridge,W.Pricing,W.Summary
    cfg=J.Parse(read(assert(arg[12])));stats={loads=0,history_loads=0,compile_ms=0,execute_ms=0,source_bytes=0,worst_load_ms=0,load_peak_kib=0}
    local root=assert(loadfile(cfg.publication..'/TwichUI_MarketData/Data.lua'));setfenv(root,c);root()
    h=J.Parse(c.TwichUIMarketData.manifest);assert(h.contract_version==3 and #h.observations==60)
    local _,at=W.BridgeValidate.Time(h.generated_at);c.time=function()return at+60 end
    c.C_AddOns.LoadAddOn=function(name)
        assert(name:match('^TwichUI_MarketPart[AB]%d%d$')or name:match('^TwichUI_MarketCurrentPart[AB]%d%d$')or name:match('^TwichUI_MarketHistoryPart[AB]%d%d$'))
        local began=clock();local source=read(cfg.publication..'/'..name..'/Data.lua')
        local at=clock();local fn=assert(loadstring(source,'@'..name..'/Data.lua'));setfenv(fn,c);stats.compile_ms=stats.compile_ms+clock()-at
        at=clock();fn();stats.execute_ms=stats.execute_ms+clock()-at
        stats.loads=stats.loads+1;stats.source_bytes=stats.source_bytes+#source
        if name:find('History',1,true)then stats.history_loads=stats.history_loads+1 end
        stats.worst_load_ms=math.max(stats.worst_load_ms,clock()-began);stats.load_peak_kib=math.max(stats.load_peak_kib,collectgarbage('count'))
        return true
    end
    local semantic={};for _,p in ipairs(h.partitions)do semantic[#semantic+1]=p.bucket..':'..p.sha256 end
    return h,c.TwichUIMarketData,{},{},J.SHA(table.concat(semantic,';'))
end
function X.recipes(count)
    local recipes,output={},1000
    for i=1,count do
        repeat output=output+1 until output%64<58
        recipes[i]={id=i,name='Synthetic craft '..i,prof=171,filled=true,outItem=output,outMin=1,outMax=1,
            mats={{item=65+i%38,qty=1+i%4},{item=65+(i*7)%38,qty=2+i%3}}}
    end
    local fields,items,buckets={},{},{}
    for _,r in ipairs(recipes)do
        fields[#fields+1]=r.id..':'..r.outItem..':'..r.mats[1].item..':'..r.mats[1].qty..':'..r.mats[2].item..':'..r.mats[2].qty
        items[r.outItem]=true;for _,m in ipairs(r.mats)do items[m.item]=true end
    end
    X.items=0;X.buckets=0;for id in pairs(items)do X.items=X.items+1;buckets[id%64]=true end;for _ in pairs(buckets)do X.buckets=X.buckets+1 end
    X.recipeSHA=J.SHA(table.concat(fields,';'));return recipes
end
function X.observe(view,elapsed,cpu,out)
    if out.prepared_visible_model_seconds then return end
    for i=1,math.min(12,#view.all)do local row=view.all[i];if not(row.done and row.owner:Valid(row))then return end end
    if #view.all==0 then return end
    out.prepared_visible_model_seconds=elapsed;out.prepared_visible_cpu_ms=cpu
end
function X.finish(out,event)
    out.prepared_layout=cfg.layout;out.prepared_production_reader=true;out.prepared_source_generation=h.generation_id
    out.prepared_recipe_sha256=X.recipeSHA;out.prepared_distinct_items=X.items;out.prepared_legacy_buckets=X.buckets
    out.compile_ms=stats.compile_ms;out.execute_ms=stats.execute_ms;out.loads=stats.loads;out.history_loads=stats.history_loads
    out.prepared_worst_load_ms=stats.worst_load_ms;out.prepared_load_peak_heap_kib=stats.load_peak_kib;out.prepared_source_bytes=stats.source_bytes
    local status=B.Status();for k,v in pairs(status.prepared or {})do out['prepared_'..k]=v end
    local bytes,history=0,0;for _,p in ipairs(h.partitions)do bytes=bytes+p.bytes end;for _,p in ipairs(h.history_partitions)do history=history+p.bytes end
    out.fixture_current_bytes=bytes;out.fixture_history_bytes=history;out.raw_fixture_bytes=bytes
    out.prepared_loaded_history_bytes=status.history_bytes;out.prepared_history_partitions=64
    local at=clock();for i=1,1000 do P.Price(65+i%38)end;out.prepared_warm_1000_prices_ms=clock()-at
    if cfg.history_probe then
        local before=stats.loads;local began=clock();B.History(1001,P.BaseKey(1001),'recent',{days=60})
        while Q.Pending()do event()end
        local series=assert(B.History(1001,P.BaseKey(1001),'recent',{days=60}));assert(#series.points==60)
        out.prepared_history_probe_cpu_ms=clock()-began;out.prepared_history_probe_loads=stats.loads-before
    end
end
return X
