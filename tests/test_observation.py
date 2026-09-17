import unittest
from collector.model import *
from collector.parsers import parse

class ObservationTests(unittest.TestCase):
 def test_model_exclusions(self):
  for name in ['420i 쿠페','420i 그란쿠페','420d 컨버터블','430i 컨버터블','M440i 컨버터블','4시리즈 G22','420i Gran Coupe Convertible']:
   self.assertFalse(is_target(name),name)
  for name in ['BMW G22 420i Convertible M Spt LCI','420i 컨버터블 M 스포츠 프로','420i 컨버']:self.assertTrue(is_target(name),name)
 def test_white_aliases(self):
  for c in ['흰색','백색','알파인 화이트','미네랄 화이트','Alpine White']:self.assertTrue(white(c))
  self.assertFalse(white(None));self.assertFalse(white('블랙 사파이어'))
 def record(self):
  r=base({'id':'a','name':'A'},'https://example.com/detail?no=1','420i 컨버터블');r['price']=50000000;return r
 def test_failure_preserves_last_price_and_timestamp(self):
  r=merge_record(None,self.record(),'2026-09-17T00:00:00Z');f=merge_record(r,None,'2026-09-18T00:00:00Z',False,'접근불가')
  self.assertEqual(f['price'],50000000);self.assertEqual(f['lastSuccess'],r['lastSuccess']);self.assertEqual(f['firstSeen'],r['firstSeen']);self.assertTrue(f['stale']);self.assertIsNone(f['observations'][-1]['price']);self.assertNotEqual(f['status'],'판매완료')
 def test_no_fabricated_history_or_duplicate_run(self):
  r=merge_record(None,self.record(),'2026-09-17T00:00:00Z');self.assertEqual(len(r['observations']),1)
  r=merge_record(r,self.record(),'2026-09-17T00:00:00Z');self.assertEqual(len(r['observations']),1)
 def test_lease_requires_all_costs(self):
  self.assertIsNone(lease_total({'initial':0,'remainingPayments':45000000,'buyout':24000000}))
  self.assertEqual(lease_total({'initial':100,'remainingPayments':200,'buyout':300,'depositReturn':50,'transferCosts':0}),550)
 def test_strong_identity_groups_and_keeps_prices(self):
  a=self.record();b=self.record();b['id']='b:2';b['sourceId']='b';b['price']=49000000
  self.assertEqual(len(group_records([a,b])),2)
  a['identityKey']=b['identityKey']=identity('123가4567');g=group_records([a,b]);self.assertEqual(len(g),1);self.assertEqual(len(g[0]['offers']),2)
 def test_possible_duplicate_stays_separate(self):
  a=self.record();b=self.record();b['id']='b:2';b['sourceId']='b'
  for r in [a,b]:r.update(registration='2024-08',mileage=10000,color='흰색')
  gs=group_records([a,b]);self.assertEqual(len(gs),2);self.assertTrue(all(g['duplicateStatus']=='중복 추정' for g in gs))
 def test_bad_title_on_detail_not_promoted(self):
  html='<h3 class="tit">BMW 430i 컨버터블</h3><span class="price">3,000만원</span><p>비슷한 차량: 420i 컨버터블</p>'
  self.assertIsNone(parse(html,{'id':'boba','name':'보배','parser':'boba'},'https://example.com/?no=1'))
 def test_finance_and_cash_conflict(self):
  html='<h3 class="tit">BMW 420i 컨버터블</h3><span class="price">6,000만원</span><div class="d-head"><h4>차량설명</h4></div><div>할부 승계 일반 판매 (수리전): 6150 일반 판매 (수리후): 6250</div>'
  r=parse(html,{'id':'boba','name':'보배','parser':'boba'},'https://example.com/?no=1')
  self.assertTrue(r['priceConflict']);self.assertFalse(r['cashConfirmed']);self.assertEqual(r['price'],60000000)
 def test_missing_insurance_not_zero(self):
  r=parse('<h3 class="tit">BMW 420i 컨버터블</h3><span class="price">5,000만원</span>',{'id':'boba','name':'보배','parser':'boba'},'https://example.com/?no=1');self.assertIsNone(r['insuranceCount']);self.assertIsNone(r['roof'])
 def test_registration_is_not_post_date(self):
  r=parse('<h3 class="tit">420i 컨버터블</h3><span class="price">5000만원</span><p>최초등록 26/06/29</p><table><tr><th>연식</th><td>2025.09</td></tr></table>',{'id':'boba','name':'보배','parser':'boba'},'https://example.com/?no=1')
  self.assertEqual(r['registration'],'2025-09');self.assertIsNone(r['modelYear'])
if __name__=='__main__':unittest.main()

class PublishedStateTests(unittest.TestCase):
 def test_sold_badge_is_distinct_from_seller_count(self):
  src={'id':'boba','name':'보배','parser':'boba'}
  h='<h3 class="tit">420i 컨버터블</h3><div class="price-area"><span class="price">[판매완료]</span></div><p>판매중 99</p>'
  self.assertEqual(parse(h,src,'https://example.com/?no=3')['status'],'판매완료')
  h='<h3 class="tit">420i 컨버터블</h3><div class="price-area"><span class="price">5000만원</span></div><p>판매완료 100</p>'
  self.assertEqual(parse(h,src,'https://example.com/?no=3')['status'],'광고 게시 중')
 def test_getcha_month_comes_from_article_not_search_snippet(self):
  from collector.parsers import parse_getcha_new
  from bs4 import BeautifulSoup
  h='<h1>2026년 8월 420i 컨버터블 M 스포츠 프로</h1><table><tr><td>실구매가</td><td>75,000,000원</td></tr><tr><td>월 납입금</td><td>410,356원</td></tr></table>'
  rs=parse_getcha_new(BeautifulSoup(h,'html.parser'),'https://web.getcha.kr/test','2026-09-18')
  self.assertEqual(len(rs),1);self.assertEqual(rs[0]['effectiveMonth'],'2026-08');self.assertEqual(rs[0]['price'],75000000)

class EncarTests(unittest.TestCase):
 def test_public_json_price_unit_and_financing(self):
  import json
  d={'cars':{'base':{'category':{'manufacturerName':'BMW','modelName':'4시리즈(G22)','gradeName':'420i M 스포츠 컨버터블','yearMonth':'202509','formYear':'2025'},'advertisement':{'price':5876,'status':'ADVERTISE','advertisementType':'FINANCING_LEASE','leaseRentInfo':{'monthlyFee':12}},'spec':{'mileage':8900,'colorName':'흰색'},'contact':{},'vehicleNo':None}}}
  h='<script>__PRELOADED_STATE__ = '+json.dumps(d)+'</script>'
  r=parse(h,{'id':'encar','name':'엔카','parser':'encar'},'https://fem.encar.com/cars/detail/123')
  self.assertEqual(r['price'],58760000);self.assertEqual(r['saleMethod'],'금융리스');self.assertIsNone(lease_total(r['lease']));self.assertEqual(r['registration'],'2025-09')
 def test_script_is_never_evaluated(self):
  self.assertIsNone(parse('<script>__PRELOADED_STATE__ = {bad}; alert(1)</script>',{'id':'encar','name':'엔카','parser':'encar'},'https://fem.encar.com/cars/detail/123'))
