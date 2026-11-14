"""Extract plain verified base-item facts; never interpret remote HTML or infer bonuses."""
import json,re
QUALITIES={'POOR','COMMON','UNCOMMON','RARE','EPIC','LEGENDARY','ARTIFACT','HEIRLOOM','WOW_TOKEN'}


def text(value,limit=512):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 and c not in '\n\t' for c in value):return None
    return value.strip()


def attributes(payload):
    preview=payload.get('preview_item') or {}
    if not isinstance(preview,dict):raise ValueError('Invalid item preview')
    linked=preview.get('item',{})
    if isinstance(linked,dict) and 'id' in linked and linked['id']!=payload['id']:raise ValueError('Preview identity mismatch')
    quality=payload.get('quality',{})
    quality=quality.get('type') if isinstance(quality,dict) else None
    if quality is not None and quality not in QUALITIES:raise ValueError('Unknown item quality')
    result={'quality':quality,'scope':'base_item','lines':[]}
    def line(value,kind='attribute'):
        value=text(value)
        if value and len(result['lines'])<40:result['lines'].append({'text':value,'kind':kind})
    for field in ['binding','unique_equipped','inventory_type','item_subclass']:
        value=preview.get(field,payload.get(field))
        if isinstance(value,dict):line(value.get('name'))
    for field in ['level','required_level']:
        value=payload.get(field)
        if type(value) is int and 0<=value<=10000:result[field]=value
    weapon=preview.get('weapon')
    if isinstance(weapon,dict):
        for field in ['damage','attack_speed','dps']:
            value=weapon.get(field)
            if isinstance(value,dict):line(value.get('display_string'))
    armor=preview.get('armor')
    if isinstance(armor,dict):line(armor.get('display',{}).get('display_string') if isinstance(armor.get('display'),dict) else armor.get('display_string'))
    for entry in (preview.get('stats') or [])[:20]:
        if isinstance(entry,dict):
            display=entry.get('display',{})
            if isinstance(display,dict):line(display.get('display_string'),'stat')
    for field in ['requirements','durability','description','spells','socket_bonus']:
        value=preview.get(field)
        if isinstance(value,str):line(value,'flavor' if field=='description' else 'attribute')
        elif isinstance(value,dict):
            line(value.get('display_string'))
            for detail in ['level','skill','reputation']:
                nested=value.get(detail)
                if isinstance(nested,dict):line(nested.get('display_string'))
        elif isinstance(value,list):
            for entry in value[:10]:
                if isinstance(entry,dict):line(entry.get('description'),'effect')
    sell=payload.get('sell_price')
    if type(sell) is int and 0<=sell<=2**63-1:result['vendor_sell']=str(sell)
    return result


def valid_namespace(value,region):
    return isinstance(value,str) and len(value)<=100 and re.fullmatch(r'static-(?:[0-9._]+-)?forever-'+region,value) is not None
