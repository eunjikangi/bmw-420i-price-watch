"""Reproducible public UI searches and detail rendering for the registered sources."""
import json,re,time,hashlib
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlsplit
from .browser import PublicBrowser,BrowserError,safe_text
from .model import canonical,is_target,base,money,merge_record
from .parsers import parse,text

SEARCH_PATHS={
 'danawa-new':'https://auto.danawa.com/auto/?Brand=362&Model=4614&Tab=main&Work=model&pcUse=y',
 'kb':'https://www.kbchachacha.com/public/search/main.kbc',
 'kcar':'https://www.kcar.com/bc/search',
 'charancha':'https://charancha.com/cars',
 'reborncar':'https://www.reborncar.co.kr/smartbuy/SB1001.rb',
 'kolon':'https://702prime.com/used-car/product-list?topFilter=all',
 'tcar':'https://tcar.lotterentacar.net/cr/search/list#page:1._.rows:15._.saleTySale:true',
 'danawa-used':'https://auto.danawa.com/usedcar/?Brand=362&Series=3434&Tab=list&Work=list',
 'daangn':'https://www.daangn.com/kr/search/cars/',
 'heydealer':'https://www.heydealer.com/market/cars?brand=0W5AWm&model-group=VMjRnM',
}

def search_ui(b,src):
    sid=src['id'];p=b.goto(SEARCH_PATHS.get(sid,src.get('searchUrls',[src['url']])[0]));note=''
    complete=False;query=None
    def click_text(t):p.get_by_text(t,exact=True).filter(visible=True).first.click();b.settle()
    def keyword(placeholder,q):
        control=p.get_by_placeholder(placeholder,exact=True).filter(visible=True).first
        control.fill(q);control.press('Enter');b.settle()
    if sid=='kb':
        click_text('BMW');click_text('4시리즈')
        # Inspect both generations, never infer the roof from a chassis label.
        labels=p.locator('label').all_inner_texts();models=[v.strip() for v in labels if re.match(r'4시리즈 \(',v.strip())]
        available=[]
        for model in models:
            p.locator('label').filter(has_text=model).first.click();b.settle()
            available += [v.strip() for v in p.locator('label').all_inner_texts() if is_target(v)]
            p.locator('label').filter(has_text=model).first.click();b.settle()
        # Select explicit convertible grades in their matching generation.
        for model in models:
            p.locator('label').filter(has_text=model).first.click();b.settle()
            matches=[v.strip() for v in p.locator('label').all_inner_texts() if is_target(v)]
            if matches:
                for name in list(dict.fromkeys(matches)):click_text(name)
                break
            p.locator('label').filter(has_text=model).first.click();b.settle()
        query='BMW → 4시리즈 → 실제 420i Convertible 등급'
        note='두 세대의 등급 확인. 공개 검색 목록 및 상세 기본정보·진단 요약 판독. 보험 상세는 로그인 필요.'
    elif sid=='charancha':
        click_text('BMW');click_text('4시리즈');query='BMW → 4시리즈 전체';note='전국 4시리즈 목록에서 실제 컨버터블 표기 확인. 상세 경로는 자동 수집 제한.'
    elif sid=='kolon':
        click_text('BMW');click_text('4시리즈');query='BMW → 4시리즈 전체';note='목록의 실제 컨버터블 등급과 상세 가격·보험·점검·보증 공개 요약 확인.'
    elif sid=='kcar':
        keyword('차량을 검색하세요.','420i 컨버터블');query='420i 컨버터블';note='통합 검색의 직영·직거래·브랜드 인증관을 구분. 인증관의 리스 금액은 일반 판매와 분리.'
    elif sid=='reborncar':keyword('원하는 차량을 검색하세요.','420i');query='420i';complete=True;note='차량 키워드 검색 정상 응답. 렌트·구독 포함 결과에서 차종 확인.'
    elif sid=='autoinside':keyword('차량명으로 검색','420i');query='420i';note='판매 차량 키워드 검색 응답. 판매준비차량은 별도이며 전체 재고 없음으로 단정하지 않음.'
    elif sid=='tcar':keyword('차종 혹은 모델을 입력해주세요.','420i');query='420i';complete=True;note='판매 차량 전체 검색에서 420i 키워드 조회.'
    elif sid=='autohub':
        # Homepage defaults to domestic. Select the actual imported-car control first.
        control=p.locator('input').filter(visible=True)
        imported=p.get_by_text('수입차',exact=True).filter(visible=True).last
        imported.click();b.settle();p.locator('#MainSearchName').fill('420i');p.get_by_role('button',name='검색하기',exact=True).click();b.settle()
        query='수입차 + 420i';note='수입차 검색 결과. 실제 컨버터블 등급을 추가 확인.'
    elif sid=='danawa-used':
        query='BMW → 4-series';note='제휴 목록 확인. 원 판매처 링크를 보존하며 별도 차량으로 중복 합산하지 않음.'
    elif sid=='mpark':keyword('검색어를 입력해주세요.','420i');query='420i';note='검색 UI는 열렸으나 원 목록의 제원 필터 데이터가 정상 로딩됐는지 확인되지 않아 0건 확정 불가.'
    elif sid=='daangn':keyword('검색어를 입력하세요','420i 컨버터블');query='420i 컨버터블';note='공개 웹 검색은 사이트가 설정한 지역 범위로 제한됨. 전국 매물 없음으로 해석하지 않음.'
    elif sid=='heydealer':query='BMW → 4시리즈 전체';complete=True;note='공개 4시리즈 전체 목록에서 실제 컨버터블 표기 대조.'
    elif sid=='danawa-new':
        titles=p.locator('dt.price_title').filter(has_text='컨버터블 가솔린 2.0')
        for i in range(titles.count()):
            titles.nth(i).locator('button.button_updown').click();b.settle()
        note='모델별 컨버터블 가격표를 펼쳐 P1·P2·P2-0을 구분. 가격표 시행일과 이번 조회일을 별도 기록.'
    elif sid=='bmw-bps':
        p.wait_for_timeout(8000);b.check();note='통합 검색 앱 렌더링 확인. 재고 필터 로딩 상태를 별도로 확인.'
    elif src['parser']=='guide':
        links=b.links();complete=any('bmw.co.kr' in v['url'] and 'usedcar' in v['url'] for v in links);note='BMW 통합 검색 안내 경로. 별도 재고 사이트로 계산하지 않음.'
    elif src['parser']=='new':note='신차 공개 문서 렌더링 확인. 공식가·광고할인·금융 예시·출고 재고는 별개.'
    else:note='공개 브라우저 화면 확인. 전체 재고 검색 완료 여부는 미확인.'
    if complete and src['kind'] not in ['보완 경로']:
        body=p.locator('body').first.inner_text()
        if sid=='heydealer':complete='BMW 4시리즈 중고차' in body and bool(re.search(r'4시리즈 \(G22\).*420i',re.sub(r'\s+',' ',body)))
        elif sid=='reborncar':complete='검색 결과가 없습니다.' in body and bool(re.search(r'총\s*0\s*대',body))
        elif sid=='tcar':complete='420i' in p.url and '검색된 차량이 없습니다.' in body
    return {'query':query,'note':note,'complete':complete}

