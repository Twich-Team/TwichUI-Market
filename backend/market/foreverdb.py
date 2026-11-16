"""Mappings verified against authenticated ForeverDB v1 responses, 2026-11-16.

Original JSON evidence and source qualifiers are retained. No variant or market
price inference. Related resource imports reuse the versioned item source catalog.
"""
import json
import math
import re
from .metadata_providers import IdentityMismatch, build_identity, decode, plain, source

MAPPING_VERSION = 2
PROFESSIONS = ('alchemy','blacksmithing','enchanting','engineering','leatherworking','tailoring','herbalism','mining','skinning','cooking','first-aid','fishing')
RELATED = re.compile(r'(?:professions/(?:'+'|'.join(PROFESSIONS)+r')|vendors/[1-9][0-9]*|itemsets/[1-9][0-9]*)')


def integer(value, minimum=0, maximum=2**31-1):
    if type(value) is not int or not minimum <= value <= maximum: raise ValueError('Invalid ForeverDB integer')
    return value


def effect_text(value):
    if not isinstance(value,str) or len(value)>4096:raise ValueError('Invalid effect text')
    return safe_json(value)


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 10**12:
        raise ValueError('Invalid ForeverDB number')
    return str(value)


def safe_json(value, *, depth=0):
    """Bound structured evidence without discarding unknown optional source fields."""
    if depth > 16: raise ValueError('ForeverDB nesting limit')
    if value is None or type(value) is bool: return value
    if type(value) is int:
        if abs(value)>2**63-1: raise ValueError('ForeverDB integer overflow')
        return value
    if type(value) is float:
        if not math.isfinite(value): raise ValueError('Nonfinite ForeverDB number')
        return value
    if isinstance(value,str):
        if len(value)>16384 or any(ord(c)<32 and c not in '\n\t\r' for c in value): raise ValueError('Invalid ForeverDB text')
        return value
    if isinstance(value,list) and len(value)<=1000:return [safe_json(v,depth=depth+1) for v in value]
    if isinstance(value,dict) and len(value)<=100:
        if any(not isinstance(k,str) or len(k)>100 for k in value): raise ValueError('Invalid ForeverDB field')
        return {k:safe_json(v,depth=depth+1) for k,v in value.items()}
    raise ValueError('Invalid ForeverDB structured data')


def envelope(body, *, at=None, resource):
    value=decode(body); row,meta=value.get('data'),value.get('meta')
    if not isinstance(meta,dict) or meta.get('edition','forever')!='forever':raise IdentityMismatch('ForeverDB edition mismatch')
    build=build_identity(meta.get('build'))
    origin=source('foreverdb',body,build=build,confidence='client_record_unverified',at=at,
        attribution={'text':'Data from ForeverDB.net','url':'https://foreverdb.net'},
        url='https://foreverdb.net/api/v1/'+resource)
    origin.update(resource=resource,mapping_version=MAPPING_VERSION,current_build=build)
    return row,meta,origin


def item(body,item_id,*,at=None):
    row,meta,origin=envelope(body,at=at,resource=f'items/{item_id}')
    if not isinstance(row,dict) or type(row.get('id')) is not int or row['id']!=item_id:raise IdentityMismatch('ForeverDB item identity mismatch')
    safe_json(row)
    fields={'name':plain(row.get('name'))}
    origin.update(resource_id=item_id,record=row,item_mapping_version=MAPPING_VERSION,item_build=origin['current_build'])
    from .item_media import icon_url
    if icon_url(row.get('icon'),foreverdb=True):origin['icon_url']=row['icon']
    for src,dst in [('class','class'),('subclass','subclass'),('inventoryType','slot'),('bonding','binding')]:
        if row.get(src) is not None:fields[dst]=plain(row[src])
    quality=row.get('quality')
    if quality is not None:
        from .item_attributes import QUALITIES
        quality=plain(quality).upper()
        if quality not in QUALITIES:raise ValueError('Invalid ForeverDB quality')
        fields['quality']=quality
    for src,dst in [('itemLevel','level'),('requiredLevel','required_level')]:
        if row.get(src) is not None:fields[dst]=integer(row[src],maximum=10000)
    if row.get('sellPrice') is not None:fields['vendor_sell']=str(integer(row['sellPrice'],maximum=2**63-1))
    ids={k:integer(row[k]) for k in ('classId','subclassId','inventoryTypeId','qualityId') if row.get(k) is not None}
    if ids:fields['category_ids']=ids
    if row.get('unique') is not None:
        if type(row['unique']) is not bool:raise ValueError('Invalid uniqueness')
        fields['unique']=row['unique']
    stats=row.get('stats')
    if stats is not None:
        if not isinstance(stats,list) or len(stats)>40:raise ValueError('Invalid ForeverDB stats')
        fields['stats']=[{'stat_id':integer(s['statId']), 'label':plain(s['stat']),
            'value':integer(s['value'],minimum=-2**31)} for s in stats]
    weapon={}
    if row.get('damage') is not None:
        damage=row['damage']
        weapon['damage']={'min':number(damage['min']),'max':number(damage['max']),'school':plain(damage['school'])}
        if float(weapon['damage']['min'])>float(weapon['damage']['max']):raise ValueError('Reversed weapon damage')
    if row.get('speed') is not None:weapon['speed_seconds']=number(row['speed'])
    if weapon:fields['weapon']=weapon
    effects=row.get('effects')
    if effects is not None:
        if not isinstance(effects,list) or len(effects)>40:raise ValueError('Invalid ForeverDB effects')
        fields['effects']=[{'spell_id':integer(e['spellId'],minimum=1),'trigger_id':integer(e['triggerId']),
            'trigger':plain(e['trigger']), 'text':effect_text(e['text'])} for e in effects]
    if row.get('disenchantable') is not None:
        if type(row['disenchantable']) is not bool:raise ValueError('Invalid disenchant flag')
        fields['disenchantable']=row['disenchantable']
    if row.get('disenchant') is not None:
        de=row['disenchant']
        if not isinstance(de,dict) or not isinstance(de.get('source'),str):raise ValueError('Unqualified disenchant data')
        fields['disenchant']=safe_json(de)
    qualifiers={k:safe_json(row[k]) for k in ('betaEvent','speculation','speculationReasons','dataFromBuild','liveClient') if k in row}
    for key in ('betaEvent','speculation'):
        if key in qualifiers and type(qualifiers[key]) is not bool:raise ValueError('Invalid availability flag')
    if qualifiers:
        fields['availability']=qualifiers;origin['qualifiers']=qualifiers
    if row.get('dataFromBuild') is not None:
        origin['build']=build_identity(row['dataFromBuild'])
        origin['confidence']='retained_earlier_build'
    elif row.get('betaEvent') or row.get('speculation'):
        origin['confidence']='availability_unconfirmed'
    return fields,origin


