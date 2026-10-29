import unittest
from evidence import check_ai_numbers, citation_check

class GeminiGuardTests(unittest.TestCase):
    def setUp(self):
        self.payload={'results':{'qc_total_mvar':232.459,'qc_per_circuit_mvar':116.229,'scr':2.8,'load_loss_mw':10.278},'inputs':{'capacity_mw':500.0,'operating_mw':500.0},'comparison':[{'충전 무효전력 (Mvar)':107.29,'부하전류 저항손실 (MW)':4.74}]}
        self.docs=[{'id':'PLAN-2'}]
    def test_matching(self):
        self.assertEqual([],check_ai_numbers('Qc 232.46 Mvar, SCR 2.80 [PLAN-2]',self.payload))
    def test_wrong_q(self):
        self.assertTrue(check_ai_numbers('Qc 999 Mvar [PLAN-2]',self.payload))
    def test_matching_mw(self):
        self.assertEqual([],check_ai_numbers('500 MW, 10.28 MW, 4.74 MW',self.payload))
    def test_wrong_mw(self):
        self.assertTrue(check_ai_numbers('손실 90 MW',self.payload))
    def test_wrong_scr(self):
        self.assertTrue(check_ai_numbers('SCR 1.0 [PLAN-2]',self.payload))
    def test_comparison(self):
        self.assertEqual([],check_ai_numbers('107.29 Mvar',self.payload))
    def test_citations(self):
        self.assertEqual((['PLAN-2'],['PLAN-999']),citation_check('[PLAN-2] [PLAN-999]',self.docs))

if __name__=='__main__':unittest.main()
