import unittest, sys, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
from core import Inputs,calculate,screening,overall,equipment,state_digest,compare_lengths
from evidence import extract_document,retrieve,BUILTIN,citation_check
from reporting import report_markdown,report_html,report_pdf

class ModelTests(unittest.TestCase):
    def test_report_reference_example(self):
        r=calculate(replace(Inputs(),length_km=30,circuits=1))
        self.assertAlmostEqual(r.qc_total_mvar,53.644328188225586,places=8)
    def test_two_circuits(self):
        x=Inputs();r=calculate(x);s=calculate(replace(x,circuits=1))
        self.assertAlmostEqual(r.qc_total_mvar,2*s.qc_total_mvar)
        self.assertAlmostEqual(r.current_per_circuit_a,.5*s.current_per_circuit_a)
        self.assertAlmostEqual(r.load_loss_mw,.5*s.load_loss_mw)
    def test_length_scaling(self):
        x=Inputs();a=calculate(x);b=calculate(replace(x,length_km=x.length_km*2))
        self.assertAlmostEqual(b.qc_total_mvar,2*a.qc_total_mvar)
        self.assertAlmostEqual(b.load_loss_mw,2*a.load_loss_mw)
    def test_voltage_scaling(self):
        x=Inputs();a=calculate(x);b=calculate(replace(x,voltage_kv=308))
        self.assertAlmostEqual(b.qc_total_mvar,4*a.qc_total_mvar)
        self.assertAlmostEqual(b.load_loss_mw,.25*a.load_loss_mw)
    def test_power_factor(self):
        x=Inputs();a=calculate(x);b=calculate(replace(x,power_factor=.8))
        self.assertAlmostEqual(b.load_loss_mw,a.load_loss_mw/.8**2)
    def test_idle_not_deenergized(self):
        x=replace(Inputs(),operating_mw=0);r=calculate(x)
        self.assertEqual(r.load_loss_mw,0);self.assertIsNone(r.load_loss_percent)
        self.assertGreater(r.qc_total_mvar,0)
        self.assertEqual(screening(x,r)[1]['검토 수준'],'판정 보류')
    def test_hvdc_never_fake_zero(self):
        x=replace(Inputs(),connection='VSC-HVDC');r=calculate(x)
        self.assertIsNone(r.qc_total_mvar);self.assertIsNone(r.load_loss_mw)
        self.assertEqual(overall(screening(x,r)),'판정 보류')
    def test_zero_length(self):
        r=calculate(replace(Inputs(),length_km=0));self.assertEqual(r.qc_total_mvar,0);self.assertEqual(r.load_loss_mw,0)
    def test_scr(self):self.assertAlmostEqual(calculate(Inputs()).scr,2.8)
    def test_invalid(self):
        for kw in [{'capacity_mw':0},{'operating_mw':600},{'power_factor':0},{'power_factor':1.01},{'circuits':1.5},{'circuits':True},{'length_km':-1},{'short_circuit_mva':float('nan')},{'voltage_kv':float('inf')},{'cod':'2033-13'}]:
            with self.subTest(kw=kw),self.assertRaises(ValueError): calculate(replace(Inputs(),**kw))
    def test_deterministic(self):
        self.assertEqual(calculate(Inputs()),calculate(Inputs()))
        self.assertEqual(state_digest(Inputs(),BUILTIN),state_digest(Inputs(),BUILTIN))
        self.assertNotEqual(state_digest(Inputs(),BUILTIN),state_digest(replace(Inputs(),length_km=30),BUILTIN))
    def test_demo_rules_off(self):
        x=replace(Inputs(),demo_rules=False);self.assertEqual(overall(screening(x,calculate(x))),'판정 보류')
    def test_length_comparison(self):
        rows=compare_lengths(Inputs());self.assertEqual(len(rows),4)
        ratios=[z['충전 무효전력 (Mvar)']/z['길이 (km)'] for z in rows]
        self.assertAlmostEqual(max(ratios),min(ratios))

class EvidenceTests(unittest.TestCase):
    def test_utf8_and_cp949(self):
        for encoding in ['utf-8','cp949']:
            chunks=extract_document('sample.txt','무효전력 리액터 검토'.encode(encoding))
            self.assertEqual(len(chunks),1);self.assertIn('무효전력',chunks[0]['text'])
    def test_no_match(self):self.assertEqual(retrieve(BUILTIN,'ZZQNORESULT'),[])
    def test_matching(self):self.assertIn('PLAN-2',[d['id'] for d in retrieve(BUILTIN,'리액터')])
    def test_citation_ids(self):
        valid,invalid=citation_check('예시 [PLAN-2] [DOC-bogus-1]',BUILTIN)
        self.assertEqual(valid,['PLAN-2']);self.assertEqual(invalid,['DOC-bogus-1'])
    def test_invalid_ext(self):
        with self.assertRaises(ValueError):extract_document('x.exe',b'data')
    def test_filename_escaping(self):
        x=replace(Inputs(),project='<script>alert(1)</script>')
        h=report_html(report_markdown(x,calculate(x),BUILTIN))
        self.assertNotIn('<script>',h)
    def test_pdf(self):
        b=report_pdf(report_markdown(Inputs(),calculate(Inputs()),BUILTIN))
        self.assertTrue(b.startswith(b'%PDF'))
        import io
        from pypdf import PdfReader
        self.assertGreaterEqual(len(PdfReader(io.BytesIO(b)).pages),1)

if __name__=='__main__':unittest.main(verbosity=2)
