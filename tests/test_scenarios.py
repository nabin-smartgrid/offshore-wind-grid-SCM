import unittest,io,sys
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Inputs,calculate
from scenarios import scm_review,compare_scenarios,scenario_takeaways
from reporting_v2 import report_pdf_pretty
from evidence import BUILTIN
from pypdf import PdfReader

class ScenarioTests(unittest.TestCase):
 def test_comparison_baseline_and_length(self):
  x=Inputs();rows=compare_scenarios(x,[30,50,80]);self.assertEqual(len(rows),4)
  self.assertTrue(any(z['기준 시나리오'] and z['케이블 길이 (km)']==65 for z in rows))
  a,b=rows[0],rows[-1]
  self.assertAlmostEqual(b['충전 무효전력 (Mvar)']/a['충전 무효전력 (Mvar)'],80/30,places=3)
  self.assertEqual(a['단순 SCR'],b['단순 SCR'])
 def test_scm_changes_with_scr(self):
  strong=Inputs(short_circuit_mva=2000);weak=Inputs(short_circuit_mva=500)
  self.assertNotEqual(scm_review(strong,calculate(strong))[1]['우선순위'],scm_review(weak,calculate(weak))[1]['우선순위'])
 def test_scm_changes_with_length(self):
  x=Inputs();a=replace(x,length_km=10);b=replace(x,length_km=100)
  self.assertNotEqual(scm_review(a,calculate(a))[0]['우선순위'],scm_review(b,calculate(b))[0]['우선순위'])
 def test_hvdc_no_ac_comparison(self):
  x=replace(Inputs(),connection='VSC-HVDC')
  self.assertEqual(compare_scenarios(x,[30,50]),[])
 def test_pdf_comparison_and_unicode(self):
  x=Inputs();r=calculate(x);rows=compare_scenarios(x,[30,50,80])
  b=report_pdf_pretty(x,r,BUILTIN,comparison=rows)
  reader=PdfReader(io.BytesIO(b));self.assertGreaterEqual(len(reader.pages),2)
  txt='\n'.join(page.extract_text() for page in reader.pages)
  self.assertIn('Shunt Reactor',txt)
  self.assertIn('65 km',txt)
 def test_pdf_base(self):
  x=Inputs();b=report_pdf_pretty(x,calculate(x),BUILTIN)
  self.assertTrue(b.startswith(b'%PDF'))

if __name__=='__main__':unittest.main()

class Version03Tests(unittest.TestCase):
 def test_korean_pdf_extractable_and_chart_table_on_page_one(self):
  x=Inputs(); r=calculate(x)
  rows=compare_scenarios(x,[30,50,80])
  b=report_pdf_pretty(x,r,BUILTIN,comparison=rows)
  reader=PdfReader(io.BytesIO(b))
  self.assertIn('해상풍력 계통연계',reader.pages[0].extract_text())
  self.assertIn('시나리오 비교',reader.pages[0].extract_text())
  self.assertIn('80 km',reader.pages[0].extract_text())
  self.assertIn('SCM',reader.pages[0].extract_text())
  self.assertIn('시나리오별 공급망',reader.pages[1].extract_text())
 def test_scm_details_change_with_length(self):
  x=Inputs(); a,b=compare_scenarios(x,[10,150])[0],compare_scenarios(x,[10,150])[-1]
  self.assertNotEqual(a['SCM 조치'],b['SCM 조치'])
  self.assertIn('발주 일정 영향',b['SCM 상세'])
 def test_no_llm_claim_when_not_run(self):
  x=Inputs();reader=PdfReader(io.BytesIO(report_pdf_pretty(x,calculate(x),BUILTIN)))
  self.assertIn('AI 분석 상태: 미실행','\n'.join(p.extract_text() for p in reader.pages))
