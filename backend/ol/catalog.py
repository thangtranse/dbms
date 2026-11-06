"""Source-backed demo catalog. Recipe-to-research-ID mapping is synthetic."""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

VERSION = 'sourced-catalog-v2'
DATA = Path(__file__).resolve().parent.parent / 'data'
FIELDS = ('name', 'price', 'categoryId', 'tags', 'image', 'source', 'metadataVersion',
          'sourceUrl', 'sourceProvider', 'retrievedAt', 'mappingBasis', 'priceStatus', 'categoryBasis', 'suggestedCategoryId')


def normalized(name):
    return ' '.join(re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFKC', name).casefold()).split())


@lru_cache(maxsize=1)
def catalog():
    snapshot = json.loads((DATA / 'catalog-v2.json').read_text())
    assignments = snapshot['assignments']
    names = [normalized(d['name']) for d in assignments.values()]
    images = [d['image'] for d in assignments.values()]
    if len(names) != len(set(names)) or len(images) != len(set(images)):
        raise ValueError('Duplicate recipe names or image URLs')
    return snapshot


def metadata(item_id):
    snapshot = catalog()
    r = snapshot['assignments'].get(str(item_id))
    if r is None:
        return dict(name=f'Item #{item_id}', price=0, categoryId=None, tags=[], image='', source='unmapped')
    return dict(name=r['name'], price=0, categoryId=None, suggestedCategoryId=r['categoryId'], tags=r['tags'], image=r['image'],
                source='sourced-demo', metadataVersion=VERSION, sourceUrl=r['sourceUrl'],
                sourceProvider=r['provider'], retrievedAt=snapshot['retrievedAt'],
                mappingBasis='synthetic-research-id', priceStatus='unknown', categoryBasis='pending-review')


def untouched_v1(d):
    if d.get('metadataVersion') != 'demo-catalog-v1' or d.get('source') != 'synthetic': return False
    template = json.loads((DATA / 'demo.json').read_text())['dishes'][(d['itemId']-1)%36]
    images=['1569718212165-3a8278d5f624','1512621776951-a57141f2eefd','1569718212165-3a8278d5f624',
            '1550547660-d9450f859349','1546069901-ba9599a7e63c','1512621776951-a57141f2eefd','1556679343-c7306c1976bc']
    expected=dict(name=f"{template['name']} · Demo {d['itemId']}", price=template['price'],
                  categoryId=template['categoryId'],tags=template['tags'],image='https://images.unsplash.com/photo-'+images[template['categoryId']])
    return all(d.get(k)==v for k,v in expected.items())


def plan(docs):
    eligible=[d for d in docs if untouched_v1(d) or (d.get('source')=='unmapped' and d.get('name')==f"Item #{d['itemId']}" and not d.get('price') and not d.get('image') and not d.get('tags') and d.get('categoryId') is None)]
    ids={d['itemId'] for d in eligible}
    reserved_names={normalized(d['name']) for d in docs if d['itemId'] not in ids}
    reserved_images={d.get('image') for d in docs if d['itemId'] not in ids and d.get('image')}
    updates=[]
    for old in eligible:
        m=metadata(old['itemId'])
        if m['source']!='unmapped' and (normalized(m['name']) in reserved_names or m['image'] in reserved_images):
            m=dict(name=f"Item #{old['itemId']}", price=0,categoryId=None,tags=[],image='',source='unmapped')
        d={k:v for k,v in old.items() if k not in FIELDS} | m
        d['vectorStatus']='pending'
        # Already-unmapped items are not queued again.
        if any(old.get(k)!=d.get(k) for k in FIELDS): updates.append(d)
    return updates


def enrich(db, apply=False, backup=None):
    from .db import dumps
    docs=db.docs('dishes','WHERE active_flag=1')
    updates=plan(docs)
    if apply:
        if backup is None: raise ValueError('A backup path is required')
        with Path(backup).open('x') as f: json.dump(docs,f,ensure_ascii=False)
        db.execute(f"UPDATE {db.table('dishes')} SET price=?,category_id=?,doc=? WHERE item_id=?",
                   [[d['price'],d['categoryId'],dumps(d),d['itemId']] for d in updates], many=True)
        existing={r[0] for r in db.execute(f"SELECT entity_id FROM {db.table('outbox')}")}
        events=[[dumps(dict(kind='dish',id=d['itemId'],action='upsert')),f"dish:{d['itemId']}"] for d in updates]
        db.execute(f"UPDATE {db.table('outbox')} SET revision=revision+1,attempts=0,last_error=NULL,doc=? WHERE entity_id=?",
                   [r for r in events if r[1] in existing],many=True)
        db.execute(f"INSERT INTO {db.table('outbox')} VALUES (?,1,0,0,NULL,?)",
                   [[key,doc] for doc,key in events if key not in existing],many=True)
    return dict(total=len(docs),eligible=len(updates),sourced=sum(d['source']=='sourced-demo' for d in updates),
                restoredUnmapped=sum(d['source']=='unmapped' for d in updates),applied=apply,version=VERSION)


def sync_catalog_batch(backup):
    """Maintenance-only: API/worker stopped; preserve existing vectors verbatim."""
    from contextlib import closing
    from qdrant_client import models as qm
    from .config import qclient, ARTIFACTS
    from .db import session
    active=json.loads((ARTIFACTS/'active.json').read_text())
    with session() as db:
        docs=[d for d in db.docs('dishes','WHERE active_flag=1') if d.get('metadataVersion')==VERSION]
        revisions={key:int(rev) for key,rev in db.execute(f"SELECT entity_id,revision FROM {db.table('outbox')}")}
    ids=[d['itemId'] for d in docs]
    records=[]
    with closing(qclient()) as q:
        for start in range(0,len(ids),128):
            records.extend(q.retrieve(active['dishes'],ids=ids[start:start+128],with_vectors=True,with_payload=True))
        by_id={p.id:p for p in records}
        if set(by_id)!=set(ids): raise ValueError('Existing Qdrant vectors missing; refuse to invent vectors')
        if any(p.payload.get('modelVersion')!=d.get('modelVersion') for d in docs for p in [by_id[d['itemId']]]):
            raise ValueError('Model version mismatch')
        with Path(backup).open('x') as f:
            json.dump([p.model_dump() for p in records],f,ensure_ascii=False)
        points=[]
        for d in docs:
            p=by_id[d['itemId']]
            payload=p.payload | dict(price=d['price'],categoryId=d['categoryId'],tags=d['tags'],source=d['source'],
                active=True,mapped=d['categoryId'] is not None and d['price']>0,
                revision=revisions[f"dish:{d['itemId']}"],priceStatus='unknown',sourceUrl=d['sourceUrl'])
            points.append(qm.PointStruct(id=p.id,vector=p.vector,payload=payload))
        for start in range(0,len(points),128):
            q.upsert(active['dishes'],points[start:start+128],wait=True)
        # Acknowledge only the exact revision published above.
        with session() as db:
            db.execute(f"UPDATE {db.table('outbox')} SET applied=?,attempts=0,last_error=NULL WHERE entity_id=? AND revision=?",
                       [[revisions[f'dish:{i}'],f'dish:{i}',revisions[f'dish:{i}']] for i in ids],many=True)
    return dict(synchronized=len(points),vectorsPreserved=True,unknownPricesExcluded=True)
