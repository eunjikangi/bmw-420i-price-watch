"""Site-specific parsers only promote fields actually present in a listing's detail section."""
import json,re
from urllib.parse import unquote
from bs4 import BeautifulSoup
from .model import base,is_target,money,identity

def text(node):return node.get_text(' ',strip=True) if node else ''
def rx(pattern,t,group=1):
    m=re.search(pattern,t,re.I);return m[group] if m else None

def integer(pattern,t):
    v=rx(pattern,t);return int(v.replace(',','')) if v else None

def table_fields(node):
    d={}
    if not node:return d
    for row in node.select('tr'):
        cells=row.find_all(['th','td'],recursive=False)
        for i in range(0,len(cells)-1,2):d[text(cells[i])]=text(cells[i+1])
    return d

def description(s,label):
    h=s.find(lambda x:x.name in ['h3','h4'] and text(x)==label)
    if not h:return ''
    p=h.parent
    # Boba heading is in a d-head and description in the adjacent d-body.
    n=p.find_next_sibling() if 'd-head' in p.get('class',[]) else p
    return text(n)

def common(r,fields,desc):
    r['color']=fields.get('색상') or fields.get('차량색상')
    if r['color'] in ['정보없음','인기색상','미확인','기타']:r['color']=None
    r['interior']=fields.get('시트색상')
    if r['interior'] in ['정보없음','없음']:r['interior']=None
    r['mileage']=integer(r'([\d,]+)\s*km',fields.get('주행거리') or fields.get('주행') or '')
    year=fields.get('연식','')
    r['modelYear']=integer(r'(20\d{2})(?:\s*년)?$',year) or (2000+int(rx(r'(\d{2})년형',year)) if rx(r'(\d{2})년형',year) else None)
    if re.match(r'\d{2}년\d{2}월',year):r['registration']='20'+year[:2]+'-'+year[3:5]
    elif re.match(r'20\d{2}\.\d{2}',year):r['registration']=year[:7].replace('.','-')
    if fields.get('등록일'):r['registration']=fields['등록일'][:7]
    r['identityKey']=identity(fields.get('차량번호') or fields.get('차량정보'))
    r['sellerClaims']=[]
    for pat,label in [(r'완전\s*무사고','완전 무사고라고 설명'),(r'(?<!완전 )무사고','무사고라고 설명'),(r'(앞범퍼|범퍼).{0,25}(파손|수리)','범퍼 파손·수리 관련 설명 있음'),(r'(휠).{0,20}(스크레치|스크래치)','휠 손상 관련 설명 있음')]:
        if re.search(pat,desc):r['sellerClaims'].append(label)
    # Descriptions are claims, never independent inspection evidence.
    if r['sellerClaims']:r['accident']='판매자 설명: '+', '.join(r['sellerClaims'])
    if re.search('금융리스|운용리스',desc):
        r['saleMethod']='금융·운용리스 선택' if '금융리스' in desc and '운용리스' in desc else ('운용리스 승계' if '운용리스' in desc else '금융리스')
        r['priceKind']='리스 광고금액';r['warnings'].append('리스 총비용 확인 필요')
    elif re.search('할부\s*승계|대출\s*잔액.{0,20}이어',desc):r['saleMethod']='할부 승계·일반 판매';r['warnings'].append('할부 승계와 일반 판매 조건 별도 확인')
    elif re.search('현금\s*(차량|판매|구매|완납)',desc):r['saleMethod']='현금 판매 설명';r['cashConfirmed']=False
    roof=rx(r'(?:루프|누수|탑 작동).{0,70}(?:정상|없음|수리|작동|누수).{0,35}',desc,0)
    if roof:r['roof']='판매자 설명: '+roof+' (점검으로 확인한 사실 아님)'
    r['cashConfirmed']=False # No contact / verified financial-product-free purchase quotation has been obtained.
    r['extraCosts']=None
    return r

