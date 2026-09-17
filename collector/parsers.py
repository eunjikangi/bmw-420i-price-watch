"""Site-specific parsers only promote fields actually present in a listing's detail section."""
import json,re
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
    if '판금/용접 0회 교환 0회' in whole:
        r['inspection']='플랫폼 진단 요약 확인';r['inspectionFacts']=['KB진단 표시: 판금/용접 0회, 교환 0회','성능점검기록부 원본은 별도 확인 필요']
    r['insuranceCount']=integer(r'보험이력\s*(\d+)건',whole)
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
