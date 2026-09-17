'use strict';

const quickRanges = {
 price: {label:'가격', title:'가격대 선택', note:'관측 광고가격 기준입니다. 가격대를 고르면 리스·렌트와 가격 미확인 자료는 제외됩니다.', choices:[
  ['전체','',''],['4천만원 미만','',3999.9999],['4천만원대',4000,4999.9999],['5천만원대',5000,5999.9999],['6천만원대',6000,6999.9999],['7천만원 이상',7000,'']
 ]},
 year: {label:'연식',title:'모델연도 선택',note:'최초등록 연월과 모델연도는 다를 수 있습니다. 모델연도 기준으로 비교합니다.',choices:[
  ['전체','',''],['2025년형 이후',2025,''],['2023–2024년형',2023,2024],['2022년형 이전','',2022]
 ]},
 km: {label:'주행거리',title:'주행거리 선택',note:'공개된 주행거리 기준입니다. 범위를 고르면 주행거리 미확인 자료는 제외됩니다.',choices:[
  ['전체','',''],['1만 km 이하','',10000],['3만 km 이하','',30000],['5만 km 이하','',50000],['10만 km 이하','',100000],['10만 km 초과',100001,'']
 ]}
};
let activeRange=null, rangeReturnFocus=null, filterReturnFocus=null;
const extraFilterKeys=['color','region','trim','facelift','sale','cert','history'];
function rangeChoices(key){
 const choices=quickRanges[key].choices;
 if(key!=='year')return choices;
 const years=[...new Set(data.records.map(r=>r.modelYear).filter(Number.isFinite))].sort((a,b)=>b-a);
 return choices.concat(years.map(y=>[y+'년형',y,y]));
}
function selectedRange(key){return rangeChoices(key).find(c=>String(c[1])===String(filters[key+'Min']??'')&&String(c[2])===String(filters[key+'Max']??''));}
function syncFilterControls(){
 for(const key of Object.keys(quickRanges)){
  const choice=selectedRange(key),button=document.querySelector('[data-range="'+key+'"]');
  if(button){button.querySelector('.filter-value').textContent=choice?.[0]||'선택 범위';button.classList.toggle('has-filter',!!filters[key+'Min']||!!filters[key+'Max']);button.setAttribute('aria-label',quickRanges[key].label+' 범위: '+(choice?.[0]||'선택 범위'));}
 }
 document.querySelectorAll('[data-filter]').forEach(el=>{el.value=filters[el.dataset.filter]||'';});
 const count=extraFilterKeys.filter(k=>filters[k]).length;
 $('#more-filter-value').textContent=count?count+'개 선택':'전체';
 $('#more-filters').classList.toggle('has-filter',count>0);
 $('#filter-result-count').textContent=rows().length+'대 보기';
}
function closeOutside(dialog,event){if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}
function setupFilters(){
 const chevron='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>';
 $('#filters').innerHTML='<div class="filter-bar">'+Object.entries(quickRanges).map(([key,v])=>'<button class="filter-trigger" data-range="'+key+'" aria-haspopup="dialog" aria-controls="range-picker"><span class="filter-copy"><span class="filter-label">'+v.label+'</span><span class="filter-value">전체</span></span>'+chevron+'</button>').join('')+'<button id="more-filters" class="filter-trigger" aria-label="색상·지역·세부 조건" aria-haspopup="dialog" aria-controls="filter-dialog"><span class="filter-copy"><span class="filter-label">색상·지역·세부 조건</span><span id="more-filter-value" class="filter-value">전체</span></span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14M7 3v4M13 8v4M8 13v4"/></svg></button></div>';
 $('#extra-filter-fields').innerHTML=select('color','외장 색상')+select('region','판매 지역')+select('trim','트림')+select('facelift','부분변경')+select('sale','판매 방식')+select('cert','인증 종류')+select('history','이력 확인 상태');
 $('#filters').addEventListener('click',e=>{
  const b=e.target.closest('[data-range]');
  if(b){activeRange=b.dataset.range;rangeReturnFocus=b;const config=quickRanges[activeRange];$('#range-picker-title').textContent=config.title;$('#range-picker-note').textContent=config.note;
   $('#range-options').innerHTML=rangeChoices(activeRange).map((c,i)=>'<button class="preset-option" data-range-option="'+i+'" aria-pressed="'+(selectedRange(activeRange)?.[0]===c[0])+'">'+esc(c[0])+'<span aria-hidden="true">✓</span></button>').join('');
   $('#range-picker').showModal();return;
  }
  if(e.target.closest('#more-filters')){filterReturnFocus=$('#more-filters');$('#filter-dialog').showModal();}
 });
 $('#range-options').addEventListener('click',e=>{const b=e.target.closest('[data-range-option]');if(!b)return;const choice=rangeChoices(activeRange)[Number(b.dataset.rangeOption)];if(!choice)return;filters[activeRange+'Min']=choice[1];filters[activeRange+'Max']=choice[2];render();$('#range-picker').close();});
 $('#extra-filter-fields').addEventListener('change',e=>{const key=e.target.dataset.filter;if(extraFilterKeys.includes(key)){filters[key]=e.target.value;render();}});
 $('#reset').addEventListener('click',()=>{filters={};sort='white';render();});
 $('#reset-extra').addEventListener('click',()=>{extraFilterKeys.forEach(k=>delete filters[k]);render();});
 $('#filter-done').addEventListener('click',()=>$('#filter-dialog').close());
 $('#close-filters').addEventListener('click',()=>$('#filter-dialog').close());
 $('#close-range').addEventListener('click',()=>$('#range-picker').close());
 $('#range-picker').addEventListener('close',()=>rangeReturnFocus?.focus());
 $('#filter-dialog').addEventListener('close',()=>filterReturnFocus?.focus());
 for(const id of ['range-picker','filter-dialog'])$('#'+id).addEventListener('click',e=>closeOutside($('#'+id),e));
}
