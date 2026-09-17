'use strict';

let leadSort='listingPrice',leadDirection='asc',leadRegion='';
function browserLeads(){return (data.leads||[]).filter(l=>l.evidence==='헤드리스 검색 목록 확인');}
function searchLeadsView(){
 const all=browserLeads(),ls=all.filter(l=>!leadRegion||l.region===leadRegion);const key=leadSort,dir=leadDirection==='asc'?1:-1;const value=l=>key==='listingPrice'&&(l.priceConflict||/리스|렌트|월/.test(l.listingPriceKind))?null:l[key];ls.sort((a,b)=>{const x=value(a),y=value(b);return x==null?(y==null?0:1):y==null?-1:typeof x==='string'?x.localeCompare(y)*dir:(x-y)*dir;});const info=data.sources.find(s=>s.id==='encar')?.browserSearch;const latest=data.runs?.at(-1)||{};const controls='<div class="lead-controls"><label>목록 정렬 기준<select id="lead-sort">'+[['listingPrice','광고가격'],['registration','최초등록'],['mileage','주행거리']].map(([v,t])=>'<option value="'+v+'"'+(leadSort===v?' selected':'')+'>'+t+'</option>').join('')+'</select></label><label>목록 정렬 방향<select id="lead-direction"><option value="asc"'+(leadDirection==='asc'?' selected':'')+'>오름차순</option><option value="desc"'+(leadDirection==='desc'?' selected':'')+'>내림차순</option></select></label><label>목록 판매 지역<select id="lead-region"><option value="">전국</option>'+[...new Set(all.map(l=>l.region).filter(Boolean))].sort().map(r=>'<option value="'+esc(r)+'"'+(leadRegion===r?' selected':'')+'>'+esc(r)+'</option>').join('')+'</select></label><p>전체 '+all.length+'개 · 이번 검색 확인 '+all.filter(l=>!l.stale).length+'개<br>목록 신규 '+Number(latest.listingNewCount||0)+'개 · 가격 변경 '+Number(latest.listingPriceChangeCount||0)+'개</p></div>';
 return '<div class="search-leads-intro"><div><h2>검색 목록에서 찾은 후보</h2><p>엔카의 실제 모델·등급 필터를 적용한 검색 결과입니다. 상세페이지 확인 자료와 분리해 보여드립니다.</p></div><strong>'+ls.length+'<small>개 목록 후보</small></strong></div><p class="notice">외장색·사고·보험·보증은 목록만으로 판단하지 않습니다. 아래 가격은 검색 목록의 광고값이며, 실제 판매 상태와 금융 조건 없는 현금가격은 미확인입니다.</p>'+controls+'<div class="table-wrap"><table class="search-leads-table"><thead><tr><th>차량 / 매물 ID</th><th class="num">목록 광고금액</th><th>최초등록 / 모델연도</th><th class="num">주행거리</th><th>지역</th><th>목록 확인 시각</th><th>원문 / 확인</th></tr></thead><tbody>'+ls.map(l=>{const r=data.records.find(r=>r.sourceId==='encar'&&r.listingId===l.listingId);return '<tr><td><strong>'+esc(l.title)+'</strong><span class="cell-note">'+esc(l.source)+' · '+esc(l.listingId)+'</span></td><td class="num"><strong>'+(l.listingPrice!=null?won(l.listingPrice):l.monthlyPayment?'월 '+won(l.monthlyPayment):'미확인')+'</strong><span class="cell-note">'+(l.listingPrice!=null||l.monthlyPayment?'만원 · ':'')+esc(l.listingPriceKind||'가격 종류 미확인')+'</span>'+(l.priceConflict?'<span class="cell-note error">목록 가격 불일치</span>':'')+listingPriceHistory(l)+'</td><td>'+val(l.registration)+'<span class="cell-note">모델연도 '+val(l.modelYear)+'</span></td><td class="num">'+n(l.mileage)+'<span class="cell-note">km</span></td><td>'+val(l.region)+'</td><td><span class="badge">'+(l.stale?'이전 목록 자료':'목록 확인')+'</span><span class="cell-note time-display">'+time(l.checkedAt)+'</span><span class="cell-note">'+esc(l.searchNote||'상세 검증 전')+'</span></td><td>'+link(l.url,'상세 원문')+'<span class="cell-note">'+link(l.searchUrl,'검색 결과')+'</span>'+(r?'<button class="detail-button" data-record="'+esc(r.id)+'">이전 상세 자료</button>':'')+'</td></tr>';}).join('')+'</tbody></table></div>'+(ls.length?'':'<div class="empty">최근 정상 확인한 브라우저 검색 자료가 없습니다.</div>')+'<p class="subnote">'+esc(info?.method||'브라우저 검색')+' · '+Number(info?.pages||0)+'페이지 · '+esc(info?.status||'미확인')+'. 검색되지 않았다는 이유만으로 판매완료 처리하지 않습니다.</p>';
}
function listingPriceHistory(l){
 const obs=l.listingObservations||[];if(obs.length<2)return '<span class="cell-note">가격 변동 관측 이력 없음</span>';
 return '<details class="listing-history"><summary>목록 관측 '+obs.length+'회</summary>'+obs.map(o=>'<span class="cell-note">'+time(o.checkedAt)+' · '+(o.listingPrice==null?'가격 미확인':won(o.listingPrice)+'만원')+(o.priceConflict?' · 불일치':'')+'</span>').join('')+'</details>';
}
function listingObservationPanel(r){
 const last=r.lastListingObservation;if(!last)return '';
 return '<h3>최근 검색 목록 관측</h3><p class="quiet">상세페이지 확인과 다른 근거입니다. 상세의 마지막 정상 확인 시각은 갱신하지 않았습니다.</p>'+factRows([['목록 확인 시각',fulltime(last.checkedAt)],['목록 광고금액',last.listingPrice==null?null:(last.listingPrice/10000).toLocaleString()+'만원'],['가격 종류',last.listingPriceKind],['목록 주행거리',last.mileage==null?null:last.mileage.toLocaleString()+'km'],['상세가격과 차이',last.listingPrice!=null&&r.price!=null&&last.listingPrice!==r.price?'가격이 다릅니다. 최신 조건 재확인 필요':'차이 확인되지 않음 · 현금가격 확정 아님']])+'<p>'+link(last.searchUrl,'실제 검색 결과')+'</p>'+listingPriceHistory(r);
}


