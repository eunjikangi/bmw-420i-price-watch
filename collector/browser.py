"""Ordinary Chromium rendering of public pages. No stealth, proxy or login automation."""
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from playwright.sync_api import sync_playwright
from .robots import RobotsPolicy
from .model import canonical,is_target

class BrowserError(Exception):
    def __init__(self,status,note):self.status=status;self.note=note;super().__init__(note)

def safe_text(value):
    value=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?:\+82[- ]?)?0\d{1,2}[- ]?\d{3,4}[- ]?\d{4}','[비공개]',str(value))
    return re.sub(r'\b\d{2,3}[가-힣]\d{4}\b','[차량 식별정보]',value)

class PublicBrowser:
    def __init__(self,fetcher,seconds=240):
        self.fetcher=fetcher;self.deadline=time.monotonic()+seconds;self.attempts=[];self.blocks=[];self.errors=[];self.responses=[];self.policy_cache={};self.last_visit=0
    def __enter__(self):
        self.pw=sync_playwright().start();self.browser=self.pw.chromium.launch(headless=True)
        self.context=self.browser.new_context(locale='ko-KR');self.page=self.context.new_page();self.page.set_default_timeout(10000)
        self.page.on('dialog',lambda dialog:dialog.dismiss())
        self.page.on('requestfailed',lambda request:self.errors.append({'type':request.resource_type,'host':urlsplit(request.url).hostname,'failure':request.failure}) if request.resource_type in ['xhr','fetch','document'] else None)
        self.page.on('response',lambda response:self.responses.append({'status':response.status,'type':response.request.resource_type,'host':urlsplit(response.url).hostname}) if response.status>=400 and response.request.resource_type in ['xhr','fetch','document'] else None)
        self.page.route('**/*',self.route)
        return self
    def __exit__(self,*args):
        try:
            for page in self.context.pages:page.unroute_all(behavior='wait')
            self.context.close();self.browser.close()
        finally:self.pw.stop()
    def allowed(self,url):
        from .run import UA
        if not self.fetcher.allowed(url):raise BrowserError('접근 차단','허용 출처 도메인 외 연결 중단')
        host=urlsplit(url).hostname
        if host not in self.policy_cache:
            # Use the browser's own certificate store; never disable TLS verification.
            try:r=self.context.request.get('https://'+host+'/robots.txt',timeout=16000,max_redirects=4)
            except Exception as e:raise BrowserError('접속 오류','브라우저 robots.txt 연결 실패: '+type(e).__name__)
            if r.status in [401,403,429]:raise BrowserError('접근 차단','robots.txt 접근 제한 (HTTP '+str(r.status)+')')
            if r.status>=500:raise BrowserError('접속 오류','robots.txt 서버 오류')
            rp=RobotsPolicy();rp.parse(r.text().splitlines() if r.status==200 else []);self.policy_cache[host]=rp
        if not self.policy_cache[host].can_fetch(UA,url):raise BrowserError('접근 차단','robots.txt에서 자동 수집을 허용하지 않은 경로')
    def route(self,route):
        req=route.request
        if req.is_navigation_request() and req.frame==self.page.main_frame and req.url!='about:blank':
            try:self.allowed(req.url)
            except BrowserError as e:self.blocks.append(e);route.abort();return
        if req.resource_type in ['image','media','font']:route.abort()
        else:route.continue_()
    def check(self):
        if self.blocks:raise self.blocks[-1]
        t=self.page.title()+' '+self.page.locator('body').first.inner_text(timeout=6000)[:5000]
        if re.search(r'Access Denied|Just a moment|403 Forbidden|보안문자를 입력|자동입력 방지|현재 접속이 제한|비정상적인 트래픽|비정상적인 접근|서비스 이용 제한됨|로봇 여부 확인|Verify you are human|Checking your browser',t,re.I):raise BrowserError('접근 차단','사이트의 접속 제한·보안 확인 안내')
        if re.search(r'로그인(?:이| 후 이용이| 후 조회가) 필요|앱에서만 (?:확인|이용)|앱으로만|로그인 후, 확인해보세요',t):raise BrowserError('로그인·앱 인증 필요','공개 화면에 로그인·앱 이용 필요 안내')
    def goto(self,url):
        if time.monotonic()>self.deadline:raise BrowserError('일부만 조회','사이트별 최대 실행시간 도달. 이전 자료 보존')
        self.allowed(url);self.blocks=[];self.errors=[];self.responses=[]
        self.page.wait_for_timeout(max(0,int((.8-(time.monotonic()-self.last_visit))*1000)))
        self.last_visit=time.monotonic()
        response=self.page.goto(url,wait_until='domcontentloaded',timeout=30000)
        if response and response.status in [401,403,429]:raise BrowserError('로그인·앱 인증 필요' if response.status==401 else '접근 차단','브라우저 HTTP '+str(response.status))
        if response and response.status>=400:raise BrowserError('접속 오류','브라우저 HTTP '+str(response.status))
        self.page.wait_for_timeout(1800);self.check();return self.page
    def settle(self):self.page.wait_for_timeout(1800);self.check()
    def snapshot(self,source,stage):
        folder=Path(__file__).parent/'cache'/source;folder.mkdir(parents=True,exist_ok=True)
        (folder/(stage+'.html')).write_text(self.page.content())
        return {'url':self.page.url,'title':self.page.title(),'text':self.page.locator('body').first.inner_text()[:24000],'inputs':self.page.locator('input:visible').evaluate_all('(xs)=>xs.map(x=>({id:x.id,name:x.name,type:x.type,placeholder:x.placeholder,value:x.type==="text"?x.value:undefined}))'),'controls':self.page.locator('button:visible, a:visible, select:visible').evaluate_all('(xs)=>xs.map(x=>({tag:x.tagName,text:x.innerText.trim().slice(0,100),href:x.getAttribute("href"),id:x.id})).filter(x=>x.text).slice(0,180)'),'errors':self.errors[:8],'responses':self.responses[:8]}
    def links(self):
        return self.page.locator('a[href]').evaluate_all('(xs)=>xs.map(x=>({url:x.href,title:x.innerText.trim()})).filter(x=>x.url.startsWith("https://"))')
