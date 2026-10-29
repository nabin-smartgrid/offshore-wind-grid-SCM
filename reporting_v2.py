"""Readable Korean PDF reports; font is provided by server, never bundled."""
from __future__ import annotations
import io,os
from pathlib import Path
from html import escape
from dataclasses import asdict
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,Flowable
from core import Inputs, Results, screening, overall, template_summary
from scenarios import scm_review,scenario_takeaways

NAVY=colors.HexColor('#153450');BLUE=colors.HexColor('#1767A5');PALE=colors.HexColor('#EAF2F9')

def _font():
    for file in [os.getenv('KOREAN_FONT_PATH',''),r'C:\Windows\Fonts\malgun.ttf','/usr/share/fonts/truetype/nanum/NanumGothic.ttf']:
        if file and Path(file).is_file():
            try:
                if 'WGKorean' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('WGKorean',file))
                return 'WGKorean'
            except Exception:pass
    if 'HYSMyeongJo-Medium' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
    return 'HYSMyeongJo-Medium'

def _clean(s):
    return escape(str(s)).replace('·',' / ').replace('→',' -> ').replace('μ','u').replace('≤','&lt;=').replace('≥','&gt;=')

class BarFigure(Flowable):
    def __init__(self,rows,font):
        Flowable.__init__(self);self.rows=rows;self.font=font;self.width=165*mm;self.height=46*mm
    def draw(self):
        c=self.canv;data=self.rows;high=max((z['충전 무효전력 (Mvar)'] for z in data),default=1) or 1
        n=len(data);w=(self.width-22)/n;start=10
        c.setStrokeColor(colors.HexColor('#BCCBDA'));c.line(start,18,self.width-10,18)
        for i,z in enumerate(data):
            val=z['충전 무효전력 (Mvar)'];h=val/high*(self.height-46)
            xx=start+i*w+w*.18
            c.setFillColor(BLUE if z['기준 시나리오'] else colors.HexColor('#93C3E4'))
            c.rect(xx,18,w*.62,h,stroke=0,fill=1)
            c.setFont(self.font,7.5);c.setFillColor(NAVY)
            c.drawCentredString(xx+w*.31,20+h,f'{val:.1f}')
            c.drawCentredString(xx+w*.31,5,f"{z['케이블 길이 (km)']:g} km")

def report_pdf_pretty(x:Inputs,r:Results,docs:list[dict],ai_text:str='',comparison:list[dict]|None=None,model:str='') -> bytes:
    font=_font()
    style={
      'title':ParagraphStyle('title',fontName=font,fontSize=17,leading=24,textColor=NAVY,spaceAfter=10),
      'subtitle':ParagraphStyle('subtitle',fontName=font,fontSize=9,leading=15,textColor=colors.HexColor('#64748B'),spaceAfter=10),
      'head':ParagraphStyle('head',fontName=font,fontSize=12,leading=18,textColor=BLUE,spaceBefore=12,spaceAfter=6,keepWithNext=True),
      'text':ParagraphStyle('text',fontName=font,fontSize=9.2,leading=15,spaceAfter=6,wordWrap='CJK'),
      'cell':ParagraphStyle('cell',fontName=font,fontSize=8.4,leading=12,wordWrap='CJK'),
    }
    def P(s,kind='text'):return Paragraph(_clean(s),style[kind])
    def T(headers,rows,widths):
        values=[[P(v,'cell') for v in headers]]+[[P(v,'cell') for v in row] for row in rows]
        table=Table(values,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#DAE4ED')),
           ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
           ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        return table
    st=[P('해상풍력 계통연계 및 공급망 영향 분석','title'),P(f'프로젝트: {x.project} / 교육용 정상상태 간이 모델 / 설계 및 발주 확정에 사용 불가','subtitle')]
    st.append(P('1. 입력 조건','head'))
    st.append(T(['항목','값'],[
      ['정격용량 / 운전출력',f'{x.capacity_mw:g} MW / {x.operating_mw:g} MW'],
      ['해저케이블 / 전압 / 회선',f'{x.length_km:g} km / {x.voltage_kv:g} kV / {x.circuits}회선'],
      ['연계방식 / 단락용량',f'{x.connection} / {x.short_circuit_mva:g} MVA'],
      ['정전용량 / 저항 (상별 가정)',f'{x.capacitance_uf_km:g} uF/km / {x.resistance_ohm_km:g} ohm/km'],
      ['주파수 / 역률 / COD',f'{x.frequency_hz:g} Hz / {x.power_factor:g} / {x.cod}']], [72*mm,97*mm]))
    st.append(P('2. 계산 결과 및 예시 판정','head'))
    def fmt(v,unit=''):return '미산출' if v is None else f'{v:,.3f} {unit}'
    st.append(T(['항목','계산값'],[
      ['충전 무효전력 합계',fmt(r.qc_total_mvar,'Mvar')],['회선당 부하전류',fmt(r.current_per_circuit_a,'A')],
      ['부하전류 성분 저항손실',fmt(r.load_loss_mw,'MW')+' / '+fmt(r.load_loss_percent,'%')],
      ['단순 SCR',fmt(r.scr)],['종합 검토 수준 (수업용)',overall(screening(x,r))]],[85*mm,84*mm]))
    if comparison:
        st.append(P('3. 케이블 길이만 변경한 시나리오 비교','head'))
        st.append(P('다른 입력값은 모두 고정하고 케이블 길이만 변경. 아래 Qc는 보상 전 충전 무효전력임.'))
        st.append(BarFigure(comparison,font))
        st.append(T(['길이','Qc','손실 (부하전류)','리액터 검토'],[
          [f"{z['케이블 길이 (km)']:g} km",f"{z['충전 무효전력 (Mvar)']:.2f} Mvar",f"{z['부하전류 저항손실 (MW)']:.2f} MW",z['리액터 검토']] for z in comparison],
          [26*mm,44*mm,55*mm,44*mm]))
        for note in scenario_takeaways(x,comparison):st.append(P('- '+note))
    st.append(P('4. 기자재 / 공급망 검토 체크리스트','head'))
    st.append(T(['기자재','우선순위 (가정)','구매 확인사항'],[
      [a['기자재'],a['우선순위'],a['구매확인']] for a in scm_review(x,r)], [43*mm,35*mm,91*mm]))
    st.append(P('5. 해석과 한계','head'))
    st.append(P(template_summary(x,r)))
    st.append(P('수치 판정의 경계값은 수업용 가정이며, 공인 계통기준이 아님. 리액터 발주 용량, STATCOM 필요 여부, 전체 손실, 케이블 허용전류, 실제 납기/가격/COD 영향은 이 모델로 결정하지 않음.'))
    if ai_text:
        st.append(P('6. LLM 해석 초안 (원문 검증 및 전문가 검토 전)','head'))
        st.append(P(f'AI 모델: {model or "사용자 지정"} / 입력값과 문서 발췌를 전송해 생성한 결과'))
        st.append(P(ai_text))
    st.append(P('근거 문서','head'))
    for d in docs[:10]:st.append(P(f"[{d['id']}] {d['name']} / {d['locator']} / {d['kind']}"))
    out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=18*mm,bottomMargin=18*mm,
        title='WindGrid SCM 교육용 분석 보고서')
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,7.5);canvas.setFillColor(colors.HexColor('#6B7C90'))
        canvas.drawString(20*mm,10*mm,'WindGrid SCM / 교육용 분석 / 계산은 코드, 해석은 LLM')
        canvas.drawRightString(A4[0]-20*mm,10*mm,str(doc.page));canvas.restoreState()
    doc.build(st,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
