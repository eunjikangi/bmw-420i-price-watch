'use strict';
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const unknown='<span class="unknown">미확인</span>';
const val=v=>v===null||v===undefined||v===''?unknown:esc(v);
const n=v=>v==null?unknown:Number(v).toLocaleString('ko-KR');
const won=v=>v==null?unknown:(Number(v)/10000).toLocaleString('ko-KR',{maximumFractionDigits:2});
const time=v=>v?new Date(v).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'미확인';
const fulltime=v=>v?new Date(v).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false}):'미확인';
const isWhite=r=>/흰색|백색|화이트|\bwhite\b/i.test(r.color||'');
const wasListed=r=>r.status==='광고 게시 중'||(r.stale&&[...(r.observations||[])].reverse().find(o=>o.kind==='관측 광고가격')?.status==='광고 게시 중');
const finance=r=>/리스|렌트|월납입|구독/.test(r.priceKind+' '+r.saleMethod);
const link=(u,label)=>/^https:\/\//.test(u||'')?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:esc(label);
let data,tab='all',filters={},sort='white',lastFocus;
const sortModes={price:{asc:'price-up',desc:'price-down'},year:{asc:'year-up',desc:'year'},mileage:{asc:'mileage',desc:'mileage-down'}};
function syncSortControls(){const field=Object.keys(sortModes).find(k=>Object.values(sortModes[k]).includes(sort));$('#sort').value=field||'white';$('#sort-direction').disabled=!field;$('#sort-direction').value=field&&sortModes[field].desc===sort?'desc':'asc';}
function changeSort(){const field=$('#sort').value;sort=field==='white'?'white':sortModes[field][$('#sort-direction').value];render();}
const enums={color:['전체 색상','흰색 계열','흰색 외','미확인'],region:['전국','서울','경기','인천','부산','대구','대전','광주','울산','세종','강원','충북','충남','전북','전남','경북','경남','제주','미확인'],trim:['모든 트림','M Sport','M Sport Pro','미확인'],facelift:['전체','부분변경 전','부분변경 후','미확인'],sale:['모든 구매 방식','일반 광고','현금 판매','할부','금융리스','운용리스','렌트·구독','미확인'],cert:['모든 인증','BMW BPS','KB진단','기타','미확인'],history:['전체','플랫폼 진단 확인','기록부 원본 확인','미확인']};
function select(name,label){return `<label><span>${label}</span><select data-filter="${name}" aria-label="${label}">${enums[name].map((t,i)=>`<option value="${i?esc(t):''}">${esc(t)}</option>`).join('')}</select></label>`;}
function setup(){
 setupFilters();
 $('#sort').addEventListener('change',changeSort);$('#sort-direction').addEventListener('change',changeSort);
 $('#nav').addEventListener('click',e=>{const b=e.target.closest('[data-tab]');if(b){tab=b.dataset.tab;render();b.scrollIntoView({block:'nearest',inline:'nearest'});}});
 $('#content').addEventListener('click',e=>{if(e.target.closest('[data-open-comparison]')){tab='all';render();return;}const b=e.target.closest('[data-record]');if(b)openRecord(b.dataset.record);});
 $('#close-detail').onclick=()=>$('#detail').close();$('#detail').addEventListener('close',()=>lastFocus?.focus());
 $('#detail').addEventListener('click',e=>{if(e.target===$('#detail') && (e.offsetX<0||e.offsetY<0||e.offsetX>e.target.clientWidth||e.offsetY>e.target.clientHeight))e.target.close();});
 wireVisuals();render();registerTools();
}
function comparisonRun(){return [...(data.runs||[])].reverse().find(r=>r.sourceCount===data.sources.length)||data.runs?.at(-1)||{};}
function summary(){
 const leadCount=document.getElementById('lead-count');if(leadCount)leadCount.textContent=browserLeads().length;
 const fresh=data.vehicles.filter(g=>g.offers.some(r=>!r.stale&&r.status==='광고 게시 중'));
 const retained=data.vehicles.filter(g=>g.offers.some(wasListed));const wh=retained.filter(g=>g.offers.some(isWhite));const latest=comparisonRun();
 const status=data.sources.reduce((a,s)=>(a[s.status]=(a[s.status]||0)+1,a),{});
 $('#summary').innerHTML='<div class="stat-grid"><div class="stat"><span>비교 자료</span><strong>'+retained.length+'<small>대</small></strong><p>동일 차량 중복 확인 후</p></div><div class="stat"><span>흰색 계열</span><strong>'+wh.length+'<small>대</small></strong><p>다른 색상도 함께 비교</p></div><div class="stat"><span>정상 확인 자료</span><strong>'+fresh.length+'<small>대</small></strong><p>이전 자료 '+(retained.length-fresh.length)+'대 보존</p></div><div class="stat stat-changes"><span>신규 / 변경</span><strong>'+Number(latest.newCount||0)+'<small>신규</small><b>·</b>'+Number(latest.priceChangeCount||0)+'<small>가격 변경</small></strong><p>최근 전체 조회 기준</p></div></div><div class="source-summary"><span><i class="source-dot"></i>출처 '+(status['조회 성공']||0)+' 성공 · '+(status['일부만 조회']||0)+' 일부 · '+(status['정상 검색 결과 대상 매물 없음']||0)+' 대상 없음 · '+(data.sources.length-(status['조회 성공']||0)-(status['일부만 조회']||0)-(status['정상 검색 결과 대상 매물 없음']||0))+' 제한/오류</span><span>마지막 수집 '+fulltime(data.updatedAt)+' KST</span></div>';
}
function within(v,min,max){if(!min&&!max)return true;if(v==null)return false;return (!min||v>=Number(min))&&(!max||v<=Number(max));}
function match(r){
 const f=filters;
 if(f.color==='흰색 계열'&&!isWhite(r)||f.color==='흰색 외'&&(!r.color||isWhite(r))||f.color==='미확인'&&r.color)return false;
 if((f.priceMin||f.priceMax)&&finance(r))return false;
 if(!within(r.price==null?null:r.price/10000,f.priceMin,f.priceMax)||!within(r.modelYear,f.yearMin,f.yearMax)||!within(r.mileage,f.kmMin,f.kmMax))return false;
 for(const [k,field] of [['region','region'],['trim','trim'],['facelift','facelift']]){if(f[k]&&(f[k]==='미확인'?!!r[field]:(k==='trim'?r[field]!==f[k]:!String(r[field]||'').includes(f[k]))))return false;}
 if(f.cert&&(f.cert==='미확인'?!!r.certification:f.cert==='기타'?(!r.certification||['BMW BPS','KB진단'].includes(r.certification)):!String(r.certification||'').includes(f.cert)))return false;
 if(f.history==='플랫폼 진단 확인'&&!r.inspection.includes('플랫폼')||f.history==='기록부 원본 확인'&&r.inspection!=='기록부 원본 확인'||f.history==='미확인'&&!r.inspection.includes('미확인'))return false;
 if(f.sale){if(f.sale==='일반 광고'&&finance(r))return false;if(f.sale==='미확인'&&!r.saleMethod.includes('미확인'))return false;if(!['일반 광고','미확인'].includes(f.sale)&&!(f.sale==='금융리스'?/금융.*리스/.test(r.saleMethod):r.saleMethod.includes(f.sale.replace('·구독',''))))return false;}
 return true;
}
function rows(){
 let result=data.vehicles.map(g=>{let os=g.offers.filter(r=>match(r)&&wasListed(r));if(tab==='bps')os=os.filter(r=>r.certification==='BMW BPS');if(!os.length)return null;os.sort((a,b)=>Number(a.stale)-Number(b.stale)||new Date(b.lastSuccess)-new Date(a.lastSuccess));return {...os[0],group:g};}).filter(Boolean);
 const nullable=(a,b,dir=1)=>a==null?(b==null?0:1):b==null?-1:(a-b)*dir;
 result.sort((a,b)=>sort==='price-up'||sort==='price-down'?nullable(finance(a)?null:a.price,finance(b)?null:b.price,sort==='price-up'?1:-1):sort==='year'||sort==='year-up'?nullable(a.modelYear,b.modelYear,sort==='year-up'?1:-1):sort==='mileage'||sort==='mileage-down'?nullable(a.mileage,b.mileage,sort==='mileage-down'?-1:1):Number(isWhite(b))-Number(isWhite(a))||Number(a.stale)-Number(b.stale)||new Date(b.lastSuccess)-new Date(a.lastSuccess));
 return result;
}
function priceCell(r){return r.price==null?`<strong>${r.status==='판매완료'?'판매완료':finance(r)?'총비용 미확인':'가격 미확인'}</strong>${r.monthlyPayment?`<span class="cell-note">월 ${won(r.monthlyPayment)}만원</span>`:''}`:`<strong>${won(r.price)}</strong><span class="cell-note ${finance(r)?'warn':''}">${esc(r.priceKind)}</span>${r.priceConflict?'<span class="cell-note error">가격 조건 불일치</span>':''}`;}
function row(r,scale={}){
 const inspection=r.inspection==='기록부 원본 확인'?'기록부 원본 확인':/표시|요약/.test(r.inspection)?'진단 표시 · 원본 미확인':'기록부 미확인';
 return '<tr class="'+(r.stale?'retained-row':'')+'"><td class="model-cell"><span class="eyebrow">'+esc(r.source)+' · '+esc(r.listingId)+'</span><button class="row-open" data-record="'+esc(r.id)+'">420i 컨버터블<span class="trim-name">'+val(r.trim)+'</span></button>'+(r.group?.offers.length>1?'<span class="cell-note">동일 차량 '+r.group.offers.length+'개 출처</span>':'')+(r.group?.duplicateStatus==='중복 추정'?'<span class="badge warn">중복 추정</span>':'')+'</td><td class="num price-cell">'+priceCell(r)+(!finance(r)&&!r.priceConflict?inlineMeter(r.price,scale.price,'price-meter'):'')+'</td><td><span class="year-chip">'+val(r.modelYear)+'</span></td><td class="registration-cell">'+val(r.registration)+'</td><td class="num mileage-cell"><strong>'+n(r.mileage)+'</strong><span class="cell-note">km</span>'+inlineMeter(r.mileage,scale.mileage,'mileage-meter')+'</td><td><span class="color-label"><i class="'+(isWhite(r)?'white-swatch':'other-swatch')+'"></i>'+val(r.color)+'</span></td><td>'+val(r.region)+'</td><td>'+val(r.facelift)+'</td><td class="condition-cell"><span class="'+(finance(r)?'warn':'')+'">'+esc(r.saleMethod)+'</span><span class="cell-note">금융 없는 현금가 '+(r.cashConfirmed?'확인':'미확인')+'</span>'+(finance(r)?'<span class="cell-note warn">총비용 확인 필요</span>':'')+'</td><td class="history-cell">'+evidenceBadge(r)+'<span class="cell-note">'+inspection+'</span>'+(r.certification?'<span class="cert-label">'+esc(r.certification)+'</span>':'')+'</td><td class="check-cell"><span class="state-label '+(r.stale?'is-stale':'')+'">'+(r.stale?'이전 자료 · '+esc(r.status):esc(r.status))+'</span>'+(r.lastListingObservation?'<span class="cell-note listing-note">목록 확인 '+time(r.lastListingObservation.checkedAt)+'</span>':'')+'<span class="cell-note time-display">정상 '+time(r.lastSuccess)+'</span><span class="cell-note time-display">조회 '+time(r.checkedAt)+'</span></td><td class="action-cell">'+link(r.url,'원문')+'<button class="detail-button" data-record="'+esc(r.id)+'">상세·이력</button></td></tr>';
}
function table(rs){
 const scale={price:Math.max(0,...rs.filter(r=>!finance(r)&&!r.priceConflict).map(r=>r.price||0)),mileage:Math.max(0,...rs.map(r=>r.mileage||0))};
 return rs.length?'<div class="table-wrap"><table class="comparison-table"><thead><tr><th>차량 / 출처</th><th class="num">광고가격 <small>만원</small></th><th>모델연도</th><th>최초등록</th><th class="num">주행거리</th><th>외장색</th><th>지역</th><th>부분변경</th><th>판매 조건</th><th>사고·보험 / 점검</th><th>확인 상태</th><th>상세</th></tr></thead><tbody>'+rs.map(r=>row(r,scale)).join('')+'</tbody></table></div>':'<div class="empty">조건에 맞는 확인 자료가 없습니다. 수집 실패나 미확인 자료는 매물 0건의 근거가 아닙니다.</div>';
}