def parse_kb(s,src,url):
    title=text(s.select_one('.car-buy-name')); title=re.sub(r'^\([^)]*\)','',title)
    if not is_target(title):return None
    r=base(src,url,title);f=table_fields(s.select_one('.detail-info-table'));d=description(s,'판매자 설명');common(r,f,d)
    r['price']=money(text(s.select_one('.car-buy-price dd')))
    area=text(s.select_one('.dealer-info-area'))
    r['region']=rx(r'(서울|경기|부산|대구|인천|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)',area)
    r['seller']=rx(r'((?:\S+차매매단지)[^ ]*)',area)
    r['certification']='KB진단' if s.select_one('.car-buy-price') and 'KB진단 Report' in text(s) else None
    whole=text(s)
    diag=re.search(r'판금/용접\s*(\d+)회\s*교환\s*(\d+)회',whole)
    if diag:
        r['inspection']='플랫폼 진단 요약 확인';r['inspectionFacts']=[f'KB진단 표시: 판금/용접 {diag[1]}회, 교환 {diag[2]}회','성능점검기록부 원본은 별도 확인 필요']
        if int(diag[1]) or int(diag[2]):r['repair']=f'플랫폼 진단 요약: 판금/용접 {diag[1]}회, 교환 {diag[2]}회'
        for marker in s.select('[data-index] .ico[class*="mark_"]'):
            if 'display:none' in (marker.get('style') or '').replace(' ',''):continue
            if not marker.get('style'):continue
            part=marker.parent.select_one('.blind')
            if part:r['inspectionFacts'].append('KB진단 표시: '+text(part)+' '+text(marker))
    doc=s.select_one('[data-link-url][id^="btnCarCheck"]')
    if doc:
        inspection_url=doc.get('data-link-url') or ''
        # Some providers embed a vehicle plate in their URL. Keep those links on the source page.
        if re.search(r'\d{2,3}[가-힣]\d{4}',unquote(inspection_url)):
            r['warnings'].append('성능기록부 링크에 차량 식별정보가 포함되어 원 판매페이지에서 확인')
        elif inspection_url.startswith('https://'):r['inspectionUrl']=inspection_url
    r['insuranceDetails']='공개 보험 건수·요약 확인. 상세 보험 처리금액·수리내역은 로그인 필요' if r.get('insuranceCount') is not None else None
    r['insuranceCount']=integer(r'보험이력\s*(\d+)건',whole)
    if r['insuranceCount'] is not None:r['insuranceDetails']='공개 보험 건수·요약 확인. 상세 보험 처리금액·수리내역은 로그인 필요'
    r['insuranceAsOf']=rx(r'보험사고정보 조회일자\s*:\s*([\d.]+)',whole)
    hist=whole[whole.find('성능점검·보험사고이력정보'):whole.find('주행거리분석')]
    r['usage']=rx(r'용도이력\s*(없음|있음)',hist);r['owners']=rx(r'소유자변경\s*(없음|\d+회)',hist)
    w=s.select_one('.etc-sec01');r['manufacturerWarranty']=text(w) or None
    if r['manufacturerWarranty']:r['warnings'].append('보증 잔여 수치는 원문 자동계산 표시이며 실제 잔여 여부 재확인 필요')
    return r

def parse_dongsung(s,src,url):
    title=text(s.select_one('strong.car_name'))
    if not is_target(title):return None
    r=base(src,url,title);d=text(s.select_one('.prd_car_content'));whole=text(s)
    # Site basic information is presented as dl and table depending on layout.
    f={}
    for e in s.select('dt'):
        n=e.find_next_sibling('dd')
        if n:f[text(e)]=text(n)
    for table in s.select('table'):f.update(table_fields(table))
    # Read only explicit labeled fields as a fallback, not the seller's financial arithmetic.
    for label,pattern in {'등록일':r'등록일\s*(20\d\d-\d\d-\d\d)','연식':r'연식\s*(20\d\d)','주행':r'주행\s*([\d,]+km)','색상':r'색상\s*(.+?)\s*연료','차량번호':r'차량번호\s*(\d{2,3}[가-힣]\d{4})'}.items():
        if not f.get(label):f[label]=rx(pattern,whole) or ''
    common(r,f,d);r['price']=money(text(s.select_one('strong.price')))
    r['region']=f.get('지점') or rx(r'지점\s*(부산|창원)',whole);r['seller']='동성모터스 BPS '+(r['region'] or '')
    r['certifiedWarranty']='BMW BPS 인증 표시. 개별 차량 보증 적용·시작일·제외조건 미확인'
    r['inspection']='기록부 원본 미확인'
    r['warnings'].append('광고의 세금·금융비용 계산은 확정 비용에 포함하지 않음')
    bsi=rx(r'BSI.{0,100}',d,0);r['serviceRemaining']=bsi
    return r