def needs_detail(record, current_build=None):
    if record.provider!='foreverdb' or record.status!='available' or not record.fields_json:return False
    origin=json.loads(record.source_json or '{}')
    return origin.get('item_mapping_version',0)<MAPPING_VERSION or bool(current_build and origin.get('item_build')!=current_build)


def related(body,resource,*,at=None):
    """Project a bounded recipe/vendor/set response onto its exact related items.

    Each relationship retains its own source. No guessed item names, categories,
    drop chances or currency conversion enter the base-item projection.
    """
    if not RELATED.fullmatch(resource):raise ValueError('Unsupported related resource')
    row,meta,origin=envelope(body,at=at,resource=resource)
    if not isinstance(row,dict):raise ValueError('Invalid related resource')
    safe_json(row)
    records={}
    def add(ident,key,entry):
        ident=integer(ident,minimum=1)
        records.setdefault(ident,{}).setdefault(key,[]).append(entry)
    if resource.startswith('professions/'):
        if row.get('slug')!=resource.split('/')[1] or not isinstance(row.get('recipes'),list):raise IdentityMismatch('Profession identity mismatch')
        for recipe in row['recipes']:
            integer(recipe.get('spellId'),minimum=1);plain(recipe.get('name'))
            reagents=recipe.get('reagents')
            if not isinstance(reagents,list):raise ValueError('Invalid recipe reagents')
            ids=set()
            for reagent in reagents:
                ids.add(integer(reagent['itemId'],minimum=1));integer(reagent['count'],minimum=1)
            makes=recipe.get('makes')
            if makes:
                ids.add(integer(makes['itemId'],minimum=1))
                for k in ('count','min','max'):
                    if makes.get(k) is not None:integer(makes[k],minimum=1)
            learned=recipe.get('learnedFrom') or {}
            for entry in learned.get('recipeItems') or []:
                ids.add(integer(entry['itemId'],minimum=1))
            value={'profession':row['slug'],'profession_name':plain(row['name']), 'recipe':recipe,'source':origin}
            for ident in ids:add(ident,'crafting',value)
    elif resource.startswith('vendors/'):
        if type(row.get('id')) is not int or row['id']!=int(resource.split('/')[1]) or not isinstance(row.get('sells'),list):raise IdentityMismatch('Vendor identity mismatch')
        vendor={k:v for k,v in row.items() if k!='sells'}
        for sale in row['sells']:
            if sale.get('price') is not None:integer(sale['price'],maximum=2**63-1)
            if sale.get('stack') is not None:integer(sale['stack'],minimum=1)
            offer={**sale}
            if sale.get('price') is not None:offer['price_copper']=str(sale['price'])
            if sale.get('pricePerItem') is not None:offer['price_per_item_copper']=number(sale['pricePerItem'])
            add(sale['itemId'],'vendors',{'vendor':vendor,'offer':offer,'source':origin})
    else:
        if type(row.get('id')) is not int or row['id']!=int(resource.split('/')[1]) or not isinstance(row.get('items'),list):raise IdentityMismatch('Item set identity mismatch')
        for ident in row['items']:add(ident,'item_sets',{'set':row,'source':origin})
    return records,origin
