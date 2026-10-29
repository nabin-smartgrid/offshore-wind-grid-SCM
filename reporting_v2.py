"""WindGrid SCM v0.3: Korean embedded-font, structured scenario reports.

ReportLab uses a TrueType font included in the runtime dependency
`koreanize-matplotlib`; no font files are stored in this repository.
If no Korean TrueType font is available, fail clearly instead of creating a broken PDF.
"""
from __future__ import annotations
import io, os
from pathlib import Path
from html import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                Spacer, Flowable, PageBreak, KeepTogether)
from core import Inputs, Results, screening, overall, template_summary
from scenarios import scm_review, scenario_takeaways, scenario_procurement_changes

NAVY=colors.HexColor('#143451')
BLUE=colors.HexColor('#156EA4')
PALE=colors.HexColor('#EAF2F8')
GRAY=colors.HexColor('#62788B')
BORDER=colors.HexColor('#D8E4EC')


def _font():
    if 'WGKorean' in pdfmetrics.getRegisteredFontNames():
        return 'WGKorean'
    candidates = [os.getenv('KOREAN_FONT_PATH',''),
                  '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                  '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
                  r'C:\Windows\Fonts\malgun.ttf']
    # koreanize-matplotlib supplies NanumGothic on pip-managed cloud environments.
    try:
        import koreanize_matplotlib
        root=Path(koreanize_matplotlib.__file__).resolve().parent
        candidates.extend(str(p) for p in root.rglob('*.ttf') if 'nanum' in p.name.lower())
    except ImportError:
        pass
    for path in candidates:
        if path and Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont('WGKorean',str(path)))
                return 'WGKorean'
            except Exception:
                continue
    raise RuntimeError('한글 PDF 폰트를 찾지 못했습니다. requirements.txt의 koreanize-matplotlib 설치를 확인하세요.')


def _clean(s):
    # Escaping only: preserve Korean punctuation and scientific symbols.
    return escape(str(s)).replace('\n','<br/>')


class BarFigure(Flowable):
    def __init__(self, rows, font):
        super().__init__()
        self.rows=rows
        self.font=font
        self.width=166*mm
        self.height=43*mm
    def draw(self):
        c=self.canv
        data=self.rows
        if not data: return
        high=max((r['충전 무효전력 (Mvar)'] or 0 for r in data),default=1) or 1
        w=(self.width-20)/len(data)
        start=10
        c.setStrokeColor(BORDER)
        c.line(start,17,self.width-10,17)
        for i,z in enumerate(data):
            val=z['충전 무효전력 (Mvar)'] or 0
            h=val/high*(self.height-49)
            xx=start+i*w+w*.17
            c.setFillColor(BLUE if z['기준 시나리오'] else colors.HexColor('#91C6E5'))
            c.roundRect(xx,17,w*.64,max(1,h),2,stroke=0,fill=1)
            c.setFillColor(NAVY)
            c.setFont(self.font,7.5)
            c.drawCentredString(xx+w*.32,21+h,f'{val:,.1f}')
            c.drawCentredString(xx+w*.32,5,f"{z['케이블 길이 (km)']:g} km")