def parse_boba(s,src,url):
    title=text(s.select_one('h3.tit'))
    if not is_target(title):return None
    r=base(src,url,title);whole=text(s);d=description(s,'차량설명');f=table_fields(s.select_one('table'));common(r,f,d)
    r['price']=money(text(s.select_one('span.price')))
    price_text=text(s.select_one('.price-area'))
    if '판매완료' in price_text:r['status']='판매완료'
    elif '예약' in price_text:r['status']='예약중'
    elif '상담' in price_text:r['priceKind']='가격 상담'
    plate=rx(r'차량번호\s*(\d{2,3}[가-힣]\d{4})',whole);r['identityKey']=identity(plate)
    r['region']=rx(r'주소\s*(서울|경기|부산|대구|인천|대전|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\s*(\S+)',whole,0)
    if r['region']:r['region']=r['region'].replace('주소','').strip()
    r['seller']='개인 판매' if '개인' in whole[whole.find('판매자정보'):whole.find('기본정보')] else '미확인'
    insurance=whole[whole.find('보험처리이력'):whole.find('차량설명')]
    r['insuranceCount']=integer(r'보험처리\s*(\d+)\s*회',insurance) or integer(r'보험이력\s*(\d+)건',whole)
    inside=rx(r'보험사고\(내차피[해헤]\)\s*([^원]+원\))',insurance)
    outside=rx(r'보험사고\(타차가해\)\s*([^원]+원\))',insurance)
    r['insuranceDetails']=' / '.join(filter(None,[('내차 '+inside) if inside else None,('타차 '+outside) if outside else None])) or None
    r['owners']=rx(r'차량번호/소유자변경\s*\d+회\s*/\s*(\d+회)',insurance)
    if re.search(r'일반 판매\s*\(수리전\)\s*:\s*\d+',d):
        prices=[int(v)*10000 for v in re.findall(r'(?:일반 판매|승계)\s*\(수리(?:전|후)\)\s*:\s*(\d+)',d)]
        if r['price'] not in prices:r['priceConflict']=True;r['warnings'].append('상단 광고가격과 판매자 설명의 구매가격 불일치')
        r['priceOptions']=[{'kind':'판매자 설명: '+k,'amount':int(v)*10000} for k,v in re.findall(r'((?:일반 판매|승계)\s*\(수리(?:전|후)\))\s*:\s*(\d+)',d)]
    if '파손' in d:r['repair']='판매자 설명에 범퍼 파손·휠 스크레치 기재. 수리 완료 여부 미확인';r['warnings'].append('파손 부위와 수리 조건 확인 필요')
    # Listing monthly rent/lease must never be represented by 0 as a whole vehicle price.
    primary=s.select_one('span.price')
    ptxt=text(primary.parent.parent) if primary else ''
    if re.search('월리스료|월렌트료|잔여개월|인수비용',ptxt):
        r['price']=None;r['priceKind']='월납입·인수금 표시';r['saleMethod']='운용리스 승계' if '리스' in ptxt else '렌트·구독';r['warnings'].append('총비용 확인 필요')
        r['monthlyPayment']=money(rx(r'(?:월리스료|월렌트료)\s*([\d,]+\s*만원)',ptxt) or '')
    r['manufacturerWarranty']='원문 기본정보: '+str(next((v for k,v in f.items() if k.startswith('보증정보')), '미확인'))
    return r

def parse_structured(s,src,url):
    # Only a detail page's own Vehicle JSON-LD with explicit convertible body/model and KRW Offer.
    for script in s.select('script[type="application/ld+json"]'):
        try:data=json.loads(script.string or script.get_text())
        except (ValueError,TypeError):continue
        entries=data if isinstance(data,list) else data.get('@graph',[data])
        for x in entries:
            if not isinstance(x,dict) or x.get('@type') not in ['Vehicle','Car']:continue
            name=x.get('name','')
            if not is_target(name):continue
            r=base(src,url,name);o=x.get('offers',{})
            if not isinstance(o,dict) or o.get('priceCurrency')!='KRW':continue
            try:r['price']=round(float(o['price']))
            except (ValueError,KeyError,TypeError):continue
            r['color']=x.get('color');r['modelYear']=x.get('vehicleModelDate')
            r['warnings'].append('구조화 데이터만 확인. 금융조건·이력 원문 추가 확인 필요')
            r['verification']='상세 구조화 데이터 확인'
            return r
    return None

