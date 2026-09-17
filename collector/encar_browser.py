"""Render Encar's public search UI. No login, stealth flags, proxies or CAPTCHA handling."""
import json,re,time
from datetime import datetime,timezone
from urllib.parse import quote,urlsplit,urljoin,parse_qs
from bs4 import BeautifulSoup
from .model import is_target,money,trim

BASE='https://www.encar.com/fc/fc_carsearchlist.do?carType=for'

OBSERVATION_FIELDS=['checkedAt','listingPrice','listingPriceKind','monthlyPayment','mileage','registration','modelYear','priceConflict','searchUrl']

def merge_search_history(previous,current,info):
    """Keep list observations separate from detail verification, including failed runs."""
    old={l['listingId']:l for l in previous if l.get('evidence')=='헤드리스 검색 목록 확인'}
    result=[];events=[];seen=set()
    for item in current:
        if item.get('evidence')!='헤드리스 검색 목록 확인':result.append(item);continue
        item=dict(item);rid=item['listingId'];seen.add(rid);prior=old.get(rid)
        observation={k:item.get(k) for k in OBSERVATION_FIELDS}
        history=list(prior.get('listingObservations',[]) if prior else [])
        if prior and not history:history=[{k:prior.get(k) for k in OBSERVATION_FIELDS}]
        if not history or history[-1]['checkedAt']!=observation['checkedAt']:history.append(observation)
        item.update(firstSeen=prior.get('firstSeen',prior['checkedAt']) if prior else item['checkedAt'],stale=False,searchCheckedAt=info['checkedAt'],listingObservations=history)
        event={'at':item['checkedAt'],'sourceId':info.get('id',item.get('sourceId','encar')),'listingId':rid,'url':item['url'],'recordId':'','scope':'검색 목록'}
        if prior is None:events.append(dict(event,type='목록 신규',text=info.get('name',item.get('source','엔카'))+' '+rid+' · 검색 목록 최초 발견. 상세 검증 전.'))
        elif prior.get('listingPrice') is not None and item.get('listingPrice') is not None and prior['listingPrice']!=item['listingPrice'] and not prior.get('priceConflict') and not item.get('priceConflict') and prior.get('listingPriceKind')==item.get('listingPriceKind'):
            events.append(dict(event,type='목록 가격 변경',text=info.get('name',item.get('source','엔카'))+' '+rid+' · 검색 목록 광고금액 변경. 실거래가 아님.',before=prior['listingPrice'],after=item['listingPrice']))
        result.append(item)
    for rid,prior in old.items():
        if rid in seen:continue
        retained=dict(prior,stale=True,searchCheckedAt=info['checkedAt'],searchNote='이번 검색에서 미발견 · 판매완료 아님' if info.get('browserSearch',{}).get('complete') else '이번 검색 실패·일부 조회. 이전 정상 목록 자료 보존')
        result.append(retained)
    return result,events

def merge_listing(old,new):
    if not old:return new
    def variants(x):
        return x.get('listingOffers') or ([{k:x.get(k) for k in ['listingPrice','monthlyPayment','listingPriceKind']}] if x.get('listingPrice') is not None or x.get('monthlyPayment') is not None else [])
    offers={json.dumps(o,sort_keys=True):o for o in variants(old)+variants(new)}
    keys=['listingPrice','monthlyPayment','mileage','registration','modelYear']
    result=dict(max([old,new],key=lambda x:sum(x.get(k) is not None for k in keys)))
    result['listingOffers']=list(offers.values())
    amounts={o['listingPrice'] for o in offers.values() if o.get('listingPrice') is not None}
    result['priceConflict']=len(amounts)>1
    return result

def timestamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def txt(node):return node.get_text(' ',strip=True) if node else ''
def action_url(action):
    return BASE+'#!'+quote(json.dumps({'action':action},ensure_ascii=False,separators=(',',':')))
def filter_options(html,prefix):
    s=BeautifulSoup(html,'html.parser');out=[]
    for label in s.select('label[for]'):
        if not label['for'].startswith(prefix):continue
        node=s.find(id=label['for'])
        if node and node.get('data-action'):out.append({'name':txt(label),'action':node['data-action'],'count':int(txt(label.parent.find('em')).replace(',','')) if txt(label.parent.find('em')).replace(',','').isdigit() else None})
    return out

