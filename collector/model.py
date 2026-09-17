"""Conservative normalization and append-only observations. No AI or paid API calls."""
import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

STATUSES = {'조회 성공','정상 검색 결과 대상 매물 없음','일부만 조회','로그인·앱 인증 필요','접근 차단','접속 오류'}

def is_target(name):
    return bool(re.search(r'(?<![a-z0-9])420i(?![a-z0-9])',name,re.I) and re.search(r'컨버(?:터블)?|convertible|cabrio',name,re.I) and not re.search(r'그란\s*쿠페|gran\s*coup|\b(?:420d|430i|M440i)\b',name,re.I))

def white(color):
    return bool(color and re.search(r'흰색|백색|화이트|\bwhite\b',color,re.I))

def money(text):
    m=re.search(r'(?<!\d)([\d,]+(?:\.\d+)?)\s*(만\s*원|원)',text or '')
    return round(float(m[1].replace(',','')) * (10000 if '만' in m[2] else 1)) if m else None

def canonical(url):
    p=urlparse(url);q=parse_qs(p.query)
    keep={k:v[-1] for k,v in q.items() if k.lower() not in {'pageid','view_type','adv_attribute','wtclick_forlist','advclickposition','tempht_arg','listadvtype','viewtype','fbclid','gclid'} and not k.startswith('utm_')}
    # Both Boba listing channels may point to the same underlying listing URL.
    return urlunparse(('https',p.netloc.lower(),p.path,'',urlencode(sorted(keep.items())),''))

def key(source,url):
    q=parse_qs(urlparse(url).query)
    for k in ['carSeq','idx','no','carid','id','DemoNo','it_id','i_sCarCd','sDemoNo']:
        if q.get(k): return source+':'+q[k][0]
    return source+':'+urlparse(url).path.rstrip('/').split('/')[-1]

def trim(name):
    if re.search('스포츠\s*프로|sport\s*pro',name,re.I): return 'M Sport Pro'
    if re.search('스포츠|sport|spt',name,re.I): return 'M Sport'
    return None

def identity(plate):
    return hashlib.sha256(re.sub(r'\s','',plate).encode()).hexdigest() if plate else None

def base(source,url,title):
    return {'id':key(source['id'],url),'sourceId':source['id'],'source':source['name'],'url':canonical(url),'listingId':key(source['id'],url).split(':',1)[1],
    'model':title,'trim':trim(title),'facelift':'부분변경 후' if re.search(r'\bLCI\b|부분변경\s*후',title,re.I) else None,
    'modelYear':None,'registration':None,'mileage':None,'color':None,'interior':None,'region':None,'seller':None,'identityKey':None,
    'price':None,'priceKind':'광고 판매가격','saleMethod':'구매 조건 미확인','cashConfirmed':False,'priceConflict':False,
    'inspection':'미확인','inspectionFacts':[],'sellerClaims':[],'accident':None,'repair':None,'insuranceCount':None,'insuranceAmount':None,'insuranceDetails':None,
    'insuranceAsOf':None,'usage':None,'owners':None,'manufacturerWarranty':None,'certification':'BMW BPS' if source['id']=='dongsung' else None,'certifiedWarranty':None,'serviceRemaining':None,
    'roof':None,'extraCosts':None,'lease':{'initial':None,'remainingPayments':None,'buyout':None,'depositReturn':None,'transferCosts':None,'earlyTerminationCosts':None},
    'status':'광고 게시 중','verification':'상세페이지 확인','warnings':[],'firstSeen':None,'lastSuccess':None,'checkedAt':None,'stale':False,'observations':[]}

def lease_total(lease):
    # Cost components must be explicitly known, including zero, and refundable deposit must not be double-counted.
    required=['initial','remainingPayments','buyout','depositReturn','transferCosts']
    if not all(isinstance(lease.get(k),(int,float)) and not isinstance(lease.get(k),bool) for k in required): return None
    return lease['initial']+lease['remainingPayments']+lease['buyout']+lease['transferCosts']-lease['depositReturn']

