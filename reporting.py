"""Downloadable reports. Font files are never redistributed with this project."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
import io, json, os
from core import Inputs, Results, screening, overall, equipment, template_summary, DEMO_RULES

def report_markdown(x: Inputs, r: Results, snippets: list[dict], ai_text: str='') -> str:
    def fmt(v, unit=''):
        return '미산출/미정의' if v is None else f'{v:,.3f} {unit}'.strip()
    lines=['# 해상풍력 계통연계 · 공급망 영향 분석',f'프로젝트: {x.project}',
           '교육용 프로토타입 / 실제 설계·발주·계통 적합성 판단에 사용하지 않음',
           f'작성: {datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")}',
           '## 1. 프로젝트 입력 및 가정']
    names={'capacity_mw':'단지 정격용량 (MW)','operating_mw':'운전 유효전력 (MW)','length_km':'케이블 길이 (km)',
           'voltage_kv':'선간 RMS 전압 (kV)','connection':'연계 방식','short_circuit_mva':'단락용량 (MVA)',
           'cod':'목표 COD','capacitance_uf_km':'상별 정전용량 (uF/km, 가정)',
           'resistance_ohm_km':'상별 저항 (ohm/km, 가정)','frequency_hz':'주파수 (Hz)',
           'power_factor':'역률','circuits':'동일 병렬 회선 수 (가정)','demo_rules':'수업용 예시 판정규칙 적용'}
    for k,v in asdict(x).items():
        if k!='project': lines.append(f'- {names[k]}: {v}')
    lines+=['## 2. 코드 계산 결과',f'- 충전 무효전력 합계: {fmt(r.qc_total_mvar,"Mvar")}',
            f'- 회선당 충전 무효전력: {fmt(r.qc_per_circuit_mvar,"Mvar")}',
            f'- 회선당 부하전류: {fmt(r.current_per_circuit_a,"A")}',
            f'- 부하전류 성분 저항손실: {fmt(r.load_loss_mw,"MW")} / {fmt(r.load_loss_percent,"%")}',
            f'- 단순 SCR: {r.scr:.3f}',
            'Qc는 상별 정전용량과 선간 RMS 전압을 사용하는 3상 식이다. 회선 수만큼 합산한다.',
            '## 3. 예시 규칙에 따른 검토 수준', '공인 기준·제조사 보증치가 아닌 수업용 경계값이다.']
    for row in screening(x,r):
        lines.append(f'- {row["항목"]}: {row["검토 수준"]} / {row["근거"]}')
    lines+=['## 4. 기자재·공급망 검토 후보']
    for row in equipment(x,r):
        lines.append(f'- {row["기자재"]}: {row["검토사항"]}. {row["공급망영향"]}. 근거: {row["근거"]}.')
    lines+=['## 5. 자동 요약 (규칙 기반, LLM 미사용)',template_summary(x,r)]
    if ai_text: lines+=['## 6. LLM 해석 초안 (전문가 검증 전)', ai_text]
    lines+=['## 근거·한계']+['- '+n for n in r.notes]
    lines+=['## 등록 근거 문서', '문서 등록은 출처·최신성 또는 인용 타당성 검증을 의미하지 않는다.']
    for c in snippets:
        lines.append(f'- [{c["id"]}] {c["name"]} / {c["locator"]} / {c["kind"]}')
    return '\n\n'.join(lines)

def report_html(markdown: str) -> str:
    blocks=[]
    for block in markdown.split('\n\n'):
        if block.startswith('## '): blocks.append('<h2>'+escape(block[3:])+'</h2>')
        elif block.startswith('# '): blocks.append('<h1>'+escape(block[2:])+'</h1>')
        else: blocks.append('<p>'+escape(block).replace('\n','<br>')+'</p>')
    return '''<!doctype html><html lang="ko"><meta charset="UTF-8"><title>해상풍력 분석 보고서</title>
<style>body{max-width:850px;margin:40px auto;padding:24px;font:15px/1.85 "Malgun Gothic",sans-serif;color:#18334c}h1{font-size:26px}h2{margin-top:28px;font-size:19px;border-bottom:1px solid #d7e1ec;padding-bottom:8px}p{margin:8px 0}button{padding:12px;border:1px solid #bacad9;background:#f4f8fb;cursor:pointer}@media print{button{display:none}body{margin:0;font-size:10pt}h2{break-after:avoid}p{orphans:3;widows:3}}</style>
<button onclick="window.print()">인쇄 / PDF로 저장</button>'''+''.join(blocks)+'</html>'

def report_pdf(markdown: str) -> bytes:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    candidates=[os.getenv('KOREAN_FONT_PATH',''),r'C:\Windows\Fonts\malgun.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf']
    font=None
    for file in candidates:
        if file and Path(file).is_file():
            try:
                name='KoreanLocal'
                if name not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont(name,file))
                font=name;break
            except Exception: continue
    if not font:
        font='HYSMyeongJo-Medium'
        if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(UnicodeCIDFont(font))
    styles={
      'title':ParagraphStyle('title',fontName=font,fontSize=18,leading=26,spaceAfter=14,textColor=colors.HexColor('#102c4a'),keepWithNext=True),
      'h2':ParagraphStyle('h2',fontName=font,fontSize=12,leading=18,spaceBefore=12,spaceAfter=5,keepWithNext=True,textColor=colors.HexColor('#1658a7')),
      'p':ParagraphStyle('p',fontName=font,fontSize=9.3,leading=15,spaceAfter=5,wordWrap='CJK'),
    }
    stream=io.BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=19*mm,rightMargin=19*mm,topMargin=20*mm,bottomMargin=19*mm,
                          title='해상풍력 계통연계 및 공급망 검토 보고서',author='Smart Grid Project')
    content=[]
    for block in markdown.split('\n\n'):
        if block.startswith('## '):kind,text='h2',block[3:]
        elif block.startswith('# '):kind,text='title',block[2:]
        else:kind,text='p',block
        content.append(Paragraph(escape(text).replace('\n','<br/>'),styles[kind]))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,8);canvas.setFillColor(colors.HexColor('#67788a'))
        canvas.drawString(19*mm,11*mm,'교육용 간이 모델 / 설계·발주 확정에 사용 불가')
        canvas.drawRightString(A4[0]-19*mm,11*mm,str(doc.page));canvas.restoreState()
    doc.build(content,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