PARSERS={'kb':parse_kb,'boba':parse_boba,'dongsung':parse_dongsung,'structured':parse_structured}
def parse(html,src,url):
    s=BeautifulSoup(html,'html.parser')
    return PARSERS.get(src['parser'],parse_structured)(s,src,url)

def parse_encar(s,src,url):
    script=next((e.get_text() for e in s.select('script') if '__PRELOADED_STATE__ = {' in e.get_text()),None)
    if not script:return None
    try:d=json.JSONDecoder().raw_decode(script[script.index('{'):])[0];b=d['cars']['base'];c=b['category'];a=b['advertisement'];spec=b['spec']
    except (ValueError,KeyError,TypeError):return None
    title=' '.join(str(c.get(k) or '') for k in ['modelName','gradeName','gradeDetailName']).strip()
    if c.get('manufacturerName')!='BMW' or not is_target(title):return None
    r=base(src,url,title)
    # Prices in Encar's public page data use 10,000 KRW units; validate against displayed price.
    if isinstance(a.get('price'),(int,float)) and a['price']>0:r['price']=round(a['price']*10000)
    ym=c.get('yearMonth','');r['registration']=ym[:4]+'-'+ym[4:6] if re.fullmatch(r'20\d{4}',ym) else None
    r['modelYear']=int(c['formYear']) if str(c.get('formYear','')).isdigit() else None
    r['mileage']=spec.get('mileage');r['color']=spec.get('colorName');r['identityKey']=identity(b.get('vehicleNo'))
    addr=b.get('contact',{}).get('address') or '';r['region']=' '.join(addr.split()[:2]) or None
    r['seller']=spec.get('tradeCompanyName')
    r['saleMethod']={'NORMAL':'일반 판매 광고','FINANCING_LEASE':'금융리스','OPERATING_LEASE':'운용리스 승계','RENT':'렌트·구독','RENT_SUCCESSION':'렌트·구독'}.get(a.get('advertisementType'),'구매 조건 미확인')
    if a.get('leaseRentInfo') or a.get('advertisementType')!='NORMAL':
        r['priceKind']='리스·렌트 광고금액';r['warnings'].append('초기·잔여·만기·승계비용이 모두 확인되지 않아 총인수비용 미계산')
        lr=a.get('leaseRentInfo') or {};r['remainingMonths']=lr.get('residualMonth')
        # Do not presume units of monthlyFee/advancePrice from the whole-vehicle price field.
    line=a.get('oneLineText') or ''
    if '무사고' in line:r['sellerClaims'].append('광고 설명: 무사고')
    if '1인소유' in line:r['sellerClaims'].append('광고 설명: 1인 소유')
    if a.get('diagnosisCar'):r['certification']='엔카진단';r['inspection']='진단 표시 확인 · 원본 미확인'
    if a.get('directInspected'):r['inspection']='엔카 직영 성능점검 표시 · 원본 미확인'
    if a.get('status')!='ADVERTISE':r['status']='상태 미확인';r['warnings'].append('현재 광고 게시 상태가 확인되지 않음')
    return r
PARSERS['encar']=parse_encar

def parse_getcha_new(s,url,at):
    title=text(s.select_one('h1'))
    if not is_target(title):return []
    period=re.search(r'(202\d)년\s*(\d{1,2})월',title)
    if not period:return []
    month=period[1]+'-'+period[2].zfill(2);out=[]
    table=s.select_one('table')
    for tr in table.select('tr') if table else []:
        cells=tr.select('td')
        if len(cells)<2:continue
        label=text(cells[0]);amount=money(text(cells[1]))
        if amount is None or ('기본가격' not in label and '실구매가' not in label):continue
        kind='플랫폼 기재 기본가격' if '기본가격' in label else '광고 할인가 · 구매조건 미확인'
        out.append({'id':'getcha-'+month+'-'+('base' if '기본가격' in label else 'discount'),'source':'겟차','sourceId':'getcha','url':url,'trim':'M Sport Pro P1' if '프로' in title else 'M Sport','model':'420i 컨버터블','price':amount,'priceKind':kind,'effectiveMonth':month,'checkedAt':at,'stock':'흰색 재고 미확인','conditions':'플랫폼의 모의견적 자료. 현금 구매·실출고 재고 견적 미확인. 월납입금과 별도.'})
    return out

