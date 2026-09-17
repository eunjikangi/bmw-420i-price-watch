"""python -m collector.run: public HTTP observation; no LLM, login, or paid API."""
import argparse,concurrent.futures,hashlib,io,json,os,re,threading,time
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,urljoin,parse_qs,urlencode,urlunparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from .model import is_target,canonical,merge_record,group_records,changes,recommendation_state
from .parsers import parse,text,parse_getcha_new
ROOT=Path(__file__).resolve().parents[1]
SOURCES=json.loads((ROOT/'collector/sources.json').read_text())
HOSTS={urlparse(s['url']).hostname.removeprefix('www.') for s in SOURCES}|{'encar.com','bing.com','bmw.co.kr'}
UA='BMW420iPriceWatch/1.0 (public listing observer)'
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
class FetchError(Exception):
    def __init__(self,status,note,code=None):self.status=status;self.note=note;self.code=code;super().__init__(note)
class Fetcher:
    def __init__(self):self.locks={};self.lock=threading.Lock();self.robots={};self.last={};self.cache={}
    def allowed(self,url):
        p=urlparse(url)
        return p.scheme=='https' and not p.username and not p.password and p.port in [None,443] and any(p.hostname==h or (p.hostname or '').endswith('.'+h) for h in HOSTS)
    def get(self,url,depth=0):
        if depth>4:raise FetchError('접속 오류','반복 리다이렉트')
        if not self.allowed(url):raise FetchError('접근 차단','허용 출처 도메인 외 연결 중단')
        if url in self.cache:return self.cache[url]
        host=urlparse(url).hostname
        with self.lock:lock=self.locks.setdefault(host,threading.Lock())
        with lock:
            try:
                if host not in self.robots:
                    rr=requests.get('https://'+host+'/robots.txt',headers={'User-Agent':UA},timeout=(8,12),allow_redirects=False)
                    rp=RobotFileParser();rp.set_url('https://'+host+'/robots.txt')
                    if rr.status_code==200:rp.parse(rr.text.splitlines());self.robots[host]=rp
                    elif rr.status_code in [401,403,429]:raise FetchError('접근 차단','robots.txt 접근 제한')
                    elif rr.status_code>=500:raise FetchError('접속 오류','robots.txt 조회 실패')
                    else:self.robots[host]=None
                rp=self.robots[host]
                if rp and not rp.can_fetch(UA,url):raise FetchError('접근 차단','robots.txt에서 자동 수집을 허용하지 않은 경로')
                time.sleep(max(0,0.8-(time.monotonic()-self.last.get(host,0))))
                self.last[host]=time.monotonic()
                r=requests.get(url,headers={'User-Agent':UA},timeout=(10,20),allow_redirects=False)
            except requests.RequestException as e:raise FetchError('접속 오류',type(e).__name__)
        if r.is_redirect:return self.get(urljoin(url,r.headers['Location']),depth+1)
        if r.status_code==401:raise FetchError('로그인·앱 인증 필요','HTTP 401',401)
        if r.status_code in [403,429]:raise FetchError('접근 차단','HTTP '+str(r.status_code),r.status_code)
        if r.status_code>=400:raise FetchError('접속 오류','HTTP '+str(r.status_code),r.status_code)
        if 'application/pdf' not in r.headers.get('content-type',''):
            r.encoding=r.apparent_encoding or 'utf-8'
            if re.search(r'<title>[^<]*(?:Just a moment|Access Denied|Attention Required)|cf-chl-|보안문자를 입력',r.text[:15000],re.I):raise FetchError('접근 차단','보안 확인 화면. 우회하지 않음')
        self.cache[url]=r;return r