let aiSummary=null;

function aiReviewCurrent(){return aiSummary.bands.flatMap(b=>[b.primary,b.alternative].filter(Boolean)).every(p=>aiBasisMatches(p,data.records.find(r=>r.id===p.id)));}
function aiQuickTable(){
 const current=aiReviewCurrent();
 return '<div class="table-wrap ai-quick-wrap"><table class="ai-quick-table"><thead><tr><th>작성 시점 가격대</th><th>검토 후보</th><th class="num">관측 광고가격</th><th>연식 · 주행거리</th><th>이력 / 우선 확인</th><th>확인</th></tr></thead><tbody>'+aiSummary.bands.map(b=>{const r=data.records.find(r=>r.id===b.primary.id);if(!r)return '<tr><td>'+esc(b.label)+'</td><td colspan="5">후보 자료 없음 · 추천 재확인 필요</td></tr>';return '<tr><td><strong>'+esc(b.label)+'</strong><span class="cell-note">'+(current?esc(b.tag):'추천 재확인 필요')+'</span></td><td><span>'+val(r.trim)+'</span><span class="cell-note">'+val(r.color)+' · '+esc(r.source)+'</span></td><td class="num"><strong>'+won(r.price)+'</strong><span class="cell-note">만원 · 추가비용 별도</span>'+(r.stale?'<span class="cell-note warn">이전 상세 자료</span>':'')+'</td><td><span class="year-chip">'+val(r.modelYear)+'</span><span class="cell-note">'+n(r.mileage)+' km</span></td><td>'+evidenceBadge(r)+'<span class="cell-note">'+(r.stale?'판매 가능 여부 재확인':'보험 수리 내역 확인')+'</span></td><td><button class="detail-button" data-record="'+esc(r.id)+'">상세 보기</button></td></tr>';}).join('')+'</tbody></table></div>';
}