def parse_kcar(s,src,url):
    title=text(s.select_one('h2.carName'))
    if not is_target(title):return None
    r=base(src,url,title);t=text(s);head=t[t.find(title):t.find('차량 예상 가격')]
    r['price']=money(head);r['identityKey']=identity(rx(r'(\d{2,3}[가-힣]\d{4})',head))
    reg=re.search(r'(\d{2})년\s*(\d{1,2})월식',head)
    if reg:r['registration']='20'+reg[1]+'-'+reg[2].zfill(2)
    r['mileage']=integer(r'([\d,]+)km',head)
    r['color']=rx(r'km\s*가솔린\s*(.+?)\s*오토',head)
    r['seller']=rx(r'차량판매자\s*(.+?)\s*0\d',head)
    r['region']=rx(r'브랜드인증\s*(\S+)',head)
    r['certification']='BMW BPS · 케이카 브랜드 인증관'
    r['saleMethod']='리스 승계·종류 미확인' if '리스차량' in head else '일반 판매 광고'
    if '리스차량' in head:r['priceKind']='리스 광고금액';r['warnings'].append('리스 총비용 확인 필요. 설명의 금융 예시는 확정 승계 조건이 아님.')
    desc=t[t.find('차량 소개'):t.find('꼭! 알아두세요')]
    r['modelYear']=integer(r'\((\d{2})MY\)',desc)
    if r['modelYear']:r['modelYear']+=2000
    year=integer(r'\((\d{2})년형\)',head)
    if year:r['modelYear']=year+2000
    if re.search(r'\bLCI\b',desc):r['facelift']='부분변경 후 · 판매자 원문 LCI'
    r['interior']='판매자 설명: '+rx(r'(블랙|베이지|브라운|레드)\s*시트',desc) if rx(r'(블랙|베이지|브라운|레드)\s*시트',desc) else None
    if re.search(r'무사고',desc):r['sellerClaims'].append('판매자 설명: 무사고')
    r['inspection']='공식딜러 72항목 진단 표시 · 사진 기록부 원본 미판독'
    r['inspectionFacts']=['케이카 브랜드 인증관의 공식딜러 제공 진단 표시. 원본 기재내용 미확인']
    hist=t[t.find('보험이력으로 더욱'):t.find('차량 소개')]
    own=integer(r'내차\s*피해\s*(\d+)건',hist);other=integer(r'상대차\s*피해\s*(\d+)건',hist)
    r['insuranceCount']=own+other if own is not None and other is not None else None
    r['insuranceDetails']=f'플랫폼 공개 요약: 내차 {own}건 / 상대차 {other}건. 보험 원본·수리금액 미확인' if r['insuranceCount'] is not None else None
    r['owners']=rx(r'소유자 변경\s*(\d+건)',hist);r['usage']=rx(r'용도 변경 이력\s*(없음|있음)',hist)
    r['manufacturerWarranty']='판매자 설명: '+rx(r'(신차 보증.{0,55})',desc) if rx(r'(신차 보증.{0,55})',desc) else None
    r['serviceRemaining']='판매자 설명: '+rx(r'(BSI.{0,55})',desc) if rx(r'(BSI.{0,55})',desc) else None
    r['warnings'].append('보험 0건·진단 표시는 무도색 또는 루프 정상 확인이 아님')
    return r