FETCH=Fetcher()
def search_web(src):
    domain=urlparse(src['url']).hostname.removeprefix('www.')
    query='site:'+domain+' 420i (컨버터블 OR Convertible OR 컨버)'
    try:
        r=FETCH.get('https://www.bing.com/search?'+urlencode({'q':query,'format':'rss'}));root=ET.fromstring(r.content);items=[]
        for e in root.findall('./channel/item'):
            title=e.findtext('title','');u=e.findtext('link','');host=urlparse(u).hostname or ''
            if (host==domain or host.endswith('.'+domain)) and is_target(title):items.append({'url':u,'title':title,'evidence':'검색 결과만 확인','checkedAt':now()})
        return items,{'status':'조회 성공','query':query,'count':len(items),'note':'검색 노출 수이며 판매 중인 차량 수 아님'}
    except (FetchError,ET.ParseError) as e:return [],{'status':getattr(e,'status','접속 오류'),'query':query,'note':getattr(e,'note','검색 응답 판독 실패')}
def page_links(s,url):
    return [urljoin(url,a['href']) for a in s.select('a[href]') if (text(a).isdigit() or text(a) in ['다음','다음페이지','Next']) and urlparse(urljoin(url,a['href'])).hostname==urlparse(url).hostname and any(q in a['href'] for q in ['p=','page='])]
def target_links(s,url):
    out=[]
    for a in s.select('a[href]'):
        u=urljoin(url,a['href'])
        if is_target(text(a)) and FETCH.allowed(u) and any(v in u.lower() for v in ['view','detail','/cars/','/car/']):out.append({'url':u,'title':text(a),'evidence':'목록에서 발견','checkedAt':now()})
    return out
def query_forms(s,url):
    out=[]
    for f in s.select('form'):
        if (f.get('method') or 'get').lower()!='get':continue
        action=urljoin(url,f.get('action') or url)
        fields={i['name']:i.get('value','') for i in f.select('input[name]') if i.get('type') in ['hidden',None,'text','search']}
        names=[n for n in fields if n.lower() in ['search_txt','keyword','searchkeyword','searchtext','search_word','query','q']]
        if len(names)!=1:continue
        fields[names[0]]='420i';p=urlparse(action);q={k:v[-1] for k,v in parse_qs(p.query).items()};q.update(fields)
        out.append(urlunparse((p.scheme,p.netloc,p.path,'',urlencode(q),'')))
    return out

def official_prices(s,url):
    candidates=[urljoin(url,a['href']) for a in s.select('a[href]') if '.pdf' in a['href'].lower() and ('가격표' in text(a) or 'pricelist' in a['href'].lower())];out=[]
    for u in candidates[:2]:
        try:
            from pypdf import PdfReader
            r=FETCH.get(u);t=' '.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(r.content)).pages);period=re.search(r'(202\d)\s*년\s*(\d{1,2})\s*월',t)
            if not period:continue
            month=period[1]+'-'+period[2].zfill(2)
            for m in re.finditer(r'420i\s*컨버터블\s*M\s*스포츠(\s*프로)?\s*([\d,]{8,})',t):
                price=int(m[2].replace(',',''))
                if not 10000000<price<200000000:continue
                out.append({'id':'bmw-official-'+('pro' if m[1] else 'sport')+'-'+month,'source':'BMW 코리아','sourceId':'bmw-new','url':u,'trim':'M Sport Pro' if m[1] else 'M Sport','model':'420i 컨버터블','price':price,'priceKind':'공식 권장소비자가격','effectiveMonth':month,'checkedAt':now(),'stock':'흰색 재고 미확인','conditions':'부가세 포함. 옵션·등록비용 별도. 기준월 확인 필요'})
        except Exception:continue
    return out