function aiBasisMatches(p,r){if(!r)return false;const l=r.lastListingObservation;if(l&&((l.listingPrice!=null&&l.listingPrice!==p.basis.price)||(l.mileage!=null&&l.mileage!==p.basis.mileage)||l.priceConflict||(/리스|렌트|월/.test(l.listingPriceKind)&&!finance(r))))return false;return Object.entries(p.basis).every(([k,v])=>JSON.stringify(r[k]??null)===JSON.stringify(v));}
function aiPick(p,alternative=false){
 const r=data.records.find(r=>r.id===p.id);if(!r)return '<p class="notice">현재 자료에서 후보를 찾지 못했습니다. 추천 재확인이 필요합니다.</p>';
 const same=aiReviewCurrent();
 return '<div class="ai-pick '+(alternative?'is-alternative':'')+'">'+(alternative?'<span class="alternative-label">함께 볼 대안</span>':'')+'<div class="ai-pick-heading"><div><span class="eyebrow">'+esc(r.source)+' · '+esc(r.listingId)+'</span><button class="row-open" data-record="'+esc(r.id)+'">'+val(r.trim)+' <span class="color-tag">'+val(r.color)+'</span></button></div><strong>'+won(r.price)+'<small>만원</small></strong></div><div class="ai-specs"><span><b>'+val(r.modelYear)+'</b>년형</span><span><b>'+n(r.mileage)+'</b>km</span></div>'+evidenceBadge(r)+'<p class="ai-read-state '+(r.stale?'is-stale':'')+'">'+(r.stale?'이전 자료 · 판매 가능 여부 재확인':'마지막 정상 조회에서 광고 확인')+' · '+time(r.lastSuccess)+'</p>'+(same?'<p class="ai-reason">'+esc(p.reason)+'</p><p class="ai-caution"><strong>확인할 점</strong> '+esc(p.caution)+'</p>':'<p class="notice">AI 요약 이후 가격·제원·판매 상태 또는 이력 정보가 달라졌습니다. 이전 추천 문구를 숨겼습니다. 현재 상세 자료를 다시 확인해 주세요.</p>')+'<button class="text-button" data-record="'+esc(r.id)+'">상세·이력 확인 <span aria-hidden="true">→</span></button></div>';
}
function aiOverview(){
 if(!aiSummary)return '<div class="empty">AI 요약을 불러오지 못했습니다. 중고차 비교에서 공개 자료를 확인할 수 있습니다.</div>';
 const picks=aiSummary.bands.flatMap(b=>[b.primary,b.alternative].filter(Boolean));
 const changed=picks.filter(p=>!aiBasisMatches(p,data.records.find(r=>r.id===p.id))).length;
 return '<section class="ai-overview"><div class="ai-intro"><div><span class="ai-label">AI 요약</span><span class="quiet">작성 '+time(aiSummary.generatedAt)+' KST</span></div><h2>'+(changed?'자료가 달라진 후보의 추천은 다시 확인해야 합니다.':esc(aiSummary.title))+'</h2><p>'+esc(aiSummary.context)+'</p><div class="ai-scope"><span>기준 자료 '+fulltime(aiSummary.dataAt)+' KST</span><span>흰색 우선 · 일반 판매 광고 기준</span></div></div>'+aiQuickTable()+'<details class="ai-reasons"><summary>가격대별 추천 이유와 대안 자세히 보기</summary><div class="ai-band-grid">'+aiSummary.bands.map(b=>{const valid=!changed;return '<article class="ai-band"><div class="band-heading"><div><h3>'+esc(b.label)+'</h3><span>'+(changed?'추천 재확인 필요':esc(b.tag))+'</span></div><span class="band-number">'+(b.min/10000000||'<4')+'</span></div>'+aiPick(b.primary)+(b.alternative?aiPick(b.alternative,true):'')+(valid?'<p class="band-verdict">'+esc(b.verdict)+'</p>':'<p class="band-verdict warn">추천 근거 재확인 필요</p>')+'</article>';}).join('')+'</div></details><div class="ai-boundaries"><p>'+esc(aiSummary.unranked)+'</p><p>'+esc(aiSummary.leaseNote)+'</p><p class="quiet">AI 요약은 위 작성 시점의 검토 메모입니다. 매일 수집 프로그램은 자료를 갱신하며, 비교에 쓴 후보의 근거가 달라지면 기존 추천 문구를 숨깁니다. 자동 수집이 매번 AI 요약을 새로 작성하는 것은 아닙니다.</p></div><button class="primary-button overview-compare" data-open-comparison="true">전체 차량을 표·그래프로 비교 <span aria-hidden="true">→</span></button></section>';
}