def listing_items(html,search_url,at):
    s=BeautifulSoup(html,'html.parser');items={}
    for a in s.select('a.newLink._link[href]'):
        name=' '.join(txt(a.select_one(v)) for v in ['.cls','.dtl']).strip()
        if not is_target(name):continue
        original=urljoin(BASE,a['href']);q=parse_qs(urlsplit(original).query)
        rid=(q.get('carid') or [None])[0]
        if not rid:
            m=re.search(r'/cars/detail/(\d+)',original);rid=m[1] if m else None
        if not rid or not rid.isdigit():continue
        card=a.find_parent('tr') or a.find_parent('li') or a
        # Standard rows put the currency outside .prc; retain that visible unit.
        price_node=card.select_one('.prc_hs') or card.select_one('.val') or card.select_one('.prc')
        price_text=txt(price_node)
        monthly=bool(re.search(r'월\s*\d',price_text))
        lease=bool(re.search('리스|렌트|구독',price_text)) or monthly
        km=re.search(r'([\d,]+)\s*km',txt(card.select_one('.km')),re.I)
        year_text=txt(card.select_one('.yer'))
        reg=re.search(r'(\d{2,4})/(\d{2})식',year_text)
        model=re.search(r'\((\d{2,4})년형\)',year_text)
        registration=(str(int(reg[1])+(2000 if len(reg[1])==2 else 0))+'-'+reg[2]) if reg else None
        model_year=int(model[1])+(2000 if len(model[1])==2 else 0) if model else None
        item={'sourceId':'encar','source':'엔카','listingId':rid,'url':'https://fem.encar.com/cars/detail/'+rid,
         'sourceLink':original,'searchUrl':search_url,'title':name,'trim':trim(name),
         'evidence':'헤드리스 검색 목록 확인','checkedAt':at,
         'listingPrice':None if monthly else money(price_text),'monthlyPayment':money(price_text) if monthly else None,
         'listingPriceKind':'월 납입 광고' if monthly else '리스·렌트 목록 광고금액' if lease else '목록 광고가격 · 구매조건 미확인',
         'registration':registration,'modelYear':model_year,'mileage':int(km[1].replace(',','')) if km else None,
         'region':txt(card.select_one('.lo')).lstrip('· ').strip() or None,
         'color':None,'interior':None,'priceConflict':False,
         'note':'검색 목록 관측. 상세페이지·사고·보험·보증·외장색 검증 전이며 현재 판매 확정 아님.'}
        items[rid]=merge_listing(items.get(rid),item)
    return list(items.values())

