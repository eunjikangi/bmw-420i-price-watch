import unittest
from collector.parsers import parse,parse_danawa_new
from bs4 import BeautifulSoup
from collector.model import key,canonical
from collector.encar_browser import merge_search_history

class BrowserSourceTests(unittest.TestCase):
 def test_inspection_link_does_not_republish_encoded_plate(self):
  html='<h1 class="car-buy-name">BMW 420i Convertible M Sport</h1><a id="btnCarCheck1" data-link-url="https://example.test/?car_no=123%EA%B0%804567">성능</a>'
  r=parse(html,{'id':'kb','name':'KB','parser':'kb'},'https://www.kbchachacha.com/public/car/detail.kbc?carSeq=123')
  self.assertNotIn('inspectionUrl',r);self.assertTrue(any('식별정보' in w for w in r['warnings']))
 def test_mpark_missing_color_and_lien_preserved(self):
  html='<title>BMW 420i 컨버터블 M 스포츠팩</title><p>판매가격 3,390만원 연식 22년09월(23년형) 144,088km 색상 압류 0회 저당 1회 81가지 차량 점검 완료! 교환 0회 성능점검기록부 보기 점검일 : 2026년 06월 08일 내차피해 0회 (0원) 타차피해 0회 (0원) 보험처리이력 보기</p>'
  r=parse(html,{'id':'mpark','name':'엠파크','parser':'mpark'},'https://www.m-park.co.kr/buy/detail/123')
  self.assertIsNone(r['color']);self.assertEqual(r['modelYear'],2023);self.assertEqual(r['registration'],'2022-09');self.assertEqual(r['price'],33900000)
  self.assertEqual(r['insuranceCount'],0);self.assertIsNone(r['roof']);self.assertTrue(any('저당 1회' in w for w in r['warnings']))
 def test_danawa_price_period_is_not_current_promotion_and_trims_stay_distinct(self):
  html='<dt class="price_title">2026년형 컨버터블 가솔린 2.0 (2026.07.01)</dt><dd><ul><li><input value="P1"><label>420i Convertible M Sport Pro (P1)</label><div class="item price">8,030만원</div></li><li><input value="P2"><label>420i Convertible M Sport Pro (P2)</label><div class="item price">8,140만원</div></li><li><input value="other"><label>430i Convertible</label><div class="item price">8,000만원</div></li></ul></dd><dt class="price_title">2026년형 쿠페 가솔린 2.0 (2026.07.01)</dt><dd><li><input value="coupe"><label>420i M Sport</label><div class="item price">7,000만원</div></li></dd>'
  rs=parse_danawa_new(BeautifulSoup(html,'html.parser'),'https://auto.danawa.com/auto/','2026-09-18T01:00:00+00:00')
  self.assertEqual(len(rs),2);self.assertEqual([r['price'] for r in rs],[80300000,81400000]);self.assertNotEqual(rs[0]['trim'],rs[1]['trim'])
  self.assertEqual(rs[0]['pricePeriodKind'],'가격표 적용 시작');self.assertEqual(rs[0]['validFrom'],'2026-07-01');self.assertEqual(rs[0]['stock'],'흰색 재고 미확인')
 def test_distinct_partner_ids_and_tracking_canonicalization(self):
  self.assertEqual(key('kolon','https://702prime.com/used-car/used-car-product-detail?id=21441'),'kolon:21441')
  self.assertNotEqual(key('kcar','https://www.kcar.com/br/detail/brandCarInfoDtl?i_sCarCd=A'),key('kcar','https://www.kcar.com/br/detail/brandCarInfoDtl?i_sCarCd=B'))
  self.assertEqual(canonical('https://charancha.com/cars/a?viewType=RECOMMEND'),'https://charancha.com/cars/a')
 def test_kcar_lease_price_stays_separate_and_no_model_year_inference(self):
  html='<h2 class="carName">BMW 420i 컨버터블 M 스포츠</h2><p>26년 3월식 6,267km 가솔린 검정색 오토 브랜드인증 서울서초 6,200만원 리스차량 차량 예상 가격 선수금 30%</p>'
  r=parse(html,{'id':'kcar','name':'케이카','parser':'kcar'},'https://www.kcar.com/br/detail/brandCarInfoDtl?i_sCarCd=A')
  self.assertEqual(r['price'],62000000);self.assertIn('리스',r['priceKind']);self.assertIsNone(r['modelYear']);self.assertEqual(r['registration'],'2026-03');self.assertFalse(r['cashConfirmed'])
 def test_kolon_insurance_spaces_and_cost_estimate_not_vehicle_price(self):
  html='<article class="title-lg">BMW 4시리즈 컨버터블 420i_M 스포츠</article><p>2023년형 56,949km 가솔린 경남 외관컬러 흰색 최초등록 2023.02.17 내차피해 4 회 ( 4,121,611 원) 타차피해 0 회 ( 0 원) 소유자 변경 0 회 판매자 정보 BPS_양산 차량 가격 46,000,000원 이전 등록 관련 부가비용 3,225,000원</p>'
  r=parse(html,{'id':'kolon','name':'코오롱','parser':'kolon'},'https://702prime.com/used-car/used-car-product-detail?id=21441')
  self.assertEqual(r['price'],46000000);self.assertEqual(r['insuranceCount'],4);self.assertEqual(r['insuranceAmount'],4121611);self.assertIsNone(r['extraCosts']);self.assertFalse(r['extraCostEstimate']['confirmed'])
 def test_other_source_failure_keeps_last_observation(self):
  old={'sourceId':'charancha','source':'차란차','listingId':'uuid','url':'https://charancha.com/cars/uuid','evidence':'헤드리스 검색 목록 확인','checkedAt':'2026-09-17T01:00:00+00:00','listingPrice':40000000}
  result,events=merge_search_history([old],[],{'id':'charancha','name':'차란차','checkedAt':'2026-09-18T01:00:00+00:00'})
  self.assertEqual(result[0]['checkedAt'],old['checkedAt']);self.assertEqual(result[0]['listingPrice'],40000000);self.assertTrue(result[0]['stale']);self.assertEqual(events,[])
if __name__=='__main__':unittest.main()
