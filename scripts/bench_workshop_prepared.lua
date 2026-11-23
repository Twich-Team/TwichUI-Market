-- File-backed hook for the existing Opportunities benchmark. No reader/service replacement.
local X={};local c,W,J,B,P,Q,h,cfg,stats
local function read(path)local f=assert(io.open(path,'rb'));local v=f:read('*a');f:close();return v end
local function clock()return os.clock()*1000 end
function X.setup(client)
    c=client;W=c.TwichUI.Workshop;J,B,P,Q=W.BridgeCodec,W.Bridge,W.Pricing,W.Summary
    local loadSamples={};X.loadSamples=loadSamples
    cfg=J.Parse(read(assert(arg[12])));if type(cfg.native_codec)=='string'then c.C_EncodingUtil=assert(package.loadlib(cfg.native_codec,'luaopen_market_codec_offline'))();c.Enum={CompressionMethod={Deflate=0}}end;stats={loads=0,history_loads=0,compile_ms=0,execute_ms=0,source_bytes=0,worst_load_ms=0,load_peak_kib=0}
    local at=clock();local source=read(cfg.publication..'/TwichUI_MarketData/Data.lua')
    local began=clock();local root=assert(loadstring(source,'@TwichUI_MarketData/Data.lua'));setfenv(root,c);stats.root_compile_ms=clock()-began
    began=clock();root();stats.root_execute_ms=clock()-began;stats.root_file_ms=clock()-at
    local step=Q.Step
    Q.Step=function(...)
        if stats.root_done then return step(...)end
        local before=clock();local ok,why=step(...)
        stats.root_validation_ms=(stats.root_validation_ms or 0)+clock()-before
        stats.root_slices=(stats.root_slices or 0)+1;stats.root_done=B.Status().ready
        return ok,why
    end
    h=J.Parse(c.TwichUIMarketData.manifest);assert(h.contract_version==3 and #h.observations==60)
    local _,at=W.BridgeValidate.Time(h.generated_at);c.time=function()return at+60 end
    c.C_AddOns.LoadAddOn=function(name)
        assert(name:match('^TwichUI_MarketPart[AB]%d%d$')or name:match('^TwichUI_MarketCurrentPart[AB]%d%d$')or name:match('^TwichUI_MarketHistoryPart[AB]%d%d$')or name:match('^TwichUI_MarketCurrentContainer[AB]%d%d$')or name:match('^TwichUI_MarketHistoryContainer[AB]%d%d$'))
        local before=collectgarbage('count');local began=clock();local source=read(cfg.publication..'/'..name..'/Data.lua');local readMS=clock()-began
        local at=clock();local fn=assert(loadstring(source,'@'..name..'/Data.lua'));setfenv(fn,c);local compileMS=clock()-at;stats.compile_ms=stats.compile_ms+compileMS
        at=clock();fn();local executeMS=clock()-at;stats.execute_ms=stats.execute_ms+executeMS
        stats.loads=stats.loads+1;stats.source_bytes=stats.source_bytes+#source
        if name:find('History',1,true)then stats.history_loads=stats.history_loads+1 end
        local duration=clock()-began;local after=collectgarbage('count')
        stats.worst_load_ms=math.max(stats.worst_load_ms,duration);stats.load_peak_kib=math.max(stats.load_peak_kib,after)
        loadSamples[#loadSamples+1]={name=name,total_ms=duration,read_ms=readMS,compile_ms=compileMS,execute_ms=executeMS,bytes=#source,heap_before_kib=before,heap_after_kib=after}
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
    local settled,priced=true,0
    for i=1,math.min(12,#view.all)do
        local row=view.all[i]
        if not(row.done and row.owner:Valid(row))then settled=false
        elseif row.est.state=='ok'then priced=priced+1 end
    end
    if #view.all==0 then return end
    if priced>0 and not out.prepared_first_visible_model_seconds then
        out.prepared_first_visible_model_seconds=elapsed;out.prepared_first_visible_cpu_ms=cpu
    end
    if settled then out.prepared_visible_model_seconds=elapsed;out.prepared_visible_cpu_ms=cpu end
end
function X.finish(out,event)
    out.root_compile_ms=stats.root_compile_ms;out.root_execute_ms=stats.root_execute_ms;out.root_file_ms=stats.root_file_ms
    out.root_validation_ms=stats.root_validation_ms;out.root_validation_slices=stats.root_slices;out.root_admission_model_seconds=stats.root_slices/60
    out.prepared_layout=cfg.layout;out.prepared_production_reader=true;out.prepared_source_generation=h.generation_id
    out.prepared_recipe_sha256=X.recipeSHA;out.prepared_distinct_items=X.items;out.prepared_legacy_buckets=X.buckets
    out.compile_ms=stats.compile_ms;out.execute_ms=stats.execute_ms;out.loads=stats.loads;out.history_loads=stats.history_loads
    out.prepared_worst_load_ms=stats.worst_load_ms;out.prepared_load_peak_heap_kib=stats.load_peak_kib;out.prepared_source_bytes=stats.source_bytes
    local status=B.Status();for k,v in pairs(status.containers or {})do out['container_'..k]=v end;for k,v in pairs(status.prepared or {})do out['prepared_'..k]=v end
    local bytes,history=0,0;for _,p in ipairs(h.partitions)do bytes=bytes+p.bytes end;for _,p in ipairs(h.history_partitions)do history=history+p.bytes end
    out.fixture_current_bytes=bytes;out.fixture_history_bytes=history;out.raw_fixture_bytes=bytes
    out.prepared_loaded_history_bytes=status.history_bytes;out.prepared_history_partitions=64
    local at=clock();for i=1,1000 do P.Price(65+i%38)end;out.prepared_warm_1000_prices_ms=clock()-at
    if cfg.history_probe then
        local before=stats.loads;local codec=B.Status().containers;local began=clock();B.History(1001,P.BaseKey(1001),'recent',{days=60})
        local worst=0;while Q.Pending()do local start=clock();event();worst=math.max(worst,clock()-start)end
        out.prepared_history_scheduler_step_max_ms=worst
        local series=assert(B.History(1001,P.BaseKey(1001),'recent',{days=60}));assert(#series.points==60)
        out.prepared_history_probe_cpu_ms=clock()-began;out.prepared_history_probe_loads=stats.loads-before
        local after=B.Status().containers
        if codec and after then
            out.history_inflate_ms=after.inflate_ms-codec.inflate_ms;out.history_base64_ms=after.base64_ms-codec.base64_ms
            out.history_inflates=after.inflates-codec.inflates;out.history_output_bytes=after.output_bytes-codec.output_bytes
        end
        local at=clock();local loads=stats.loads;B.History(1001,P.BaseKey(1001),'recent',{days=60})
        out.history_warm_ms=clock()-at;out.history_warm_loads=stats.loads-loads
    end
    -- The production JSON encoder deliberately accepts integer numbers only.
    -- Preserve fractional observations as decimal strings in this test receipt.
    out.physical_load_samples=J.Array()
    for _,sample in ipairs(X.loadSamples)do
        local row=J.Object()
        for key,value in pairs(sample)do row[key]=type(value)=='number'and ('%.6f'):format(value)or value end
        out.physical_load_samples[#out.physical_load_samples+1]=row
    end
end
return X