def parse_kolon(s,src,url):
    title=text(s.select_one('article.title-lg'))
    if not is_target(title):return None
    r=base(src,url,title);t=re.sub(r'(\d)\s+(회|건|원)',r'\1\2',text(s)).replace('( ','(');head=t[t.find(title):t.find('판매자 정보')]
    r['price']=money(rx(r'차량 가격\s*([\d,]+원)',t) or '')
    r['modelYear']=integer(r'(20\d{2})년형',head);r['registration']=(rx(r'최초등록\s*(20\d\d[.\-]\d\d)',head) or '').replace('.','-') or None
    r['mileage']=integer(r'([\d,]+)km',head);r['color']=rx(r'외관컬러\s*(\S+)',head);r['identityKey']=identity(rx(r'(\d{2,3}[가-힣]\d{4})',head))
    r['region']=rx(r'가솔린\s*(서울|경기|경남|대전|대구|광주|부산|인천)',head);r['seller']='코오롱 BPS '+(rx(r'BPS_(\S+)',t) or '');r['certification']='BMW BPS · 코오롱 인증중고차'
    own=integer(r'내차피해\s*(\d+)회',head);other=integer(r'타차피해\s*(\d+)회',head)
    r['insuranceCount']=own+other if own is not None and other is not None else None
    a=integer(r'내차피해\s*\d+회\s*\(([\d,]+)원\)',head);c=integer(r'타차피해\s*\d+회\s*\(([\d,]+)원\)',head)
    r['insuranceAmount']=a+c if a is not None and c is not None else None
    if a is not None:r['insuranceDetails']=f'플랫폼 공개 요약: 내차 {own}회 ({a:,}원) / 타차 {other}회 ({c:,}원). 세부 수리 부위 미확인' if c is not None else f'내차 {own}회 ({a:,}원)'
    r['owners']=rx(r'소유자 변경\s*(\d+회)',head);r['usage']=rx(r'용도 변경 이력\s*(없음|있음)',head)
    desc=t[t.find('판매자 정보'):t.rfind('차량 점검 상세보기')]
    if '무사고' in desc:r['sellerClaims'].append('판매자 설명: 무사고')
    for pat,label in [('타이어.*교체','타이어 최근 교체'),('점화플러그.*교체','점화플러그 최근 교체'),('블랙.*시트','실내 블랙 시트')]:
        if re.search(pat,desc):r['sellerClaims'].append('판매자 설명: '+label)
    if '블랙 시트' in desc or '블랙(내장' in desc:r['interior']='판매자 설명: 블랙'
    if 'BPS 보증 가입 지원' in desc:r['certifiedWarranty']='판매자 설명: BPS 보증 가입 지원 (1년 또는 2만km). 실제 가입·개시·제외조건 미확인'
    diag=t[t.rfind('차량 점검 상세보기'):t.find('구매비용 계산기')]
    for label in ['내외관 상태','외부패널 진단','주요프레임 진단']:
        m=rx(label+r'\s*((?:(?:양호|흠집|깨짐|정상|교환|판금|용접)\s*\d+건\s*)+)',diag)
        if m:r['inspectionFacts'].append('플랫폼 점검 요약: '+label+' '+m.strip())
    if r['inspectionFacts']:r['inspection']='플랫폼 점검 요약 확인 · 성능기록부 원본 미확인'
    r['manufacturerWarranty']=rx(r'제조사 보증\s*(.+?)(?:구매비용|리스 정보|$)',diag)
    if r['manufacturerWarranty']:r['warnings'].append('보증 잔여 수치는 플랫폼 표시. 표시 날짜·거리 기준이 불일치할 수 있어 재확인 필요')
    if re.search(r'차량 가격\s*[\d,]+원',t):r['saleMethod']='일반 판매 광고'
    if '리스 정보' in t or re.search(r'리스방식\s*(금융|운용)',t):r['saleMethod']='리스 승계·종류 미확인';r['priceKind']='리스 광고금액';r['warnings'].append('총비용 확인 필요')
    extra=integer(r'이전 등록 관련 부가비용\s*([\d,]+)원',t)
    if extra is not None:r['extraCostEstimate']={'amount':extra,'basis':'판매 사이트의 취등록세·공채 할인비 등 예상치. 적용 기준·최종 비용 미확인','confirmed':False}
    r['warnings'].append('보험처리 금액·외부패널 진단만으로 무도색·루프 정상 여부를 확정하지 않음')
    return r
PARSERS['kcar']=parse_kcar
PARSERS['kolon']=parse_kolon

