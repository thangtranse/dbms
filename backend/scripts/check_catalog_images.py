"""Check source image headers, with an auditable result cache."""
import concurrent.futures as cf
import json
import time
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'data/catalog-v2.json'
CACHE=ROOT.parent/'.runtime/catalog-sources/image-checks.json'


def main():
    data=json.loads(PATH.read_text()); cached=json.loads(CACHE.read_text()) if CACHE.exists() else {}
    urls=sorted({r['image'] for r in data['recipes']})
    def check(url):
        if url in cached:return url,cached[url]
        error=''
        for attempt in range(2):
            try:
                req=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'OfficeLunchDemoCatalog/2.0'})
                with urllib.request.urlopen(req,timeout=12) as r:
                    if r.status==200 and r.headers.get('Content-Type','').startswith('image/'):
                        return url,dict(status=200,contentType=r.headers['Content-Type'])
                    error=str(r.status)
            except Exception as e:error=str(e)
        return url,dict(error=error)
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for i,(url,result) in enumerate(pool.map(check,urls),1):
            cached[url]=result
            if i%200==0:
                CACHE.write_text(json.dumps(cached));print('Image checks',i,'/',len(urls),flush=True)
    CACHE.write_text(json.dumps(cached))
    bad={u for u in urls if cached[u].get('status')!=200}
    data['imageChecks']=dict(checkedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),passed=len(urls)-len(bad),failed=len(bad))
    data['recipes']=[r for r in data['recipes'] if r['image'] not in bad]
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Image checks complete',data['imageChecks'],flush=True)

if __name__=='__main__':main()