def discover_encar(fetcher,max_pages=15):
    from playwright.sync_api import sync_playwright
    from .run import FetchError,UA
    info={'status':'일부만 조회','method':'Playwright Chromium headless','pages':0,'complete':False,'queries':[],'note':''}
    found={};deadline=time.monotonic()+240;stage='검색 화면 열기'
    # Fetching the same allowed search URL establishes robots policy before rendering.
    fetcher.get(BASE)
    def policy(url):
        p=urlsplit(url)
        if p.scheme!='https' or p.hostname!='www.encar.com' or p.path!='/fc/fc_carsearchlist.do':
            raise FetchError('접근 차단','검색 이외의 브라우저 탐색 중단')
        rp=fetcher.robots.get(p.hostname)
        if rp and not rp.can_fetch(UA,url):raise FetchError('접근 차단','robots.txt에서 검색 경로 제한')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            ctx=browser.new_context(locale='ko-KR')
            page=ctx.new_page();page.set_default_timeout(12000)
            blocked=[];failed_requests=[];bad_responses=[]
            page.on('requestfailed',lambda request:failed_requests.append({'host':urlsplit(request.url).hostname,'type':request.resource_type,'failure':request.failure}) if request.resource_type in ['document','script','xhr','fetch'] else None)
            page.on('response',lambda response:bad_responses.append({'host':urlsplit(response.url).hostname,'status':response.status,'type':response.request.resource_type}) if response.status>=400 and response.request.resource_type in ['document','script','xhr','fetch'] else None)
            def route_request(route):
                request=route.request
                if request.is_navigation_request() and request.frame==page.main_frame:
                    try:policy(request.url)
                    except FetchError as e:blocked.append(e.note);route.abort();return
                if request.resource_type in ['image','media','font']:route.abort()
                else:route.continue_()
            page.route('**/*',route_request)
            def checked():
                if blocked:raise FetchError('접근 차단',blocked[-1])
                title=page.title()
                body=page.locator('body').inner_text(timeout=5000)[:3000]
                if re.search(r'Access Denied|Just a moment|보안문자를 입력|자동입력 방지|접근이 차단|비정상적인 접근|서비스 이용 제한됨|현재 접속이 제한|비정상적인 트래픽',title+' '+body,re.I):
                    raise FetchError('접근 차단','사이트의 접속 제한·보안 확인 안내. 이전 정상 자료 보존')
            def navigate(url,selector):
                if time.monotonic()>deadline:raise TimeoutError('브라우저 수집 시간 제한')
                policy(url);page.goto('about:blank');response=page.goto(url,wait_until='domcontentloaded',timeout=40000)
                if response and response.status in [401,403,429]:raise FetchError('접근 차단','브라우저 HTTP '+str(response.status))
                if response and response.status>=400:raise FetchError('접속 오류','브라우저 HTTP '+str(response.status))
                checked();page.locator(selector).first.wait_for(state='attached',timeout=15000);checked()
            navigate(BASE,'a[data-action]')
            # Use filter actions exposed by the page, never an undocumented API or an invented chassis filter.
            stage='BMW 제조사 선택'
            page.locator('a[data-action]').filter(has_text=re.compile(r'^BMW$')).first.click()
            page.locator('a[data-action]').filter(has_text=re.compile(r'^4시리즈$')).first.wait_for()
            page.locator('a[data-action]').filter(has_text=re.compile(r'^4시리즈$')).first.click()
            stage='4시리즈 모델 필터 확인'
            page.locator('a[data-action]').filter(has_text='4시리즈 (').first.wait_for()
            models=page.locator('a[data-action]').evaluate_all("(xs)=>xs.filter(x=>x.textContent.trim().startsWith('4시리즈 (')&&x.dataset.action.includes('.Model.')).map(x=>({name:x.textContent.trim(),action:x.dataset.action}))")
            models=list({m['action']:m for m in models}.values())
            if not models:raise ValueError('모델 필터 확인 실패')
            queries=[]
            for model in models:
                stage=model['name']+' 연료 필터 확인'
                navigate(action_url(model['action']),'label[for^="badgeGroup_"]')
                fuels=[x for x in filter_options(page.content(),'badgeGroup_') if '가솔린' in x['name'] and x.get('count')!=0]
                for fuel in fuels:
                    stage=model['name']+' 컨버터블 등급 확인'
                    navigate(action_url(fuel['action']),'label[for^="badge_"]')
                    queries += [q for q in filter_options(page.content(),'badge_') if is_target(q['name']) and q.get('count')!=0]
            queries=list({q['action']:q for q in queries}.values())
            info['queries']=[{'name':q['name'],'url':action_url(q['action'])} for q in queries]
            if not queries:
                info['complete']=True;info['status']='정상 검색 결과 대상 매물 없음';info['note']='모델·연료 필터에서 대상 컨버터블 등급 없음'
                info['listingCount']=0;info['checkedAt']=timestamp()
                return info,[]
            all_complete=True
            for query in queries:
                stage=query['name']+' 검색 목록 확인'
                if info['pages']>=max_pages:all_complete=False;break
                url=action_url(query['action'])
                navigate(url,'#sr_normal')
                page.wait_for_function("()=>document.querySelector('#sr_normal')?.innerText.trim().length>0 || /검색 결과가 없습니다|검색된 차량이 없습니다/.test(document.body.innerText)",timeout=15000)
                page_number=1
                while True:
                    checked()
                    for item in listing_items(page.content(),page.url,timestamp()):found[item['listingId']]=merge_listing(found.get(item['listingId']),item)
                    info['pages']+=1
                    nxt=page.locator('a[data-page="'+str(page_number+1)+'"]')
                    if not nxt.count():break
                    if info['pages']>=max_pages or time.monotonic()>deadline:all_complete=False;break
                    previous=page.locator('#sr_normal').inner_text()
                    nxt.first.click()
                    page.wait_for_function("n=>document.querySelector('a[data-page=\"'+n+'\"].current')",arg=str(page_number+1),timeout=15000)
                    page.wait_for_function("old=>document.querySelector('#sr_normal')?.innerText!==old",arg=previous,timeout=15000)
                    page_number+=1
                if not all_complete:break
            info['complete']=all_complete
            info['status']='조회 성공' if all_complete else '일부만 조회'
            info['note']='모델·가솔린·컨버터블 등급 검색 및 페이지 이동 확인. 상세 확인과 별도.'
        except Exception as e:
            info['status']=getattr(e,'status','일부만 조회' if found else '접속 오류')
            info['note']=stage+' 단계: '+getattr(e,'note','브라우저 화면을 제한시간 안에 판독하지 못했습니다.' if 'Timeout' in type(e).__name__ else '브라우저 화면 판독 오류')
            info['diagnostics']={'stage':stage,'pageTitle':page.title(),'filterCount':page.locator('a[data-action]').count(),'failedRequests':failed_requests[:12],'badResponses':bad_responses[:12]}
            if not info['diagnostics']['filterCount']:
                message=page.locator('body').inner_text(timeout=3000)[:110]
                message=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?:\+82[- ]?)?0\d{1,2}[- ]?\d{3,4}[- ]?\d{4}', '[비공개]',message)
                info['diagnostics']['emptySearchMessage']=message
        finally:browser.close()
    info['listingCount']=len(found);info['checkedAt']=timestamp()
    return info,list(found.values())