def discover(b,src,max_pages):
    from .run import now,target_links,page_links
    result=search_ui(b,src);pages=0;targets={};leads=[];seen=set();p=b.page
    while pages<max_pages:
        html=p.content();s=BeautifulSoup(html,'html.parser');pages+=1
        for lead in target_links(s,p.url):targets[canonical(lead['url'])]=lead
        if src['id']=='danawa-used':
            for a in s.select('a[href*="loadingBridge.php"]'):
                if is_target(text(a)):
                    url=urljoin(p.url,a['href']);targets[canonical(url)]={'url':url,'title':text(a),'checkedAt':now(),'evidence':'제휴 목록에서 발견'}
        if src['id']=='charancha':
            for a in s.select('a[href*="/cars/"]'):
                title=text(a)
                if not is_target(title):continue
                u=urljoin(p.url,a['href']).split('?')[0];card=a
                for _ in range(4):
                    if re.search(r'\d[\d,]*\s*만원',text(card)):break
                    card=card.parent
                t=text(card);r=base(src,u,title);reg=re.search(r'(\d{2})년(\d{2})월',t);km=re.search(r'([\d,]+)km',t);year=re.search(r'\((\d{2})년형\)',t)
                leads.append({'sourceId':src['id'],'source':src['name'],'listingId':r['listingId'],'url':u,'title':title.split('만원')[0][:130],
                  'searchUrl':p.url,'checkedAt':now(),'evidence':'헤드리스 검색 목록 확인','listingPrice':money(t),'monthlyPayment':None,
                  'listingPriceKind':'목록 광고가격 · 구매조건 미확인','modelYear':2000+int(year[1]) if year else None,'registration':'20'+reg[1]+'-'+reg[2] if reg else None,
                  'mileage':int(km[1].replace(',','')) if km else None,'region':next((v for v in ['서울','경기','부산','인천','대구','울산','대전','광주','경남','경북','전남','전북','충남','충북','강원','제주','세종'] if '· '+v in t),None),
                  'color':None,'interior':None,'stale':False,'priceConflict':False,'note':'목록 관측. 상세페이지 자동 수집 제한으로 외장색·점검·보험·보증 미확인.'})
        # Follow only visible page controls; a hidden next link is not proof of a next page.
        nxt=p.locator('a.next:visible, button[aria-label="다음 페이지"]:visible').first
        current=p.url+'|'+hashlib.sha256(html.encode()).hexdigest()
        if current in seen:break
        seen.add(current)
        if nxt.count() and not nxt.is_disabled():
            nxt.click();b.settle();continue
        # Load explicitly lazy-rendered cards by ordinary scrolling, bounded to avoid crawling unrelated recommendations.
        if src['id']=='charancha' and pages<3:
            before=p.locator('a[href*="/cars/"]').count();p.evaluate('window.scrollTo(0,document.body.scrollHeight)');b.settle()
            if p.locator('a[href*="/cars/"]').count()>before:continue
        break
    if src['id'] in ['kcar','kolon']:
        if src['id']=='kcar':
            # A SPA transition would otherwise skip document navigation guards. Check the known detail route first.
            try:b.allowed('https://www.kcar.com/br/detail/brandCarInfoDtl')
            except BrowserError as e:
                result['note']+=' 상세 경로 자동 수집 제한으로 목록 후보만 보존.'
                result.update(pages=pages,searchUrl=p.url,targets={},leads=leads)
                return result
        selector='p.carTit' if src['id']=='kcar' else 'article.body-lg'
        names=list(dict.fromkeys(n.strip() for n in p.locator(selector).all_inner_texts() if is_target(n) and len(n)<160))
        for name in names[:30]:
            p.get_by_text(name,exact=True).first.click();b.settle()
            active=b.context.pages[-1]
            if active!=p:active.wait_for_load_state();url=active.url;active.close()
            else:url=p.url;p.go_back();b.settle()
            if b.fetcher.allowed(url):targets[canonical(url)]={'url':url,'title':name,'checkedAt':now(),'evidence':'헤드리스 검색 목록 확인'}
    result.update(pages=pages,searchUrl=p.url,targets=targets,leads=list({l['url']:l for l in leads}.values()))
    return result