def collect_source(src,old_records,web=True,max_pages=15):
    out=[];leads=[];attempts=[];prices=[];success=False;complete=False
    queue=list(dict.fromkeys(src.get('searchUrls',[])+[src['url']]));seen=set();targets={canonical(u):{'url':u,'title':'기존 상세페이지','evidence':'기존 기록'} for u in src.get('seeds',[])}
    for r in old_records:targets[r['url']]={'url':r['url'],'title':r['model'],'evidence':'기존 기록'}
    forms=False
    try:
        while queue and len(seen)<max_pages:
            u=queue.pop(0)
            if canonical(u) in seen:continue
            seen.add(canonical(u))
            try:
                resp=FETCH.get(u);s=BeautifulSoup(resp.text,'html.parser');success=True;attempts.append({'url':u,'at':now(),'status':'조회 성공','http':resp.status_code,'scope':'목록·안내 페이지 응답'})
                for lead in target_links(s,u):targets[canonical(lead['url'])]=lead
                if src['parser']=='guide':complete=any('bmw.co.kr' in a['href'] and ('usedcar' in a['href'] or 'used-vehicles' in a['href']) for a in s.select('a[href]'))
                if src.get('pagination') or src['parser']=='boba':queue += [p for p in page_links(s,u) if canonical(p) not in seen]
                if not forms and src['parser'] not in ['guide','new']:queue+=query_forms(s,u);forms=True
                if src.get('pagination') and '매물 리스트' in text(s) and not queue:complete=True
                if src['id']=='bmw-new':prices+=official_prices(s,u)
                if src['id']=='getcha':prices+=parse_getcha_new(s,u,now())
            except FetchError as e:attempts.append({'url':u,'at':now(),'status':e.status,'note':e.note,'http':e.code})
        if src.get('pagination') and not queue and attempts and all(a['status']=='조회 성공' for a in attempts):complete=True
        web_result={'status':'미실행','note':'공개 웹 검색 생략 옵션'}
        if web and src['parser']!='guide':
            leads,web_result=search_web(src)
            for l in leads:targets.setdefault(canonical(l['url']),l)
        for u,lead in list(targets.items())[:40]:
            old=next((r for r in old_records if canonical(r['url'])==u),None)
            try:
                resp=FETCH.get(u);p=parse(resp.text,src,u);at=now()
                if p:
                    p['evidenceHash']=hashlib.sha256(resp.content).hexdigest();out.append(merge_record(old,p,at));success=True;attempts.append({'url':u,'at':at,'status':'조회 성공','scope':'대상 상세페이지 판독'})
                else:
                    if old:out.append(merge_record(old,None,at,False))
                    lead['note']='차량·가격의 안전한 상세 자동 판독 미완료';leads.append(lead)
            except FetchError as e:
                attempts.append({'url':u,'at':now(),'status':e.status,'note':e.note})
                if old:out.append(merge_record(old,None,now(),False,'삭제·비공개 여부 미확인' if e.code in [404,410] else '접근불가'))
                else:lead['note']=e.note;leads.append(lead)
        have={r['id'] for r in out}
        for r in old_records:
            if r['id'] not in have:out.append(merge_record(r,None,now(),False))
        healthy=[r for r in out if not r['stale']]
        if success:
            status='조회 성공' if complete else '일부만 조회';note='공개 목록의 탐색 가능한 페이지 조회 완료' if complete else '공개 페이지 일부 응답. 전체 재고 조회를 보장하지 않음'
            if src['parser']=='structured':note='목록 HTML·공개 검색·구조화 데이터 경로. 동적 검색의 전체 재고 자동 판독 미완성'
            if src['parser']=='guide':note='BMW 통합 검색 연결 확인. 별도 재고로 세지 않음' if complete else '안내 페이지 확인. 별도 재고 미확인'
            if src['parser']=='new':note='신차 안내·검색 일부 확인. 당월 할인·흰색 출고 재고 미확인'
            if complete and src['parser']=='dongsung' and not targets:status='정상 검색 결과 대상 매물 없음'
        else:
            a=attempts[0] if attempts else {};status=a.get('status','접속 오류');note=a.get('note','정상 응답 없음')
        info={'id':src['id'],'name':src['name'],'url':src['url'],'kind':src['kind'],'inventoryGroup':src.get('inventoryGroup',src['id']),'status':status,'note':note,'checkedAt':now(),'lastSuccess':max((r['lastSuccess'] for r in healthy),default=None),'verifiedCount':len(healthy),'listingCount':len(healthy) if complete else None,'internalSearch':{'pages':len(seen),'complete':complete},'webSearch':web_result,'attempts':attempts}
        return info,out,list({canonical(l['url']):l for l in leads if canonical(l['url']) not in {r['url'] for r in healthy}}.values()),prices
    except Exception as e:
        return {'id':src['id'],'name':src['name'],'url':src['url'],'kind':src['kind'],'status':'접속 오류','note':'수집기 오류: '+type(e).__name__,'checkedAt':now(),'lastSuccess':None,'verifiedCount':0,'attempts':attempts},[merge_record(r,None,now(),False) for r in old_records],[],[]