def parse_mpark(s,src,url):
    title=text(s.select_one('title'))
    if not is_target(title):return None
    t=text(s);r=base(src,url,title);r['price']=money(rx(r'판매가격\s*([\d,]+\s*만원)',t) or '')
    if r['price'] is None:return None
    r['mileage']=integer(r'([\d,]+)km',t);r['modelYear']=2000+int(rx(r'연식\s*\d{2}년\d{2}월\((\d{2})년형\)',t)) if rx(r'연식\s*\d{2}년\d{2}월\((\d{2})년형\)',t) else None
    reg=rx(r'연식\s*(\d{2}년\d{2}월)',t)
    if reg:r['registration']='20'+reg[:2]+'-'+reg[3:5]
    r['identityKey']=identity(rx(r'차량정보\s*(\d{2,3}[가-힣]\d{4})',t));r['seller']=rx(r'상사명\s*(.+?)\s*상사주소',t);r['region']=rx(r'상사주소\s*(\S+\s+\S+)',t)
    color=(rx(r'색상\s*(.+?)\s*압류',t) or '').strip();r['color']=color if color and len(color)<20 else None
    r['saleMethod']='일반 판매 광고 · 직접매도' if '직접매도' in t else '구매 조건 미확인'
    diag=t[t.find('81가지 차량 점검 완료!'):t.find('성능점검기록부 보기')]
    for label in ['사고(단순수리제외)','단순수리','교환','판금/용접','용도변경','침수']:
        v=rx(re.escape(label)+r'\s*(없음|무|있음|유|\d+회)',diag)
        if v:r['inspectionFacts'].append('엠파크 점검 요약: '+label+' '+v)
    if r['inspectionFacts']:r['inspection']='플랫폼 점검 요약 확인 · 원본 미확인'
    hist=t[t.find('성능점검기록부 보기'):t.find('보험처리이력 보기')]
    r['insuranceAsOf']=rx(r'점검일\s*:\s*(20\d\d년\s*\d\d월\s*\d\d일)',hist)
    own=integer(r'내차피해\s*(\d+)회',hist);other=integer(r'타차피해\s*(\d+)회',hist)
    r['insuranceCount']=own+other if own is not None and other is not None else None
    r['insuranceDetails']=' / '.join(re.findall(r'(?:내차피해|타차피해)\s*\d+회\s*\([\d,]+원\)',hist)) or None
    r['owners']=rx(r'소유자 변경\s*(\d+회)',hist);r['usage']=rx(r'용도 변경 이력\s*(없음|있음)',hist)
    if re.search(r'저당\s*[1-9]\d*회',t):r['warnings'].append('공개 정보에 저당 '+rx(r'저당\s*(\d+회)',t)+' 표시. 인도 전 말소 조건 확인 필요')
    r['warnings']+=['보험·성능 자료 기준일 확인 필요. 보험 0건은 무도색·루프 정상 확정이 아님','외장색이 빈칸이면 사진으로 색상을 추정하지 않음']
    return r
PARSERS['mpark']=parse_mpark

def parse_danawa_new(s,url,at):
    out=[]
    for heading in s.select('dt.price_title'):
        label=text(heading);period=re.search(r'(20\d\d)\.(\d\d)\.(\d\d)',label)
        year=integer(r'(20\d\d)년형',label)
        if not period or '컨버터블 가솔린 2.0' not in label:continue
        listing=heading.find_next_sibling('dd')
        if not listing:continue
        for item in listing.select('li'):
            model=text(item.select_one('label'));price=money(text(item.select_one('.item.price')));ident=item.select_one('input[value]')
            if not is_target(model) or not price or not ident:continue
            out.append({'id':'danawa-'+ident['value'],'source':'다나와 자동차','sourceId':'danawa-new','url':url,'model':'420i 컨버터블','trim':model.replace('420i Convertible','').strip(),'modelYear':year,
             'price':price,'priceKind':'플랫폼 기재 모델별 가격표','effectiveMonth':period[1]+'-'+period[2],'pricePeriodKind':'가격표 적용 시작','validFrom':'-'.join(period.groups()),'checkedAt':at,
             'stock':'흰색 재고 미확인','conditions':'사이트에 표시된 가격표 적용 시작일 기준. 할인·금융 조건·현금 견적·출고 재고 확인과 별개. P1/P2/P2-0 사양을 구분.'})
    return out
