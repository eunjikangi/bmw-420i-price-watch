"""Reject unsafe/invalid snapshots before publication; no network or model calls."""
import json,re
from urllib.parse import unquote
from pathlib import Path
from datetime import datetime
from .model import is_target,STATUSES

def validate(data):
 assert data['schemaVersion']==1
 ids=set()
 for r in data['records']:
  assert is_target(r['model']),r['id']
  assert r['id'] not in ids;r_id=r['id'];ids.add(r_id)
  assert r['url'].startswith('https://')
  assert r['price'] is None or (isinstance(r['price'],int) and r['price']>0),r_id
  assert r['mileage'] is None or isinstance(r['mileage'],(int,float))
  assert not r['cashConfirmed'],'Cash confirmation requires independently reviewed evidence, not an advertising parser.'
  if r['stale']:assert r['lastSuccess']!=r['checkedAt'],r_id
  assert r['firstSeen'] and r['lastSuccess'] and r['checkedAt']
  for o in r['observations']:
   assert datetime.fromisoformat(o['at'])>=datetime.fromisoformat(r['firstSeen'])
   if o['kind']=='조회 실패':assert o['price'] is None
  published=unquote(json.dumps(r,ensure_ascii=False))
  assert not re.search(r'010[- ]?\d{4}[- ]?\d{4}|050[\d-]{8,}',published),r_id
  assert not re.search(r'\d{2,3}[가-힣]\d{4}',published),r_id
 for l in data.get('leads',[]):
  if l.get('evidence')=='헤드리스 검색 목록 확인':
   assert is_target(l['title'])
   assert l['listingId']
   if l['sourceId']=='encar':
    assert l['listingId'].isdigit()
    assert l['url']=='https://fem.encar.com/cars/detail/'+l['listingId']
   else:assert l['url'].startswith('https://')
   assert l['listingPrice'] is None or (isinstance(l['listingPrice'],int) and l['listingPrice']>0)
   if l.get('monthlyPayment'):assert l['listingPrice'] is None
   assert l['color'] is None
   datetime.fromisoformat(l['checkedAt'])
   assert not re.search(r'010[- ]?\d{4}[- ]?\d{4}|050[\d-]{8,}',json.dumps(l,ensure_ascii=False))
 for s in data['sources']:assert s['status'] in STATUSES,s['id']
 for p in data['newCars']:
  assert re.fullmatch(r'20\d\d-\d\d',p['effectiveMonth'])
  assert p['stock']=='흰색 재고 미확인'
 return {'records':len(ids),'sources':len(data['sources']),'passed':True}
if __name__=='__main__':print(json.dumps(validate(json.loads((Path(__file__).resolve().parents[1]/'dist/data.json').read_text())),ensure_ascii=False))