function render(){
 summary();syncSortControls();syncFilterControls();document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-current',b.dataset.tab===tab?'page':'false');});
 const showFilters=['all','recommend','bps'].includes(tab);$('#filters').hidden=!showFilters;$('#sort-label').hidden=!showFilters||(['all','bps'].includes(tab)&&comparisonView==='graph');$('#sort-direction-label').hidden=$('#sort-label').hidden;$('#reset').hidden=!showFilters;
 const supportsView=['all','bps'].includes(tab);$('.toolbar').dataset.view=supportsView?comparisonView:tab;$('#view-switch').hidden=!supportsView;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===comparisonView)));
 let rs=rows();$('#content').dataset.view=(supportsView?comparisonView:tab);$('#result-count').innerHTML=showFilters?`조건에 맞는 차량 <strong>${rs.length}</strong>대 · 금액은 광고값, 추가비용 별도`:'공개 자료와 관측 이력';
 const c=$('#content');
 if(tab==='all'||tab==='bps')c.innerHTML=(comparisonView==='graph'?graphs(rs):table(rs))+`<p class="subnote">${tab==='bps'?'BMW BPS 표시를 확인한 차량만 표시합니다. 인증 표시가 개별 보증 잔여를 뜻하지는 않습니다. ':''}조회 실패 차량은 ‘이전 정상 자료 보존’으로 표시합니다. ‘광고 게시 중’은 상세페이지가 열렸다는 뜻입니다. 금융상품 가입 없는 구매가격·총인수비용·실재고는 별도 확인이 필요합니다. 표의 막대는 현재 표의 최대값 기준입니다. 가로로 스크롤하면 모든 비교 항목을 볼 수 있습니다.</p>`;
 else if(tab==='leads')c.innerHTML=searchLeadsView();
 else if(tab==='overview')c.innerHTML=aiOverview();
 else if(tab==='recommend')c.innerHTML=recommend(rs);
 else if(tab==='new')c.innerHTML=newCars();
 else if(tab==='prices')c.innerHTML=priceHistory();
 else if(tab==='history')c.innerHTML=statusHistory();
 else if(tab==='sources')c.innerHTML=sources();
}
function reason(r){let a=[`${r.modelYear?r.modelYear+'년형':'모델연도 미확인'}, ${r.mileage!=null?r.mileage.toLocaleString()+'km':'주행거리 미확인'}`];if(r.certification)a.push(r.certification+' 표시');if(r.priceConflict)a.push('광고가격 불일치로 가격 추천 보류');if(finance(r))a.push('리스·렌트 총비용 미확인');if(!r.cashConfirmed)a.push('조건 없는 현금 구매가격 미확인');if(r.inspection.includes('미확인'))a.push('기록부 원본 미확인');if(!r.roof)a.push('루프·누수 점검 미확인');return a.join(' · ');}
function recommend(rs){
 const white=rs.filter(r=>isWhite(r)&&!r.stale);const value=white.filter(r=>!finance(r)&&!r.priceConflict);const near=white.filter(r=>Number(r.modelYear)>=new Date().getFullYear()-2&&r.mileage!=null&&r.mileage<=20000);const alt=rs.filter(r=>r.color&&!isWhite(r)&&!r.stale);
 let out='<p class="notice">확인 범위 안의 검토 후보입니다. 조건 없는 현금가·보증·상태 근거가 부족하면 가성비 우위를 확정하지 않습니다.</p>';
 for(const [title,list,explain] of [['흰색 가성비 후보',value,'일반 광고금액을 비교할 수 있는 흰색 차량. 추가비용과 현금가격 확인 후 판단.'],['흰색 신차급 후보',near,'분류 기준: 최근 2개 모델연도 범위·2만 km 이하. 실제 신차 상태나 무사고를 뜻하지 않음.'],['다른 색상까지 포함한 대안',alt,'흰색 대비 가격·상태 우위를 입증하지 못한 차량은 추가 확인 대상으로 표시.']]){
 out+=`<h2>${title}</h2><p class="quiet">${explain}</p>${table(list)}${list.length?`<ul class="quiet">${list.map(r=>`<li><button class="row-open" data-record="${esc(r.id)}">${esc(r.source)} ${esc(r.listingId)}</button> — ${esc(reason(r))}</li>`).join('')}</ul>`:''}`;}
 return out;
}
function newCars(){
 const month=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}).slice(0,7);const entries=data.newCars||[];
 let out='<p class="notice">공식 판매가격 · 광고 할인 · 금융 조건부 가격 · 출고재고 확인 견적을 구분합니다. 현재 확인된 출고 가능 흰색 재고 견적은 없습니다.</p><h2>신차 가격 자료</h2>';
 out+=entries.length?`<div class="table-wrap"><table class="small-table"><thead><tr><th>차량 / 트림</th><th class="num">가격 (만원)</th><th>가격 종류</th><th>기준월</th><th>확인 시각</th><th>재고 / 조건</th><th>출처</th></tr></thead><tbody>${entries.map(p=>`<tr><td>${esc(p.model)}<span class="cell-note">${esc(p.trim)}</span></td><td class="num"><strong>${won(p.price)}</strong></td><td>${esc(p.priceKind)}</td><td>${esc(p.validFrom||p.effectiveMonth)}${p.pricePeriodKind?'<span class="cell-note">'+esc(p.pricePeriodKind)+'</span>':''}${!p.pricePeriodKind&&p.effectiveMonth!==month?'<span class="cell-note warn">이전 기준월 · 이번 달 가격 아님</span>':''}</td><td>${time(p.checkedAt)}</td><td>${esc(p.stock)}<span class="cell-note">${esc(p.conditions)}</span></td><td>${link(p.url,p.source)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">당월 신차 가격을 확인하지 못했습니다. 오래된 프로모션을 이번 달 가격으로 대신하지 않습니다.</div>';
 out+='<h2>함께 비교할 중고차</h2><p class="quiet">트림·모델연도·장비·판매조건이 다르므로 동일 사양의 할인율로 계산하지 않습니다.</p>'+table(data.vehicles.filter(g=>g.offers.some(r=>r.status==='광고 게시 중'&&!r.stale)).map(g=>({...g.offers.find(r=>r.status==='광고 게시 중'&&!r.stale),group:g})));
 out+='<h3>아직 확인되지 않은 가격</h3><div class="table-wrap"><table><thead><tr><th>가격 구분</th><th>확인 상태</th></tr></thead><tbody><tr><td>BMW 공식 당월 판매가격</td><td>미확인</td></tr><tr><td>금융상품 조건부 신차 가격</td><td>미확인</td></tr><tr><td>출고 가능한 흰색 재고 견적</td><td>미확인</td></tr></tbody></table></div>';return out;
}
function priceHistory(){return '<p class="notice">이 사이트가 실제로 관측한 광고가격만 표시합니다. 최초 관측 전의 가격을 복원하지 않으며, 광고가격은 실거래가가 아닙니다.</p>'+data.records.map(r=>`<h3><button class="row-open" data-record="${esc(r.id)}">${esc(r.source)} · ${esc(r.listingId)} · ${esc(r.trim||'트림 미확인')}</button></h3>${observationTable(r)}`).join('');}
function observationTable(r){const obs=r.observations||[];const priced=obs.filter(o=>o.price!=null&&o.kind==='관측 광고가격');const dates=new Set(priced.map(o=>new Date(o.at).toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'})));return (dates.size<2?'<p class="quiet">첫날 관측 자료입니다. 날짜 간 가격 변동 이력이 아직 없습니다.</p>':'')+`<div class="table-wrap"><table class="history-table"><thead><tr><th>실제 관측 시각 (KST)</th><th class="num">관측 광고금액 (만원)</th><th>가격 종류</th><th>상태</th></tr></thead><tbody>${obs.map(o=>`<tr><td>${fulltime(o.at)}</td><td class="num">${o.kind==='조회 실패'?'—':won(o.price)}</td><td>${esc(o.priceKind||o.kind)}</td><td>${esc(o.status)}</td></tr>`).join('')}</tbody></table></div>`;}
function statusHistory(){const ev=data.events.filter(e=>e.type!=='신규');const archived=data.records.filter(r=>r.status!=='광고 게시 중');return (archived.length?'<h2>판매완료·확인불가 차량</h2>'+table(archived):'')+ '<p class="quiet">판매완료는 원문에 명시된 경우만 기록합니다. 삭제·비공개·접근불가·예약중을 별도로 구분하고, 접속 실패 시 이전 정상 자료를 보존합니다.</p>'+(ev.length?`<div class="table-wrap"><table><thead><tr><th>시각</th><th>변경 종류</th><th>차량</th><th>내용</th></tr></thead><tbody>${[...ev].reverse().map(e=>`<tr><td>${fulltime(e.at)}</td><td>${esc(e.type)}</td><td>${e.recordId?`<button class="row-open" data-record="${esc(e.recordId)}">${esc(e.recordId)}</button>`:esc(e.listingId?(data.sources.find(s=>s.id===e.sourceId)?.name||'목록')+' '+e.listingId:'검토 후보 전체')}</td><td>${esc(e.text)}${['가격 변경','목록 가격 변경'].includes(e.type)?`<span class="cell-note">${won(e.before)} → ${won(e.after)}만원</span>`:''}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">첫 관측 이후 기록된 가격·판매 상태 변화가 없습니다.</div>');}
function sources(){
 const scheduled=data.schedule?.status==='활성';let out=`<div class="status-line"><strong>자동 갱신: ${esc(data.schedule?.status||'미설정')}</strong> · ${esc(data.schedule?.description||'')}<br><span class="quiet">수집은 일반 프로그램으로 실행합니다. 매일 AI가 페이지를 읽거나 토큰을 사용하는 방식이 아닙니다.</span></div>`;
 if(data.schedule?.workflowUrl)out+='<p>'+link(data.schedule.workflowUrl,'자동 수집 실행 기록')+'</p>';
 out+='<p class="subnote">로컬 브라우저에서 성공해도 예약 실행 서버에서는 차단될 수 있습니다. 엔카의 최근 GitHub 실행은 접속 제한으로 실패했으며, 실패한 날에는 이전 정상 자료를 보존합니다.</p>';
 if(scheduled)out+='<p class="subnote">예약 시각은 매일 08:00 Asia/Seoul입니다. 실행 플랫폼 상황에 따라 시작이 지연될 수 있습니다.</p>';
 out+=`<div class="table-wrap"><table class="sources"><thead><tr><th>출처</th><th>구분</th><th>이번 조회 상태</th><th>확인 범위 / 한계</th><th>상세 확인</th><th>내부 탐색 / 웹 검색</th><th>이번 조회 (KST)</th><th>마지막 정상 차량 확인</th></tr></thead><tbody>${data.sources.map(s=>`<tr><td>${link(s.url,s.name)}</td><td>${esc(s.kind)}</td><td><span class="badge ${['접근 차단','접속 오류','로그인·앱 인증 필요'].includes(s.status)?'warn':''}">${esc(s.status)}</span></td><td>${esc(s.note)}</td><td>${s.kind==='보완 경로'?'통합 검색과 동일 재고':(s.verifiedCount||0)+'개 상세'}<span class="cell-note">${s.listingCount==null?'전체 매물 수 미확인':'확인 범위 내 결과 '+s.listingCount+'개'}</span></td><td>${s.internalSearch?.pages??'미확인'} 페이지<span class="cell-note">${s.browserSearch?'헤드리스 '+esc(s.browserSearch.status)+' · '+esc(s.executionEnvironment||'실행 환경 미확인'):'HTML 조회'}<br>웹 검색 ${esc(s.webSearch?.status||'미실행')}${s.publicWebReview?'<br>공개 웹 검색 보완 '+fulltime(s.publicWebReview.checkedAt):''}</span></td><td>${fulltime(s.checkedAt)}</td><td>${fulltime(s.lastSuccess)}</td></tr>`).join('')}</tbody></table></div>`;
 out+='<h2>검증 전 검색·목록 자료</h2><p class="quiet">상세페이지 판독 전 자료입니다. 현재 판매 중인 확인 매물 수와 추천에 포함하지 않습니다.</p>';
 out+=(data.leads?.length?`<div class="table-wrap"><table><thead><tr><th>출처</th><th>검색·목록 제목</th><th>확인 한계</th><th>원문</th></tr></thead><tbody>${data.leads.map(l=>`<tr><td>${esc(l.source)}</td><td>${esc(l.title)}</td><td>${esc(l.note||l.evidence)}</td><td>${link(l.url,'열기')}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">추가 검증 대기 자료가 없습니다. 검색 결과가 없다는 의미는 아닙니다.</div>');
 out+='<h2>기록 원칙</h2><ul class="quiet"><li>대상은 420i 컨버터블입니다. 쿠페·그란쿠페·420d·430i·M440i는 제외합니다. 차대코드만으로 판정하지 않습니다.</li><li>흰색은 우선 조건입니다. 예산·연식·주행거리·지역·구매 방식 상한을 기본으로 두지 않습니다.</li><li>판매자 설명, 플랫폼 진단 요약, 성능점검기록부 원본은 서로 다른 근거입니다. 보험 0건은 무사고·무도색 확정이 아닙니다.</li><li>사진만으로 루프 작동·누수·기계 상태를 판정하지 않습니다. 매물 대체 사진을 쓰지 않습니다.</li><li>리스의 선수금·보증금·인수금·월납입금은 차량 전체 가격이 아닙니다. 필수 비용이 빠지면 총비용을 계산하지 않습니다.</li><li>취득·이전·관리·탁송 비용은 차량가격과 분리하며, 확인되지 않은 세금·비용 추정치는 합산하지 않습니다.</li><li>동일 차량은 차량 식별정보가 일치할 때만 묶고, 사이트별 가격·URL·시각을 보존합니다. 유사 제원만 일치하면 중복 추정으로 남깁니다.</li><li>인증이나 접근 제한을 우회하지 않습니다. 동적 검색 자동 판독이 미완성인 출처는 일부 조회로 표시합니다.</li><li>조회 실패 시 마지막 정상 가격과 시각을 그대로 보존합니다. 페이지가 사라져도 판매완료로 단정하지 않습니다.</li></ul>';
 return out;
}
function factRows(items){return `<dl class="facts">${items.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${v===null||v===undefined||v===''?unknown:esc(v)}</dd>`).join('')}</dl>`;}
function openRecord(id){const r=data.records.find(x=>x.id===id);if(!r)return;lastFocus=document.activeElement;$('#detail-title').textContent=r.model;
 const g=data.vehicles.find(g=>g.offers.some(o=>o.id===id));let html=`<p class="quiet">${esc(r.source)} · 매물 ID ${esc(r.listingId)} · ${link(r.url,'실제 상세페이지')}</p>${r.stale?'<p class="notice">이번 조회에서 정상 확인하지 못했습니다. 아래 가격은 마지막 정상 관측 자료입니다.</p>':''}`;
 if(r.originalSourceUrl)html+='<p>'+link(r.originalSourceUrl,'제휴 원 판매처 상세페이지')+'</p>';
 html+=listingObservationPanel(r);
 html+='<h3>가격과 판매 조건</h3>'+factRows([['광고금액',r.price==null?null:(r.price/10000).toLocaleString()+'만원'],['가격 종류',r.priceKind],['판매 방식',r.saleMethod],['금융상품 없는 현금가',r.cashConfirmed?'확인':'미확인'],['추가비용',r.extraCosts],['가격 불일치',r.priceConflict?'상단 광고가격과 판매자 설명이 다름':'확인된 불일치 없음 · 조건 확정 아님']]);
 if(r.extraCostEstimate)html+='<p class="notice">출처의 추가비용 추정: '+won(r.extraCostEstimate.amount)+'만원 · '+esc(r.extraCostEstimate.basis)+' 차량가격과 별도이며 확정 총구매가격이 아닙니다.</p>';
 if(r.priceOptions?.length)html+='<p class="quiet">'+r.priceOptions.map(p=>esc(p.kind)+': '+won(p.amount)+'만원').join('<br>')+'</p>';
 if(finance(r))html+='<h3>리스·렌트 구성 — 총비용 확인 필요</h3>'+factRows([['초기 지급액',r.lease?.initial],['잔여 납입액',r.lease?.remainingPayments],['만기 인수금',r.lease?.buyout],['보증금 반환 조건',r.lease?.depositReturn],['승계·이전 비용',r.lease?.transferCosts],['중도해지 비용',r.lease?.earlyTerminationCosts]]);
 html+='<h3>차량 정보</h3>'+factRows([['정확한 원문 모델명',r.model],['트림',r.trim],['부분변경',r.facelift],['모델연도',r.modelYear],['최초등록 연월',r.registration],['주행거리',r.mileage==null?null:r.mileage.toLocaleString()+'km'],['외장색 / 실내색',(r.color||'미확인')+' / '+(r.interior||'미확인')],['판매지역 / 업체',(r.region||'미확인')+' / '+(r.seller||'미확인')]]);
 html+='<h3>이력과 보증</h3>'+factRows([['성능·상태점검',r.inspection],['점검 근거',r.inspectionFacts?.join(' / ')],['판매자 주장',r.sellerClaims?.join(' / ')],['사고·수리·교환·판금',r.repair||r.accident],['보험처리 건수',r.insuranceCount==null?null:r.insuranceCount+'건'],['보험 금액·수리 내역',r.insuranceDetails],['보험 자료 기준일',r.insuranceAsOf],['렌터카·영업용 이력',r.usage],['소유자 변경 이력',r.owners],['제조사 보증',r.manufacturerWarranty],['인증중고차 보증',r.certifiedWarranty],['정비서비스 잔여',r.serviceRemaining],['루프 작동·누수·수리',r.roof]]);
 if(r.inspectionUrl)html+='<p>'+link(r.inspectionUrl,'출처에 연결된 성능점검기록부')+' · '+esc(r.inspectionDocumentStatus||'원본 자동 판독 미완료')+'</p>';
 html+='<h3>검토 의견</h3><p class="quiet">'+esc(reason(r))+'</p>'+(r.warnings.length?'<ul class="quiet">'+r.warnings.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'');
 html+='<h3>관측 시각</h3>'+factRows([['최초 발견일',fulltime(r.firstSeen)],['마지막 정상 확인',fulltime(r.lastSuccess)],['이번 조회',fulltime(r.checkedAt)],['판매 상태',r.status]]);
 html+='<h3>관측 광고가격</h3>'+observationTable(r);
 if(g?.offers.length>1)html+='<h3>같은 차량의 출처별 가격</h3>'+table(g.offers);
 $('#detail-body').innerHTML=html;$('#detail').showModal();$('#detail').scrollTop=0;
}
function registerTools(){const ctx=document.modelContext;if(!ctx?.registerTool)return;const ac=new AbortController();window.addEventListener('pagehide',()=>ac.abort(),{once:true});
 Promise.resolve(ctx.registerTool({name:'filter_420i_listings',description:'420i 비교 표의 색상 필터와 가격·모델연도·주행거리 정렬을 변경하고 보이는 매물 요약을 반환합니다.',inputSchema:{type:'object',properties:{color:{type:'string',enum:['all','white','other']},sort:{type:'string',enum:['white','price-up','price-down','year-up','year','mileage','mileage-down']}},additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:true},execute(input){if(!input||typeof input!=='object'||Object.keys(input).some(k=>!['color','sort'].includes(k))||input.color&&!['all','white','other'].includes(input.color)||input.sort&&!['white','price-up','price-down','year-up','year','mileage','mileage-down'].includes(input.sort))throw Error('유효하지 않은 필터');tab='all';if(input.color){filters.color={all:'',white:'흰색 계열',other:'흰색 외'}[input.color];$('[data-filter="color"]').value=filters.color;}if(input.sort){sort=input.sort;$('#sort').value=sort;}render();return rows().map(r=>({id:r.id,price:r.price,priceKind:r.priceKind,year:r.modelYear,mileage:r.mileage,source:r.source,url:r.url}));}},{signal:ac.signal})).catch(()=>{});
}
async function load(){
 let local;try{const r=await fetch('./data.json',{cache:'no-store'});if(!r.ok)throw Error('자료 요청 실패');local=await r.json();data=local;try{aiSummary=await fetch('./ai-summary.json',{cache:'no-store'}).then(r=>r.ok?r.json():null);}catch{}setup();}catch{throw Error('현재 데이터를 불러올 수 없습니다. 잠시 후 새로고침해 주세요.');}
 try{const config=await fetch('./data-source.json',{cache:'no-store'}).then(r=>r.ok?r.json():{});if(config.url){const remote=await fetch(config.url+'?t='+Math.floor(Date.now()/300000),{signal:AbortSignal.timeout(10000)});if(!remote.ok)throw Error('원격 응답 오류');const d=await remote.json();if(d.schemaVersion!==1||!Array.isArray(d.records)||!Array.isArray(d.vehicles)||!Array.isArray(d.sources))throw Error('자료 형식 오류');if(new Date(d.updatedAt)>=new Date(local.updatedAt))data=d;}}
 catch{$('#load-note').hidden=false;$('#load-note').textContent='최신 데이터 연결에 실패했습니다. 사이트에 저장된 마지막 정상 자료를 표시합니다. 확인 시각은 갱신하지 않았습니다.';}
 if(Date.now()-new Date(data.updatedAt)>36*3600000){$('#load-note').hidden=false;$('#load-note').textContent='마지막 수집 후 36시간이 지났습니다. 오래된 자료입니다. 출처별 확인 시각을 확인해 주세요.';}
 render();
}
load().catch(e=>{$('#summary').textContent=e.message;});
