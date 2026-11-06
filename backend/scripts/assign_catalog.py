"""Stable, explicit demo mapping; never cycle recipes to fill missing IDs."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ol.catalog import normalized


def main():
    path=ROOT/'data/catalog-v2.json'
    snapshot=json.loads(path.read_text())
    seeds=json.loads((ROOT/'data/demo.json').read_text())['dishes']
    names={normalized(d['name']) for d in seeds}
    images={d['image'] for d in seeds}
    candidates=[r for r in snapshot['recipes'] if normalized(r['name']) not in names and r['image'] not in images]
    all_ids=sorted({int(i) for line in (ROOT.parent/'office-lunch/pipeline/data/food.txt').read_text().splitlines() for i in line.split('\t')[1].split()})
    seed_ids={d['itemId'] for d in seeds}
    targets=[i for i in all_ids if i not in seed_ids]
    snapshot['assignments']={str(i):r for i,r in zip(targets,candidates)}
    snapshot['unassignedItemIds']=targets[len(candidates):]
    path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    print('assignments',len(snapshot['assignments']),'unassigned',len(snapshot['unassignedItemIds']))
    print('source providers', {p:sum(r['provider']==p for r in snapshot['assignments'].values()) for p in ['Cookbeo','TheMealDB']})
if __name__=='__main__':main()