def collect_browser_source(src,old_records,fetcher,max_pages=15):
    from .run import now
    at=now();out=[];leads=[];attempts=[];prices=[];result={'complete':False,'pages':0,'note':''};ok=False
    try:
        with PublicBrowser(fetcher,seconds=480) as b:
            try:
                result=discover(b,src,max_pages);ok=True;leads=result.pop('leads');targets=result.pop('targets')
                attempts.append({'url':b.page.url,'at':now(),'status':'조회 성공','scope':'헤드리스 내부 검색','note':result.get('query') or '공개 안내'})
                b.snapshot(src['id'],'latest-search')
                if src['id']=='getcha':
                    from .parsers import parse_getcha_new
                    prices+=parse_getcha_new(BeautifulSoup(b.page.content(),'html.parser'),b.page.url,now())
                if src['id']=='danawa-new':
                    from .parsers import parse_danawa_new
                    prices+=parse_danawa_new(BeautifulSoup(b.page.content(),'html.parser'),b.page.url,now())
                if src['id']=='bmw-new':
                    from .run import official_prices
                    prices+=official_prices(BeautifulSoup(b.page.content(),'html.parser'),b.page.url)
            except Exception as e:
                result['status']=getattr(e,'status','접속 오류');result['note']=getattr(e,'note','동적 검색 판독 실패: '+type(e).__name__)
                attempts.append({'url':b.page.url if b.page.url.startswith('https:') else src['url'],'at':now(),'status':result['status'],'scope':'헤드리스 내부 검색','note':result['note']})
                targets={}
                # A block stops that source. A search-specific DOM failure may still permit previously known details.
                if result['status']=='접근 차단':raise BrowserError(result['status'],result['note'])
            for u in src.get('seeds',[]):targets.setdefault(canonical(u),{'url':u,'title':'기존 상세 경로'})
            for old in old_records:targets.setdefault(canonical(old['url']),{'url':old['url'],'title':old['model']})
            for url,lead in list(targets.items())[:60]:
                prior=next((r for r in old_records if canonical(r['url'])==canonical(url)),None)
                try:
                    b.goto(url);html=b.page.content();parsed=parse(html,dict(src,parser='mpark') if src['id']=='danawa-used' and '/buy/detail/' in b.page.url else src,url)
                    if parsed and b.page.url!=url:parsed['originalSourceUrl']=b.page.url
                    if parsed and (parsed['price'] is not None or parsed['priceKind'] in ['가격 상담','월납입·인수금 표시']):
                        checked=now();parsed['evidenceHash']=hashlib.sha256(html.encode()).hexdigest();parsed['collectionMethod']='Playwright Chromium headless'
                        out.append(merge_record(prior,parsed,checked));ok=True;attempts.append({'url':url,'at':checked,'status':'조회 성공','scope':'헤드리스 상세페이지 판독'})
                        b.snapshot(src['id'],'latest-detail-'+parsed['listingId'])
                    else:
                        attempts.append({'url':url,'at':now(),'status':'일부만 조회','scope':'상세페이지','note':'대상 모델·가격의 안전한 자동 판독 미완료'})
                        leads.append(dict(lead,note='상세 자동 판독 미완료. 현재 판매 검증과 분리.',checkedAt=now(),evidence='목록에서 발견'))
                except Exception as e:
                    status=getattr(e,'status','접속 오류');note=getattr(e,'note','상세 화면 로딩 실패: '+type(e).__name__)
                    attempts.append({'url':url,'at':now(),'status':status,'scope':'헤드리스 상세페이지','note':note})
                    if src['id'] not in ['charancha']:leads.append(dict(lead,note=note,checkedAt=now(),evidence='목록에서 발견'))
                    if status=='접근 차단' and 'robots.txt' not in note:
                        result['note']+=' 상세 조회 중 보안 확인 안내를 만나 이후 요청 중단.'
                        result['status']='일부만 조회' if out else '접근 차단'
                        break
            result['diagnostics']={'failedRequests':b.errors[:5],'badResponses':b.responses[:5]}
    except Exception as e:
        result['status']=getattr(e,'status','접속 오류');result['note']=getattr(e,'note','브라우저 실행 실패: '+type(e).__name__)
    have={r['id'] for r in out}
    for old in old_records:
        if old['id'] not in have:out.append(merge_record(old,None,now(),False,'접근불가' if result.get('status')=='접근 차단' else '확인불가'))
    # Only explicit normal filtered emptiness can become zero; shell/UI errors remain partial.
    status=result.get('status') or ('조회 성공' if result.get('complete') else '일부만 조회')
    if result.get('complete') and not out and src['kind'] not in ['신차','보완 경로']:status='정상 검색 결과 대상 매물 없음'
    if out and any(r['stale'] for r in out):status='일부만 조회' if ok else status
    result.update(status=status,method='Playwright Chromium headless',checkedAt=now(),listingCount=len(leads),verifiedCount=sum(not r['stale'] for r in out))
    info={'id':src['id'],'name':src['name'],'url':src['url'],'kind':src['kind'],'inventoryGroup':src.get('inventoryGroup',src['id']),'status':status,'note':result['note'],'checkedAt':now(),
      'lastSuccess':max((r['lastSuccess'] for r in out if not r['stale']),default=None),'verifiedCount':sum(not r['stale'] for r in out),'listingCount':None,
      'internalSearch':{'pages':result['pages'],'complete':result['complete']},'browserSearch':result,'attempts':attempts}
    return info,out,leads,prices