def run(args):
    path=ROOT/'dist/data.json';old=json.loads(path.read_text()) if path.exists() else {'records':[],'sources':[],'events':[],'newCars':[],'runs':[]};started=now();selected=[s for s in SOURCES if not args.sources or s['id'] in args.sources.split(',')];results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(collect_source,s,[r for r in old['records'] if r['sourceId']==s['id']],not args.no_web,args.max_pages):s['id'] for s in selected}
        for f in concurrent.futures.as_completed(tasks):
            r=f.result();results.append(r);print(json.dumps({'source':tasks[f],'status':r[0]['status'],'records':len(r[1]),'unverified':len(r[2])},ensure_ascii=False),flush=True)
    ids={s['id'] for s in selected};records=[r for r in old['records'] if r['sourceId'] not in ids];sources=[s for s in old['sources'] if s['id'] not in ids];leads=[l for l in old.get('leads',[]) if l.get('sourceId') not in ids];prices={p['id']:p for p in old.get('newCars',[])}
    for info,rs,ls,ps in results:
        if not info.get('lastSuccess'):info['lastSuccess']=next((s.get('lastSuccess') for s in old['sources'] if s['id']==info['id']),None)
        records+=rs;sources.append(info);leads += [dict(l,sourceId=info['id'],source=info['name']) for l in ls]
        for p in ps:prices[p['id']]=p
    ev=changes(old['records'],records,started)
    recommendations=recommendation_state(records,datetime.now(timezone.utc).year)
    if old.get('recommendations') is not None and old['recommendations']!=recommendations:
        ev.append({'at':started,'type':'추천 후보 변경','recordId':'','text':'확인된 가격·연식·주행거리·판매 상태 또는 이력 근거가 바뀌어 검토 후보 목록을 갱신했습니다.','before':old['recommendations'],'after':recommendations})
    data={'schemaVersion':1,'updatedAt':now(),'firstRunAt':old.get('firstRunAt',started),'timezone':'Asia/Seoul','schedule':old.get('schedule',{'status':'미설정','description':'예약 실행 연결 준비 중'}),'records':records,'vehicles':group_records(records),'newCars':list(prices.values()),'sources':sorted(sources,key=lambda s:next((i for i,x in enumerate(SOURCES) if x['id']==s['id']),99)),'leads':list({(l['sourceId'],canonical(l['url'])):l for l in leads}.values()),'events':old.get('events',[])+ev,'runs':old.get('runs',[])+[{'startedAt':started,'finishedAt':now(),'sourceCount':len(selected),'newCount':len({g['id'] for g in group_records(records) if any(r['id'] not in {p['id'] for p in old['records']} and r['status']=='광고 게시 중' for r in g['offers']) and g['id'] not in {p['id'] for p in old.get('vehicles',[])}}),'priceChangeCount':sum(e['type']=='가격 변경' for e in ev)}]}
    data['recommendations']=recommendations
    if os.environ.get('GITHUB_ACTIONS')=='true':data['schedule']={'status':'활성','description':'GitHub Actions · 매일 08:00 Asia/Seoul','workflowUrl':'https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/workflows/daily-collection.yml'}
    path.parent.mkdir(exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)
    print(json.dumps({'records':len(records),'groups':len(data['vehicles']),'sourceCount':len(sources),'updatedAt':data['updatedAt']},ensure_ascii=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sources');p.add_argument('--no-web',action='store_true');p.add_argument('--max-pages',type=int,default=15);run(p.parse_args())
