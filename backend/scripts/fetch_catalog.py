"""Fetch public recipe metadata only; no article text or cooking instructions."""
import concurrent.futures as cf
import hashlib
import json
import re
import string
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT.parent / '.runtime/catalog-sources'
CACHE.mkdir(parents=True, exist_ok=True)


def fetch(url):
    file = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if file.exists():
        return json.loads(file.read_text())
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'OfficeLunchDemoCatalog/2.0'})
            with urllib.request.urlopen(req, timeout=25) as r:
                content = r.read().decode()
            if 'cookbeo.com/recipes/' in url:
                matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', content, re.S)
                obj = next(json.loads(x) for x in matches if json.loads(x).get('@type') == 'Recipe')
                # Persist only factual identifiers/categories and image URLs.
                obj = {k:obj.get(k) for k in ['name', 'image', 'recipeCategory', 'recipeCuisine']}
            else:
                obj = json.loads(content)
                obj = [{k:v for k,v in m.items() if k in ['idMeal','strMeal','strMealThumb','strArea','strCategory','strTags'] or k.startswith('strIngredient')}
                       for m in obj.get('meals') or []]
            file.write_text(json.dumps(obj, ensure_ascii=False))
            time.sleep(.15)
            return obj
        except Exception:
            if attempt == 2: raise
            time.sleep(1 + attempt)


def norm(s):
    return ' '.join(re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFKC', s).casefold()).split())


def category(name, tags, source_category=''):
    text = norm(name)
    if source_category == 'Dessert' or re.match(r'^(chè|kem|sinh tố|nước ép|trà|sữa chua|bánh flan|mứt)\b', text): return 6
    if re.search(r'\b(chay|vegan)\b', text) or source_category in ['Vegan','Vegetarian']: return 5
    if re.match(r'^(salad|poke)\b', text): return 4
    if re.match(r'^(xôi|bánh mì|bánh bao)\b', text): return 3
    if re.match(r'^(bún|mì|miến|phở|hủ tiếu)\b', text) and re.search(r'\b(trộn|xào|khô)\b', text): return 2
    if re.match(r'^(canh|súp|cháo|lẩu|phở|bún|hủ tiếu|bánh canh)\b', text): return 0
    if re.match(r'^cơm\b', text): return 1
    return None  # Existing categories do not cover every standalone recipe.


def main():
    urls = [e.text for e in ET.parse(CACHE/'cookbeo-sitemap.xml').findall('.//{*}loc') if '/recipes/' in e.text]
    candidates=[]; errors=[]
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch,u):u for u in urls}
        for i,f in enumerate(cf.as_completed(futures),1):
            url=futures[f]
            try:
                r=f.result(); images=r.get('image') or []
                if isinstance(images,str): images=[images]
                tags=r.get('recipeCategory') or []
                if isinstance(tags,str): tags=[tags]
                candidates.append(dict(name=r['name'],image=images[0],tags=tags[:20],sourceUrl=url,provider='Cookbeo',cuisine=r.get('recipeCuisine')))
            except Exception as e: errors.append(dict(url=url,error=str(e)))
            if i%100==0: print('Cookbeo',i,'/',len(urls),flush=True)
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        for meals in pool.map(fetch,['https://www.themealdb.com/api/json/v1/1/search.php?f='+c for c in string.ascii_lowercase]):
            for r in meals:
                tags=[r.get('strCategory'),r.get('strArea')]+[r.get('strIngredient'+str(i)) for i in range(1,21)]
                tags=list(dict.fromkeys(t.strip() for t in tags if t and t.strip()))[:25]
                candidates.append(dict(name=r['strMeal'],image=r['strMealThumb'],tags=tags,sourceUrl='https://www.themealdb.com/meal/'+r['idMeal'],provider='TheMealDB',cuisine=r.get('strArea'),sourceCategory=r.get('strCategory')))
    seen_names=set(); seen_images=set(); recipes=[]
    for r in sorted(candidates,key=lambda d:(d['provider']!='Cookbeo',norm(d['name']),d['sourceUrl'])):
        n=norm(r['name']); im=r['image'].split('?')[0]
        if not n or n in seen_names or im in seen_images or not r['tags']: continue
        seen_names.add(n);seen_images.add(im)
        r['categoryId']=category(r['name'],r['tags'],r.pop('sourceCategory',''))
        recipes.append(r)
    result=dict(version='sourced-catalog-v2',retrievedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),mapping='demo-only; original dataset identities unknown',recipes=recipes,errors=errors)
    (ROOT/'data/catalog-v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Unique recipes',len(recipes),'Cookbeo',sum(r['provider']=='Cookbeo' for r in recipes),'errors',len(errors),flush=True)

if __name__=='__main__': main()
