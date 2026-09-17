import unittest
from collector.robots import RobotsPolicy
from collector.encar_browser import listing_items,merge_listing,merge_search_history

class RobotsTests(unittest.TestCase):
    def policy(self,text):
        p=RobotsPolicy();p.parse(text.splitlines());return p
    def test_longest_rule_overrides_early_allow(self):
        p=self.policy('User-agent: *\nAllow: /\nDisallow: /cars/detail/\n')
        self.assertFalse(p.can_fetch('BMW420iPriceWatch/1.0','https://fem.encar.com/cars/detail/42477383'))
        self.assertTrue(p.can_fetch('BMW420iPriceWatch/1.0','https://www.encar.com/fc/fc_carsearchlist.do'))
    def test_equal_specificity_allow_and_agent_groups(self):
        p=self.policy('User-agent: *\nDisallow: /private\nAllow: /private/open\nUser-agent: GPTBot\nDisallow: /\n')
        self.assertTrue(p.can_fetch('BMW420iPriceWatch/1.0','https://example.com/private/open'))
        self.assertFalse(p.can_fetch('GPTBot','https://example.com/private/open'))
    def test_wildcard_and_query_end(self):
        p=self.policy('User-agent: *\nDisallow: /search?*private=1$\n')
        self.assertFalse(p.can_fetch('observer','https://example.com/search?q=a&private=1'))
        self.assertTrue(p.can_fetch('observer','https://example.com/search?q=a&private=10'))

class SearchListingTests(unittest.TestCase):
    def html(self,grade='420i M 스포츠 컨버터블',price='4,600만원',year='23/02식'):
        return '<ul><li><a class="newLink _link" href="/dc/dc_cardetailview.do?carid=42477383"><span class="cls">BMW 4시리즈 (G22)</span><span class="dtl">'+grade+'</span><span class="yer">'+year+'</span><span class="km">57,011km</span><span class="lo">· 경남</span><span class="prc">'+price+'</span></a></li></ul>'
    def test_actual_target_and_no_registration_year_inference(self):
        r=listing_items(self.html(),'https://www.encar.com/search','2026-09-18')[0]
        self.assertEqual(r['listingPrice'],46000000)
        self.assertEqual(r['registration'],'2023-02')
        self.assertIsNone(r['modelYear'])
        self.assertIsNone(r['color'])
        self.assertEqual(r['mileage'],57011)
        self.assertEqual(r['url'],'https://fem.encar.com/cars/detail/42477383')
    def test_excludes_coupe_diesel_and_other_engines(self):
        for grade in ['420i M 스포츠 쿠페','420i 그란쿠페','420d 컨버터블','430i 컨버터블']:
            self.assertEqual(listing_items(self.html(grade),'https://www.encar.com/search','t'),[])
    def test_monthly_is_never_full_price(self):
        r=listing_items(self.html(price='월110만원/42개월 리스'),'https://www.encar.com/search','t')[0]
        self.assertIsNone(r['listingPrice'])
        self.assertEqual(r['monthlyPayment'],1100000)
    def test_standard_row_currency_outside_price_element(self):
        html='<table><tr><td><a class="newLink _link" href="/dc/dc_cardetailview.do?carid=42477383"><span class="cls">BMW 4시리즈 (G22)</span><span class="dtl">420i M 스포츠 컨버터블</span></a></td><td class="prc_hs"><strong class="prc">4,400</strong>만원</td></tr></table>'
        self.assertEqual(listing_items(html,'https://www.encar.com/search','t')[0]['listingPrice'],44000000)
    def test_missing_duplicate_price_does_not_signal_price_change(self):
        r=listing_items(self.html(),'https://www.encar.com/search','t')[0]
        missing={**r,'listingPrice':None}
        merged=merge_listing(r,missing)
        self.assertEqual(merged['listingPrice'],46000000)
        self.assertFalse(merged['priceConflict'])
    def test_conflicting_duplicate_prices_preserve_both(self):
        r=listing_items(self.html(),'https://www.encar.com/search','t')[0]
        merged=merge_listing(r,{**r,'listingPrice':45000000})
        self.assertTrue(merged['priceConflict'])
        self.assertEqual(len(merged['listingOffers']),2)
    def test_failed_search_preserves_price_time_and_history(self):
        r=listing_items(self.html(),'https://www.encar.com/search','2026-09-17T00:00:00Z')[0]
        merged,events=merge_search_history([r],[],{'checkedAt':'2026-09-18T00:00:00Z','browserSearch':{'complete':False}})
        self.assertEqual(merged[0]['checkedAt'],r['checkedAt'])
        self.assertEqual(merged[0]['listingPrice'],r['listingPrice'])
        self.assertTrue(merged[0]['stale'])
        self.assertEqual(events,[])
    def test_actual_list_change_keeps_both_observations(self):
        r=listing_items(self.html(),'https://www.encar.com/search','2026-09-17T00:00:00Z')[0]
        new={**r,'listingPrice':45000000,'checkedAt':'2026-09-18T00:00:00Z'}
        merged,events=merge_search_history([r],[new],{'checkedAt':new['checkedAt']})
        self.assertEqual(merged[0]['firstSeen'],r['checkedAt'])
        self.assertEqual([x['listingPrice'] for x in merged[0]['listingObservations']],[46000000,45000000])
        self.assertEqual(events[0]['type'],'목록 가격 변경')
        self.assertFalse(merged[0]['stale'])