def merge_record(old,new,at,ok=True,failure_status='확인불가'):
    if not ok:
        r=dict(old);r['checkedAt']=at;r['stale']=True;r['status']=failure_status
        r['observations']=list(old.get('observations',[]))
        if not r['observations'] or (r['observations'][-1].get('status')!=failure_status):
            r['observations'].append({'at':at,'status':failure_status,'kind':'조회 실패','price':None})
        return r
    r=dict(new);r['firstSeen']=old.get('firstSeen') if old else at;r['lastSuccess']=at;r['checkedAt']=at;r['stale']=False
    r['observations']=list(old.get('observations',[])) if old else []
    obs={'at':at,'price':new['price'],'priceKind':new['priceKind'],'saleMethod':new['saleMethod'],'status':new['status'],'kind':'관측 광고가격'}
    # Keep one successful observation per run, including unchanged prices. Never invent pre-discovery history.
    if not r['observations'] or r['observations'][-1].get('at')!=at:r['observations'].append(obs)
    return r

def group_records(records):
    groups={}
    for r in records:
        g='vehicle:'+r['identityKey'] if r.get('identityKey') else r['id']
        groups.setdefault(g,[]).append(r)
    result=[]
    for gid,offers in groups.items():
        result.append({'id':gid,'offers':offers,'duplicateStatus':'동일 차량 확인' if len(offers)>1 and offers[0].get('identityKey') else '단일 출처'})
    # A close specification match is a suspicion, never a merge.
    for i,g in enumerate(result):
        a=g['offers'][0]
        for h in result[i+1:]:
            b=h['offers'][0]
            if a.get('identityKey') and b.get('identityKey'):continue
            if a['sourceId']!=b['sourceId'] and a.get('registration') and a['registration']==b.get('registration') and a.get('mileage') is not None and a['mileage']==b.get('mileage') and a.get('color')==b.get('color'):
                g['duplicateStatus']=h['duplicateStatus']='중복 추정'
    return result

def changes(previous,current,at):
    old={r['id']:r for r in previous};events=[]
    for r in current:
        p=old.get(r['id'])
        if p is None: events.append({'at':at,'type':'신규','recordId':r['id'],'text':'처음 관측한 광고. 이전 가격은 알 수 없음.'});continue
        if not r.get('stale') and p.get('price')!=r.get('price'):
            events.append({'at':at,'type':'가격 변경','recordId':r['id'],'before':p.get('price'),'after':r.get('price'),'text':'관측 광고가격 변경. 실거래가 아님.'})
        if p.get('status')!=r.get('status'):events.append({'at':at,'type':'상태 변경','recordId':r['id'],'text':p.get('status','미확인')+' → '+r.get('status','미확인')})
    return events

def recommendation_state(records,year):
    """Transparent candidate sets, not a financial or mechanical quality score."""
    candidates=[]
    for g in group_records(records):
        active=[r for r in g['offers'] if r['status']=='광고 게시 중' and not r['stale']]
        if not active:continue
        r=sorted(active,key=lambda x:x['lastSuccess'],reverse=True)[0]
        categories=[]
        if white(r['color']):
            if not re.search('리스|렌트|구독',r['priceKind']+' '+r['saleMethod']) and not r['priceConflict']:categories.append('흰색 가성비 검토')
            if r['modelYear'] and int(r['modelYear'])>=year-2 and r['mileage'] is not None and r['mileage']<=20000:categories.append('흰색 신차급 검토')
        elif r['color']:categories.append('다른 색상 추가 확인')
        reason={'price':r['price'],'modelYear':r['modelYear'],'mileage':r['mileage'],'inspection':r['inspection'],'warranty':r['manufacturerWarranty'],'unknownRoof':not bool(r['roof']),'priceConflict':r['priceConflict'],'saleMethod':r['saleMethod']}
        for category in categories:candidates.append({'vehicleId':g['id'],'recordId':r['id'],'category':category,'basis':reason})
    return candidates
