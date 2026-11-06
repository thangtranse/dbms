import json
from ol import catalog as c


def legacy(item_id=1):
    template=json.loads((c.DATA/'demo.json').read_text())['dishes'][(item_id-1)%36]
    return dict(itemId=item_id,name=f"{template['name']} · Demo {item_id}",price=template['price'],
                categoryId=template['categoryId'],tags=template['tags'],
                image='https://images.unsplash.com/photo-1569718212165-3a8278d5f624',
                source='synthetic',metadataVersion='demo-catalog-v1',clusterId=5,x=3,y=4,modelVersion='original')


def test_snapshot_unique_sourced_and_unknown_prices():
    snapshot=c.catalog()
    assert len(snapshot['assignments'])>500
    for key in snapshot['assignments']:
        d=c.metadata(int(key))
        assert d['sourceUrl'].startswith('https://')
        assert d['image'].startswith('https://') and d['tags']
        assert d['price']==0 and d['priceStatus']=='unknown'
        assert d['mappingBasis']=='synthetic-research-id'
    assert c.metadata(2147483647)['source']=='unmapped'


def test_plan_preserves_edits_and_model():
    old=legacy()
    assert c.untouched_v1(old)
    edited=legacy(2) | {'name':'Món tôi đã sửa'}
    rows=c.plan([old,edited])
    assert len(rows)==1 and rows[0]['itemId']==1
    for k in ['clusterId','x','y','modelVersion']:
        assert rows[0][k]==old[k]
    assert c.plan(rows)==[]


def test_enrich_backup_and_batch_outbox(tmp_path):
    class DB:
        rows=[legacy()]
        statements=[]
        def docs(self,*args):return self.rows
        def table(self,name):return name
        def execute(self,sql,params=None,many=False):
            self.statements.append((sql,params,many))
            if sql.startswith('SELECT'): return [['dish:1']]
    db=DB()
    assert c.enrich(db)['eligible']==1
    assert db.statements==[]
    path=tmp_path/'before.json'
    result=c.enrich(db,apply=True,backup=path)
    assert result['applied'] and json.loads(path.read_text())==db.rows
    assert any('revision=revision+1' in sql and many for sql,_,many in db.statements)