let comparisonView='table', graphAxis='mileage', graphColor='history', graphSelected=null;
const evidenceKinds={
 repair:{label:'손상·수리 설명',color:'#c35944',note:'판매자 설명 또는 공개 기재. 수리 완료·사고 범위 별도 확인'},
 insurance:{label:'보험처리 있음',color:'#b27b20',note:'보험처리 공개. 사고 부위·수리 범위 별도 확인'},
 zero:{label:'보험 0건 공개',color:'#287bb8',note:'보험 0건은 무사고·무도색 확정이 아님'},
 claim:{label:'판매자 설명만',color:'#8971ad',note:'무사고 등 판매자 설명. 점검기록 근거 미확인'},
 unknown:{label:'이력 미확인',color:'#8a97a5',note:'사고·보험 근거가 충분히 공개되지 않음'}
};
function historySignal(r){
 if(r.repair)return 'repair';
 if(Number.isInteger(r.insuranceCount)&&r.insuranceCount>0)return 'insurance';
 if(r.insuranceCount===0)return 'zero';
 if(r.accident||r.sellerClaims?.some(s=>/무사고|사고|수리/.test(s)))return 'claim';
 return 'unknown';
}
function evidenceBadge(r){const k=historySignal(r),h=evidenceKinds[k];return '<span class="evidence '+k+'" title="'+esc(h.note)+'"><i aria-hidden="true"></i>'+h.label+'</span>';}
function inlineMeter(value,max,type){if(value==null||!Number.isFinite(max)||max<=0)return '';return '<span class="mini-meter '+type+'" aria-hidden="true"><i style="width:'+Math.min(100,Math.max(0,value/max*100))+'%"></i></span>';}
function graphEligible(rs){return rs.filter(r=>!finance(r)&&!r.priceConflict&&Number.isFinite(r.price)&&r.price>0&&Number.isFinite(r[graphAxis]));}
function numericScale(max){if(max<=0)return {max:1,step:0.25};const raw=max/4,power=10**Math.floor(Math.log10(raw)),step=[1,2,2.5,5,10].find(v=>v*power>=raw)*power;return {max:Math.ceil(max/step)*step,step};}
function graphPointStyle(r,years){
 if(graphColor==='history')return {color:evidenceKinds[historySignal(r)].color,label:evidenceKinds[historySignal(r)].label};
 if(graphColor==='exterior')return {color:isWhite(r)?'#2779c3':r.color?'#657080':'#aab3bf',label:isWhite(r)?'흰색 계열':r.color?'다른 색상':'색상 미확인'};
 const palette=['#d2d9e3','#99b1c9','#638bb2','#3973a7','#245987','#143e65'];
 return {color:palette[Math.min(years.indexOf(r.modelYear),palette.length-1)]||'#9ca7b5',label:r.modelYear?r.modelYear+'년형':'연식 미확인'};
}
function graphLegend(years){let entries=graphColor==='history'?Object.entries(evidenceKinds).map(([key,v])=>({label:v.label,color:v.color})):graphColor==='exterior'?[{label:'흰색 계열',color:'#2779c3'},{label:'다른 색상',color:'#657080'},{label:'색상 미확인',color:'#aab3bf'}]:years.map(y=>graphPointStyle({modelYear:y},years)).concat([{label:'연식 미확인',color:'#9ca7b5'}]);
 return '<div class="plot-legend">'+entries.map(v=>'<span><i style="--swatch:'+v.color+'"></i>'+esc(v.label)+'</span>').join('')+'<span><i class="stale-key"></i>이전 확인 자료</span></div>';
}
function scatter(rs){
 const points=graphEligible(rs),years=[...new Set(points.map(r=>r.modelYear).filter(Number.isFinite))].sort((a,b)=>a-b);
 const excluded=rs.length-points.length;
 const y=numericScale(Math.max(0,...points.map(r=>r.price/10000)));
 let xMin=0,xMax,xStep;
 if(graphAxis==='modelYear'){xMin=Math.min(...points.map(r=>r.modelYear))-0.5;xMax=Math.max(...points.map(r=>r.modelYear))+0.5;xStep=1;}
 else{const x=numericScale(Math.max(0,...points.map(r=>r.mileage)));xMax=x.max;xStep=x.step;}
 let plot='';
 if(points.length){
  for(let v=0;v<=y.max+y.step/10;v+=y.step){const pct=v/y.max*100;plot+='<div class="grid-line y-grid" style="bottom:'+pct+'%"><span>'+v.toLocaleString('ko-KR')+'</span></div>';}
  const start=graphAxis==='modelYear'?Math.ceil(xMin):0;
  for(let v=start;v<=xMax;v+=xStep){const pct=(v-xMin)/(xMax-xMin)*100;plot+='<div class="grid-line x-grid" style="left:'+pct+'%"><span>'+(graphAxis==='modelYear'?v:v===0?'0':(v/10000)+'만')+'</span></div>';}
  plot+=points.map(r=>{const x=(r[graphAxis]-xMin)/(xMax-xMin)*100,p=r.price/10000/y.max*100,style=graphPointStyle(r,years);const description=(r.modelYear||'연식 미확인')+' · '+(r.trim||'트림 미확인')+' · '+won(r.price)+'만원 · '+n(r.mileage)+'km · '+r.source+' '+r.listingId;
   return '<button class="plot-point '+(r.stale?'is-stale ':'')+(graphSelected===r.id?'is-selected ':'')+(x>65?'tip-left ':'')+(p>72?'tip-bottom ':'')+'" data-point="'+esc(r.id)+'" aria-label="'+esc(description+' 선택')+'" aria-pressed="'+(graphSelected===r.id)+'" style="left:'+x+'%;bottom:'+p+'%;--point-color:'+style.color+'"><span class="point-center"></span><span class="point-tip"><strong>'+won(r.price)+'만원</strong><span>'+val(r.modelYear)+'년형 · '+n(r.mileage)+'km</span><span>'+evidenceKinds[historySignal(r)].label+'</span><small>'+esc(r.source)+' '+esc(r.listingId)+(r.stale?' · 이전 자료':'')+'</small></span></button>';}).join('');
 }
 return '<section class="chart-panel main-chart"><div class="panel-heading"><div><h2>가격과 '+(graphAxis==='mileage'?'주행거리':'연식')+'</h2><p>점 하나가 차량 한 대입니다. 점을 선택해 세부 정보를 확인하세요.</p></div><span class="count-label">'+points.length+'대 표시</span></div><div class="chart-controls"><div class="segmented" role="group" aria-label="그래프 가로축"><button data-axis="mileage" aria-pressed="'+(graphAxis==='mileage')+'">주행거리</button><button data-axis="modelYear" aria-pressed="'+(graphAxis==='modelYear')+'">모델연도</button></div><label>색상 구분 <select id="graph-color"><option value="history"'+(graphColor==='history'?' selected':'')+'>사고·보험 정보</option><option value="year"'+(graphColor==='year'?' selected':'')+'>모델연도</option><option value="exterior"'+(graphColor==='exterior'?' selected':'')+'>외장색</option></select></label></div>'+graphLegend(years)+(points.length?'<div class="plot-shell"><span class="axis-title y-title">광고가격 · 만원</span><div class="scatter-plot" role="group" aria-label="차량별 가격 분포">'+plot+'</div><span class="axis-title x-title">'+(graphAxis==='mileage'?'주행거리 · km':'모델연도')+'</span></div>':'<div class="empty">그래프를 그릴 수 있는 가격·'+(graphAxis==='mileage'?'주행거리':'모델연도')+' 자료가 없습니다.</div>')+'<p class="chart-footnote">제외 '+excluded+'대: 리스·렌트, 가격 조건 불일치 또는 축 값 미확인. 광고가격이며, 총구매비용이나 실거래가가 아닙니다.</p></section>';
}
function graphSelection(r){
 if(!r)return '<div class="selection-empty"><span class="selection-symbol" aria-hidden="true">＋</span><h3>차량을 선택하세요</h3><p>그래프의 점이나 아래 목록에서 선택하면 가격·연식·주행거리·이력을 함께 볼 수 있습니다.</p></div>';
 return '<div class="selection-top"><span class="eyebrow">'+esc(r.source)+' · '+esc(r.listingId)+'</span><h3>420i 컨버터블<br>'+val(r.trim)+'</h3><div class="selection-price">'+won(r.price)+'<small>만원</small></div><span class="quiet">관측 광고가격 · 추가비용 별도</span></div><dl class="selection-specs"><div><dt>모델연도</dt><dd>'+val(r.modelYear)+'</dd></div><div><dt>주행거리</dt><dd>'+n(r.mileage)+' <small>km</small></dd></div><div><dt>외장색</dt><dd>'+val(r.color)+'</dd></div><div><dt>판매지역</dt><dd>'+val(r.region)+'</dd></div></dl><div class="selection-evidence">'+evidenceBadge(r)+'<p>'+esc(evidenceKinds[historySignal(r)].note)+'</p><span class="cell-note">'+esc(r.inspection)+'</span></div><div class="selection-fresh '+(r.stale?'is-stale':'')+'">'+(r.stale?'이전 정상 자료 보존':'이번 조회 확인')+'<small>정상 확인 '+time(r.lastSuccess)+'</small></div><button class="primary-button" data-record="'+esc(r.id)+'">차량 상세·원문 확인 <span aria-hidden="true">↗</span></button>';
}
function selectGraphRecord(id){
 const r=graphEligible(rows()).find(r=>r.id===id);graphSelected=r?.id||null;
 const panel=$('#graph-selection');if(panel)panel.innerHTML=graphSelection(r);
 const select=$('#graph-record-select');if(select)select.value=graphSelected||'';
 document.querySelectorAll('[data-point]').forEach(p=>{p.classList.toggle('is-selected',p.dataset.point===graphSelected);p.setAttribute('aria-pressed',String(p.dataset.point===graphSelected));});
}
function yearDistribution(rs){
 const eligible=rs.filter(r=>!finance(r)&&!r.priceConflict&&Number.isFinite(r.price)&&Number.isFinite(r.modelYear));
 const years=[...new Set(eligible.map(r=>r.modelYear))].sort((a,b)=>a-b),max=Math.max(1,...eligible.map(r=>r.price/10000));
 return '<section class="chart-panel"><div class="panel-heading"><div><h2>연식별 광고가격 범위</h2><p>선은 최저–최고 관측값, 점은 중앙값입니다.</p></div></div><div class="range-chart">'+(years.length?years.map(y=>{const ps=eligible.filter(r=>r.modelYear===y).map(r=>r.price/10000).sort((a,b)=>a-b),mid=(ps[Math.floor((ps.length-1)/2)]+ps[Math.floor(ps.length/2)])/2;return '<div class="range-row"><span>'+y+'<small>'+ps.length+'대</small></span><div class="range-track" aria-label="'+y+'년형 '+ps[0]+'만원부터 '+ps.at(-1)+'만원, 중앙값 '+mid+'만원"><i style="left:'+ps[0]/max*100+'%;width:'+(ps.at(-1)-ps[0])/max*100+'%"></i><b style="left:'+mid/max*100+'%"></b></div><strong>'+ps[0].toLocaleString()+(ps[0]!==ps.at(-1)?'–'+ps.at(-1).toLocaleString():'')+'<small>만원</small></strong></div>';}).join(''):'<p class="quiet">확인된 가격·연식 자료가 없습니다.</p>')+'</div><p class="chart-footnote">0–'+Math.ceil(max).toLocaleString()+'만원 공통 척도 · 트림·상태·판매 조건이 서로 다릅니다.</p></section>';
}
function historyDistribution(rs){
 const counts=Object.keys(evidenceKinds).map(k=>({key:k,count:rs.filter(r=>historySignal(r)===k).length}));
 return '<section class="chart-panel"><div class="panel-heading"><div><h2>사고·보험 정보 확인 범위</h2><p>필터에 맞는 '+rs.length+'대 · 차량당 하나의 분류</p></div></div><div class="evidence-distribution">'+counts.map(({key,count})=>'<div class="evidence-row"><span><i style="--swatch:'+evidenceKinds[key].color+'"></i>'+evidenceKinds[key].label+'</span><div class="evidence-track"><i style="background:'+evidenceKinds[key].color+';width:'+(rs.length?count/rs.length*100:0)+'%"></i></div><strong>'+count+'<small>대</small></strong></div>').join('')+'</div><p class="chart-footnote">사고율 그래프가 아닙니다. 보험 0건·판매자 무사고 설명은 점검기록으로 확인한 무사고와 다릅니다. 손상·수리 설명이 있으면 우선 분류합니다.</p></section>';
}
function graphs(rs){
 const pts=graphEligible(rs);if(!pts.some(r=>r.id===graphSelected))graphSelected=null;
 return '<div class="graph-dashboard"><div class="graph-main">'+scatter(rs)+'<aside class="chart-panel selection-panel"><label class="selection-picker">그래프 차량 선택<select id="graph-record-select"><option value="">차량 선택</option>'+pts.map(r=>'<option value="'+esc(r.id)+'"'+(r.id===graphSelected?' selected':'')+'>'+won(r.price)+'만원 · '+(r.modelYear||'연식 미확인')+' · '+esc(r.source)+' '+esc(r.listingId)+'</option>').join('')+'</select></label><div id="graph-selection">'+graphSelection(pts.find(r=>r.id===graphSelected))+'</div></aside></div><div class="graph-secondary">'+yearDistribution(rs)+historyDistribution(rs)+'</div><details class="graph-data-table"><summary>그래프와 함께 비교 표 보기 <span>'+rs.length+'대</span></summary>'+table(rs)+'</details></div>';
}
function wireVisuals(){
 $('#view-switch').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(b){comparisonView=b.dataset.view;render();}});
 $('#content').addEventListener('click',e=>{const axis=e.target.closest('[data-axis]');if(axis){graphAxis=axis.dataset.axis;render();return;}const p=e.target.closest('[data-point]');if(p){const nearest=e.detail?[...document.querySelectorAll('[data-point]')].map(node=>{const r=node.getBoundingClientRect();return {id:node.dataset.point,d:Math.hypot(e.clientX-r.left-r.width/2,e.clientY-r.top-r.height/2)};}).sort((a,b)=>a.d-b.d)[0]:null;selectGraphRecord(nearest?.id||p.dataset.point);}});
 $('#content').addEventListener('focusin',e=>{const p=e.target.closest('[data-point]');if(p)selectGraphRecord(p.dataset.point);});
 $('#content').addEventListener('change',e=>{if(e.target.id==='lead-sort'){leadSort=e.target.value;render();}if(e.target.id==='lead-direction'){leadDirection=e.target.value;render();}if(e.target.id==='lead-region'){leadRegion=e.target.value;render();}if(e.target.id==='graph-color'){graphColor=e.target.value;render();}if(e.target.id==='graph-record-select')selectGraphRecord(e.target.value);});
}