def report_pdf_pretty(x:Inputs,r:Results,docs:list[dict],ai_text:str='',comparison:list[dict]|None=None,model:str='') -> bytes:
    font=_font()
    styles={
        'title':ParagraphStyle('wgtitle',fontName=font,fontSize=16.5,leading=22,textColor=NAVY,spaceAfter=5),
        'subtitle':ParagraphStyle('wgsub',fontName=font,fontSize=8.1,leading=12,textColor=GRAY,spaceAfter=7,wordWrap='CJK'),
        'head':ParagraphStyle('wghead',fontName=font,fontSize=11,leading=15,textColor=BLUE,spaceBefore=8,spaceAfter=5,keepWithNext=True),
        'text':ParagraphStyle('wgtext',fontName=font,fontSize=8.5,leading=13,spaceAfter=4,wordWrap='CJK'),
        'cell':ParagraphStyle('wgcell',fontName=font,fontSize=8,leading=11.8,wordWrap='CJK'),
        'tiny':ParagraphStyle('wgtiny',fontName=font,fontSize=7.3,leading=11,wordWrap='CJK'),
    }
    def P(s,kind='text'): return Paragraph(_clean(s),styles[kind])
    def T(headers, rows, widths, small=False):
        kind='tiny' if small else 'cell'
        data=[[P(v,kind) for v in headers]]+[[P(v,kind) for v in row] for row in rows]
        table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),PALE),
            ('GRID',(0,0),(-1,-1),.4,BORDER),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
            ('TOPPADDING',(0,0),(-1,-1),5 if small else 6),
            ('BOTTOMPADDING',(0,0),(-1,-1),5 if small else 6),
        ]))
        return table
    def section(name): return P(name,'head')
    def fmt(v,unit=''): return '미산출' if v is None else f'{v:,.3f}{(" "+unit) if unit else ""}'
    st=[P('해상풍력 계통연계 및 공급망 영향 분석','title'),
        P(f'프로젝트: {x.project}  |  교육용 정상상태 간이 모델  |  설계·발주 확정에 사용 불가','subtitle')]
    st.append(section('1. 입력 조건'))
    st.append(T(['항목','값','항목','값'],[
        ['정격 / 운전 출력',f'{x.capacity_mw:g} / {x.operating_mw:g} MW','해저케이블',f'{x.length_km:g} km'],
        ['연계전압',f'{x.voltage_kv:g} kV','회선 / 방식',f'{x.circuits}회선 / {x.connection}'],
        ['단락용량',f'{x.short_circuit_mva:g} MVA','주파수 / 역률',f'{x.frequency_hz:g} Hz / {x.power_factor:g}'],
        ['정전용량 / 저항',f'{x.capacitance_uf_km:g} μF/km / {x.resistance_ohm_km:g} Ω/km','목표 COD',x.cod],
    ],[35*mm,50*mm,35*mm,49*mm],small=True))
    st.append(section('2. 계산 결과 · 수업용 예시 판정'))
    st.append(T(['충전 무효전력','부하전류 성분 손실','단순 SCR','종합 검토'],[[
        fmt(r.qc_total_mvar,'Mvar'),
        f'{fmt(r.load_loss_mw,"MW")} / {fmt(r.load_loss_percent,"%")}',
        fmt(r.scr), overall(screening(x,r))
    ]],[43*mm,52*mm,29*mm,45*mm],small=True))
    if comparison:
        st.append(section('3. 케이블 길이별 시나리오 비교'))
        st.append(P('케이블 길이만 변경하며, 나머지 입력 조건은 고정. 충전 무효전력(Qc)은 보상 전 계산값.','tiny'))
        # Keep the bar chart and the full comparison table together whenever possible.
        comp=[BarFigure(comparison,font),Spacer(1,3*mm),
              T(['길이','Qc','저항손실','리액터 검토','SCM 검토 단계'],[
                [f"{z['케이블 길이 (km)']:g} km",f"{z['충전 무효전력 (Mvar)']:.2f} Mvar",
                 f"{z['부하전류 저항손실 (MW)']:.2f} MW",z['리액터 검토'],
                 z.get('SCM 조치','기본 확인')] for z in comparison
              ],[22*mm,42*mm,37*mm,31*mm,37*mm],small=True)]
        st.append(KeepTogether(comp))
        # Page 2 starts with procurement impacts, not a split comparison table.
        st.append(PageBreak())
        st.append(section('4. 시나리오별 공급망·일정 검토'))
        st.append(T(['시나리오','리액터 검토','조달 검토사항 / 일정 영향'],[
            [f"{z['케이블 길이 (km)']:g} km",z['리액터 검토'],z.get('SCM 상세','검토 필요')]
            for z in comparison
        ],[25*mm,31*mm,113*mm],small=True))
        for note in scenario_takeaways(x,comparison): st.append(P('• '+note,'tiny'))
    else:
        st.append(section('3. 기자재·공급망 검토'))
    if comparison: st.append(section('5. 기준 시나리오의 기자재별 조달 체크리스트'))
    st.append(T(['기자재','검토 수준','확인할 설계·구매·일정 사항'],[
        [a['기자재'],a['우선순위'],a['구매확인']] for a in scm_review(x,r)
    ],[43*mm,30*mm,96*mm],small=True))
    st.append(section('6. 분석 해석 및 한계' if comparison else '4. 분석 해석 및 한계'))
    st.append(P(template_summary(x,r)))
    st.append(P('본 결과는 수업용 판정 경계에 따른 우선순위 표시임. 리액터 확정 용량, STATCOM 필요 여부, 전체 손실, 케이블 허용전류, 공급사 가격·납기 및 COD 지연은 산출하지 않음.'))
    if ai_text:
        st.append(section('7. 실제 LLM 분석 초안 · 원문 및 전문가 검증 전'))
        st.append(P(f'실행 모델: {model or "사용자 지정"}. 입력 및 공개 문서 발췌를 외부 API에 전송하여 생성함.'))
        st.append(P(ai_text))
    else:
        st.append(P('AI 분석 상태: 미실행. 위 해석은 규칙 기반 템플릿이며 LLM 응답이 아님.','tiny'))
    st.append(section('근거 문서 (원문 타당성 검증 별도)'))
    for d in docs[:10]:
        st.append(P(f"[{d['id']}] {d['name']} / {d['locator']} / {d['kind']}",'tiny'))
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,
                          topMargin=17*mm,bottomMargin=17*mm,title='WindGrid SCM v0.3 교육용 분석 보고서')
    def footer(c,doc):
        c.saveState();c.setFont(font,7);c.setFillColor(GRAY)
        c.drawString(20*mm,10*mm,'WindGrid SCM v0.3  |  교육용 분석  |  계산은 코드, 해석은 LLM')
        c.drawRightString(A4[0]-20*mm,10*mm,str(doc.page));c.restoreState()
    doc.build(st,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
