"""Run: python -m streamlit run app.py

The five screens follow the user's submitted project report.
Core calculations and deterministic reports work without any AI API key.
"""
from __future__ import annotations
from dataclasses import asdict
from html import escape
import json, os, sys
import streamlit as st
from core import (Inputs,calculate,screening,overall,equipment,compare_lengths,
                  template_summary,state_digest,DEMO_RULES,MODEL_NOTES)
from evidence import BUILTIN,extract_document,retrieve,llm_prompt,call_gemini,citation_check,check_ai_numbers,available_gemini_models,gemini_model_details,diagnose_gemini_generate
from reporting import report_markdown,report_html,report_pdf
from scenarios import scm_review, compare_scenarios, scenario_takeaways, scenario_procurement_changes

st.set_page_config(page_title='WindGrid | 계통·공급망 분석',page_icon='⚡',layout='wide',initial_sidebar_state='expanded')

def _secret(name: str, default: str = '') -> str:
    """Streamlit Cloud secrets first, local environment second. Never log secrets."""
    try:
        value = st.secrets.get(name)
        if value is not None:
            return str(value)
    except Exception:
        # Missing Streamlit secrets file also raises StreamlitSecretNotFoundError.
        pass
    return os.getenv(name, default)

def _ai_issues(text: str, docs: list[dict], trusted: dict) -> tuple[list[str], list[str], list[str]]:
    valid, invalid = citation_check(text, docs)
    issues = check_ai_numbers(text, trusted)
    if not valid: issues.append('등록된 문서 ID 인용이 없음')
    if invalid: issues.append('등록되지 않은 문서 ID 인용: ' + ', '.join(invalid))
    return valid, invalid, issues

BROWSER = sys.platform == 'emscripten'
if not BROWSER:
    from reporting_v2 import report_pdf_pretty
st.markdown('''<style>
.stApp{background:#f7f9fc} [data-testid="stSidebar"]{background:#edf2f8;border-right:1px solid #dce4ee}
.block-container{padding-top:1.5rem;padding-bottom:2rem;max-width:1500px}
h1,h2,h3{letter-spacing:-.04em} [data-testid="stMetric"]{background:white;border:1px solid #dce4ee;border-radius:12px;padding:18px}
[data-testid="stMetricValue"]{font-size:2rem;color:#183553}
.wg-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.wg-word{font-size:12px;letter-spacing:.2em;font-weight:800;color:#25728c}.wg-badge{font-size:12px;color:#3c6178;background:#e7f2f5;border:1px solid #c7e3e8;border-radius:25px;padding:6px 12px}
.wg-card{background:white;border:1px solid #dce4ee;border-radius:14px;padding:20px 22px;margin:8px 0 16px}.wg-muted{color:#6b7e91;font-size:13px}.wg-rule{font-size:13px;line-height:1.65;padding:10px 13px;border-radius:8px;background:#fff5df;color:#75541c;margin:10px 0}
.wg-table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.65}.wg-table th{padding:12px;background:#edf3f9;text-align:left;color:#264969}.wg-table td{padding:13px 12px;border-bottom:1px solid #e4eaf0;vertical-align:top}
.wg-small{font-size:13px;line-height:1.75;color:#60768b}.wg-title{font-size:19px;font-weight:750;margin:0 0 12px;color:#153a60}.wg-step{padding:15px 0;border-bottom:1px solid #e4eaf0}
.wg-foot{font-size:12px;color:#74849b;padding-top:18px;border-top:1px solid #e2e8f1;margin-top:20px}
</style>''',unsafe_allow_html=True)

if 'config' not in st.session_state:st.session_state.config=asdict(Inputs())
if 'documents' not in st.session_state:st.session_state.documents=[]
if 'llm_result' not in st.session_state:st.session_state.llm_result=None
config=st.session_state.config

def load_default():
    st.session_state.config=asdict(Inputs())
    for key in list(st.session_state):
        if key.startswith('in_'):del st.session_state[key]
    st.session_state.llm_result=None

with st.sidebar:
    st.markdown('### WindGrid <span style="font-size:12px;color:#65849d">SCM LAB</span>',unsafe_allow_html=True)
    st.caption('스마트그리드 개인 프로젝트 · 곽나빈')
    st.markdown('**프로젝트 입력 조건**')
    with st.form('input_form'):
        cap=st.number_input('발전단지 정격용량 (MW)',min_value=1.0,max_value=10000.0,value=config['capacity_mw'],step=50.0,key='in_cap')
        length=st.number_input('해저케이블 길이 (km)',min_value=0.0,max_value=500.0,value=config['length_km'],step=5.0,key='in_len')
        voltage=st.selectbox('연계전압 (kV, 선간 RMS)',[154.0,345.0],index=[154.0,345.0].index(config['voltage_kv']),key='in_volt')
        conn=st.selectbox('연계 방식',['HVAC','VSC-HVDC'],index=['HVAC','VSC-HVDC'].index(config['connection']),key='in_conn')
        ssc=st.number_input('연계점 단락용량 (MVA)',min_value=1.0,max_value=100000.0,value=config['short_circuit_mva'],step=100.0,help='계통의 강도를 나타내는 입력값입니다. SCR은 이 값÷단지 정격MW로 계산합니다.',key='in_ssc')
        with st.expander('상세 가정 · 단위 확인'):
            project=st.text_input('프로젝트명',value=config['project'],max_chars=120,key='in_project')
            cod=st.text_input('목표 COD (YYYY-MM)',value=config['cod'],key='in_cod')
            op=st.number_input('운전 유효전력 (MW)',min_value=0.0,max_value=10000.0,value=config['operating_mw'],step=50.0,key='in_op')
            circuits=st.number_input('동일 병렬 회선 수 (가정)',min_value=1,max_value=20,value=config['circuits'],key='in_n')
            c=st.number_input('상별 정전용량 (μF/km, 가정)',min_value=0.0,max_value=3.0,value=config['capacitance_uf_km'],step=.01,format='%.3f',key='in_c')
            r=st.number_input('상별 저항 (Ω/km, 가정)',min_value=0.0,max_value=5.0,value=config['resistance_ohm_km'],step=.005,format='%.4f',key='in_r')
            hz=st.selectbox('주파수 (Hz)',[50.0,60.0],index=[50.0,60.0].index(config['frequency_hz']),key='in_hz')
            pf=st.number_input('역률',min_value=.1,max_value=1.0,value=config['power_factor'],step=.01,key='in_pf')
            demo=st.checkbox('수업용 예시 판정규칙 사용',value=config['demo_rules'],key='in_rules')
            st.caption('회선 수·C·R·판정 경계는 실제 설계값 또는 공인 기준이 아닙니다.')
        submitted=st.form_submit_button('입력 적용 · 분석 실행',type='primary',use_container_width=True)
    if submitted:
        candidate=Inputs(project,cap,op,length,voltage,conn,ssc,cod,c,r,hz,pf,int(circuits),demo)
        try:
            candidate.validate();st.session_state.config=asdict(candidate)
            st.session_state.llm_result=None;st.session_state.comparison_ai=None;st.session_state.last_run=True
        except ValueError as err:st.error(str(err))
    st.button('기본 예시로 되돌리기',on_click=load_default,use_container_width=True)
    st.caption('변경 후 분석 실행을 눌러 적용하세요. 실제 계통·제조사 데이터는 연결되어 있지 않습니다.')
    st.divider()
    st.caption('계산은 코드, 해석은 LLM\n\n현재 기본 모드: API 없이 계산·요약')

x=Inputs(**st.session_state.config)
r=calculate(x)
rows=screening(x,r)
docs=BUILTIN+st.session_state.documents
fingerprint=state_digest(x,docs)
if st.session_state.llm_result and st.session_state.llm_result['fingerprint']!=fingerprint:
    st.session_state.llm_result=None

st.markdown('<div class="wg-top"><span class="wg-word">OFFSHORE WIND / GRID TO PROCUREMENT</span><span class="wg-badge">교육용 프로토타입 · v0.4.2</span></div>',unsafe_allow_html=True)
st.title('해상풍력 계통연계 · 공급망 영향 분석')
st.caption('전기적 조건을 계산하고, 기자재와 조달 일정에서 확인할 일을 연결합니다.')
nav=st.radio('화면 이동',['① 프로젝트 입력','② 근거 문서','③ 분석 진행','④ 분석 결과','⑤ AI 보고서','⑥ 시나리오 비교'],index=3,horizontal=True,label_visibility='collapsed',key='nav')
st.markdown('<div class="wg-rule">수업용 가정값을 사용한 간이 모델입니다. 결과는 검토의 출발점이며, 설계 확정·계통 합격·발주 용량을 뜻하지 않습니다.</div>',unsafe_allow_html=True)

def nice(v:float|None,dec:int=2):return '미산출' if v is None else f'{v:,.{dec}f}'

def show_metrics():
    a,b,c,d=st.columns(4)
    a.metric('충전 무효전력 합계',nice(r.qc_total_mvar)+' Mvar' if r.qc_total_mvar is not None else '미산출',help='보상 전 3상 합계 × 병렬 회선 수. 리액터 발주 용량이 아닙니다.')
    b.metric('부하전류 저항손실',nice(r.load_loss_percent)+' %' if r.load_loss_percent is not None else '미정의',help='충전전류 등은 제외한 I²R 추정입니다. 전체 송전손실이 아닙니다.')
    c.metric('단락비 · SCR',f'{r.scr:.2f}',help='단락용량(MVA)÷단지 정격(MW)의 단순 참고값.')
    d.metric('예시 검토 수준',overall(rows),help='사용자가 켠 수업용 경계값을 적용한 결과. 공식 위험등급이 아닙니다.')

if nav.startswith('①'):
    st.subheader('01 / 프로젝트와 가정을 확인하세요')
    st.write('왼쪽 입력창에서 조건을 변경한 뒤 **입력 적용 · 분석 실행**을 누르면 다른 화면에도 반영됩니다.')
    a,b=st.columns([1.2,1])
    with a:
        st.markdown('#### 현재 적용된 입력')
        st.json(asdict(x),expanded=True)
    with b:
        st.markdown('#### 숫자의 출처')
        st.info('500 MW는 제출 보고서의 가상 단지 예시입니다. 65 km·단락용량 1,400 MVA·2회선·R=0.03 Ω/km 등은 이번 시연을 위한 추가 가정입니다.')
        st.write('정전용량 0.2 μF/km는 보고서의 가정값입니다. 실제 제조사 자료는 아직 반영하지 않았습니다.')
        st.markdown('#### 처음 보는 용어')
        st.write('**충전 무효전력:** AC 케이블의 정전용량에 따라 생기는 무효전력의 크기입니다.\n\n**SCR:** 발전단지 크기에 비해 연결 지점의 계통이 얼마나 강한지 살펴보는 단순 지표입니다.\n\n**회선:** 전기를 보내는 3상 케이블 한 세트입니다.')
        st.caption('모델 가정이나 회선 수를 바꾸면 예전 목업 이미지의 숫자와 달라집니다.')

elif nav.startswith('②'):
    st.subheader('02 / 근거 문서 등록')
    st.write('기본 문서는 **과제 계획의 발췌**입니다. 한전 기준 또는 제조사 보증 문서가 아닙니다.')
    st.info('공개 자료만 업로드하세요. 내부 견적·계약서·개인정보는 입력하지 마세요. 업로드만으로 외부 AI에 전송되지는 않습니다.')
    files=st.file_uploader('PDF · TXT · MD / 파일당 10 MB · PDF 최대 60쪽',type=['pdf','txt','md'],accept_multiple_files=True)
    if st.button('문서 등록 / 기존 업로드 교체'):
        new=[];errs=[]
        if len(files)>5:st.error('한 번에 5개 이하로 등록하세요.')
        else:
            for f in files:
                try:new+=extract_document(f.name,f.getvalue())
                except Exception as e:errs.append(f'{f.name}: {str(e)[:200]}')
            if errs:
                for err in errs:st.error(err)
                st.warning('오류가 있어 기존 문서는 유지했습니다.')
            else:
                st.session_state.documents=new;st.session_state.llm_result=None
                st.success(f'{len(files)}개 문서 / {len(new)}개 텍스트 조각 등록. 아래 목록을 갱신합니다.');st.rerun()
    st.caption('세션 메모리에 보관하며 분석 이력 DB는 없습니다. 스캔 PDF의 OCR·표/수식 자동 검증은 지원하지 않습니다.')
    query=st.text_input('근거 검색어','무효전력 리액터 STATCOM 계통 공급망')
    selected=retrieve(docs,query,6)
    st.caption('키워드 일치 기반 검색입니다. 임베딩 기반 RAG 또는 조항의 기술적 타당성 검증은 아닙니다.')
    for c in selected:
        with st.expander(f'[{c["id"]}] {c["name"]} · {c["locator"]}',expanded=False):
            st.caption(c['kind']);st.text(c['text'])
    if not selected:st.warning('검색어와 일치하는 발췌가 없습니다.')

elif nav.startswith('③'):
    st.subheader('03 / 처리 단계와 검증 상태')
    if st.button('현재 입력으로 계산 다시 실행',type='primary'):
        calculate(x);st.session_state.last_run=True;st.success('현재 입력값의 계산과 예시 규칙 적용을 완료했습니다.')
    stages=[('1. 입력 검증','완료','단위·양수 조건·운전출력 범위를 확인했습니다.'),
            ('2. 공학 지표 계산','완료' if x.connection=='HVAC' else '일부 보류','HVAC: Qc·부하전류 I²R·SCR / HVDC: SCR 참고값만 계산'),
            ('3. 예시 판정규칙 적용','적용' if x.demo_rules and x.connection=='HVAC' else '보류','문서에 없는 수치 경계는 수업용 구현 가정으로 명시했습니다.'),
            ('4. 기자재 후보 연결','완료','과제 보고서에 따라 검토 항목을 제시했습니다. 발주 사양이 아닙니다.'),
            ('5. 문서 기반 LLM 해석','생성됨·검증 전' if st.session_state.llm_result else '미실행','⑤ AI 보고서에서 API와 공개 자료 전송 동의 후 별도로 실행합니다.')]
    for title,status,desc in stages:
        st.markdown(f'<div class="wg-card"><strong>{escape(title)}</strong>　<span class="wg-badge">{escape(status)}</span><p class="wg-small">{escape(desc)}</p></div>',unsafe_allow_html=True)
    st.caption('진행 단계는 실제 처리 상태를 표시합니다. API를 호출하지 않고 AI 분석 완료로 표시하지 않습니다.')

elif nav.startswith('④'):
    show_metrics()
    st.caption(f'적용 시나리오: {x.capacity_mw:g} MW / {x.length_km:g} km / {x.voltage_kv:g} kV / {x.circuits}회선 / {x.connection} · 상세 입력은 ① 또는 왼쪽 펼침 메뉴')
    left,right=st.columns([1,1.25],gap='large')
    with left:
        st.markdown('#### 계통 검토 포인트')
        for row in rows:
            icon={'검토 우선':'●','주의':'●','참고':'○','판정 보류':'—'}[row['검토 수준']]
            st.markdown(f'**{icon} {row["항목"]} — {row["검토 수준"]}**')
            st.caption(row['근거'])
        st.markdown('#### 케이블 길이만 바꾸면?')
        if x.connection=='HVAC':
            data=compare_lengths(x)
            st.bar_chart(data,x='길이 (km)',y='충전 무효전력 (Mvar)',height=230)
            st.caption('동일 전압·C·주파수·회선 수 가정. 길이에 선형 비례합니다.')
        else:st.info('HVDC에는 AC 충전 무효전력 그래프를 적용하지 않습니다.')
    with right:
        st.markdown('#### 기자재 · SCM 영향')
        table='<table class="wg-table"><thead><tr><th>기자재</th><th>확인할 사항</th><th>조달·설계 영향</th></tr></thead><tbody>'
        for row in scm_review(x,r):
            table+='<tr><td><b>'+escape(row['기자재'])+'</b><br><span class="wg-small">'+escape(row['우선순위'])+'</span></td><td>'+escape(row['검토이유'])+'</td><td>'+escape(row['구매확인'])+'</td></tr>'
        st.markdown(table+'</tbody></table>',unsafe_allow_html=True)
        st.caption('출처: 관심영역 보고서 §2·§4·§5. 납기·가격·용량은 미확인입니다.')
    st.markdown('#### 결과 읽기')
    st.info(template_summary(x,r))
    st.caption('현재 요약은 코드가 만든 템플릿입니다. LLM 생성 결과가 아닙니다.')
    with st.expander('계산식 · 판정규칙 · 한계 보기'):
        st.latex(r'Q_c=n\,V_{LL}^{2}\,(2\pi f)\,C_{phase}\,\ell')
        st.latex(r'I=\frac{P}{\sqrt{3}\,V_{LL}\,PF\,n},\quad P_{loss}=n\,3I^2R_{phase}\ell,\quad SCR=\frac{S_{sc}}{P_{rated}}')
        st.write('SI 단위로 계산 후 Mvar/MW로 환산합니다. Qc는 보고서의 식, 손실·SCR 세부 산식과 회선 수는 이번 구현의 명시적 간이 모델입니다.')
        for key,val in DEMO_RULES.items():st.write(f'**{key}**: {val}')
        for note in MODEL_NOTES:st.write('- '+note)

elif nav.startswith('⑤'):
    st.subheader('05 / 보고서 생성과 근거 확인')
    st.write('API 없이도 계산 결과·가정·검토사항이 담긴 보고서를 저장할 수 있습니다.')
    ai=st.session_state.llm_result
    md=report_markdown(x,r,docs,ai['text'] if ai and not ai.get('issues') else '')
    col1,col2,col3=st.columns(3)
    col1.download_button('HTML 보고서 저장',report_html(md),'windgrid_report.html','text/html',use_container_width=True)
    col2.download_button('입력·계산 JSON 저장',json.dumps({'inputs':asdict(x),'results':asdict(r),'rules':DEMO_RULES,'source':'교육용 가정'},ensure_ascii=False,indent=2),'windgrid_results.json','application/json',use_container_width=True)
    if not BROWSER:
        try: col3.download_button('개선된 PDF 저장',report_pdf_pretty(x,r,docs,ai['text'] if ai and not ai.get('issues') else '',model=ai['model'] if ai and not ai.get('issues') else ''),'windgrid_report.pdf','application/pdf',use_container_width=True)
        except (ImportError,RuntimeError) as e:col3.error(f'PDF 생성 불가: {e}')
    else:col3.info('브라우저판: HTML 보고서를 열어 인쇄 → PDF로 저장')
    with st.expander('LLM 연결 (선택) · 공개 자료만 전송',expanded=False):
        st.warning('현재 기본 화면은 템플릿 모드입니다. 아래 버튼을 눌러야 외부 API를 호출합니다. 호출 비용이 발생할 수 있습니다.')
        if BROWSER:
            st.info('브라우저 실행판에서는 API 키 입력을 비활성화했습니다. LLM 연동은 ZIP의 Python 서버판에서 설정하세요.')
        else:
            key=_secret('GEMINI_API_KEY')
            if key: st.success('Gemini API 키가 Streamlit Cloud Secrets에 설정됨')
            else: st.info('Cloud 관리 화면 → App settings → Secrets에 GEMINI_API_KEY를 등록하세요.')
            model=st.text_input('Gemini 모델 ID',value=_secret('GEMINI_MODEL','gemini-3.8-flash'),help='현재 API 키로 사용 가능한 모델을 아래 진단 버튼에서 확인하세요.')
            with st.expander('API 연결 진단 (프로젝트 데이터 전송 없음)', expanded=False):
                st.caption('모델 목록·메타데이터 조회는 생성 호출과 다릅니다. 짧은 생성 테스트는 12초 제한, 재시도 없음. API 키는 표시하지 않습니다.')
                api_version=st.selectbox('진단할 API 버전', ['v1beta','v1'], key='diag_api_version')
                if st.button('선택 API 버전의 모델 목록 조회', disabled=not key):
                    try:
                        with st.spinner('모델 목록 조회 중...'):
                            st.session_state['gemini_models']=available_gemini_models(key,api_version)
                            st.session_state['gemini_models_version']=api_version
                    except Exception as err: st.error(str(err)[:420])
                known=st.session_state.get('gemini_models', []) if st.session_state.get('gemini_models_version')==api_version else []
                if known:
                    st.success(f'{api_version} generateContent 지원 모델 목록: {len(known)}개')
                    st.write('현재 모델:', '목록에 있음' if model in known else '목록에 없음')
                    st.caption('일부: '+', '.join([m for m in known if 'flash' in m][:12]))
                if st.button('선택 모델 메타데이터 확인', disabled=not(key and model)):
                    try:
                        details=gemini_model_details(key,model,api_version)
                        st.json(details)
                    except Exception as err: st.error(str(err)[:420])
                if st.button('짧은 생성 호출 테스트 (12초)', disabled=not(key and model)):
                    try:
                        with st.spinner(f'{api_version} 생성 호출 확인 중...'):
                            answer=diagnose_gemini_generate(key,model,api_version)
                        st.success(f'{api_version} 생성 호출 성공')
                        st.caption('응답: '+answer[:100])
                        st.session_state['gemini_working_api_version']=api_version
                        st.session_state['gemini_working_model']=model
                    except Exception as err:
                        st.error(str(err)[:420])
                st.caption('404면 모델·버전·API 프로젝트 제한 확인. 429면 할당량, 503이면 서버/경로 문제 가능. 오류의 짧은 진단만 표시합니다.')
            working_ver=st.session_state.get('gemini_working_api_version','v1beta')
            working_model=st.session_state.get('gemini_working_model','')
            st.caption(f'실제 분석 API 버전: {working_ver}'+ (' (간단 테스트에서 확인)' if working_model==model else ' (기본값; 테스트 미확인)'))
            prompt_query=st.text_input('분석 초점','무효전력 리액터 STATCOM 계통 공급망 납기')
            selected=retrieve(docs,prompt_query,6)
            payload={'inputs':asdict(x),'results':asdict(r),'screening':rows,'notes':'판정규칙은 수업용 가정, 공인기준 아님'}
            prompt=llm_prompt(payload,selected)
            st.caption(f'전송 대상: Google Gemini API / 계산·입력값 + 선택된 발췌 {len(selected)}개. 키는 보고서에 저장되지 않습니다.')
            with st.expander('외부로 전송할 텍스트 미리보기'):st.text(prompt)
            consent=st.checkbox('위 자료가 공개 가능하며, Gemini API로 전송하는 데 동의합니다.')
            if st.button('근거를 포함한 AI 해석 생성',disabled=not consent or not key or not model or not selected,type='primary'):
                try:
                    with st.spinner('실제 Gemini API에 요청 중...'):
                        text=call_gemini(key,model,prompt,working_ver if working_model==model else 'v1beta')
                    valid,invalid,issues=_ai_issues(text,selected,{'inputs':asdict(x),'results':asdict(r)})
                    st.session_state.llm_result={'text':text,'fingerprint':fingerprint,'model':model,'valid':valid,'invalid':invalid,'issues':issues}
                    st.rerun()
                except Exception as err:st.error(str(err)[:250])
    if ai:
        st.markdown('#### 실제 LLM 응답 · 전문가 검토 전')
        st.markdown(ai['text'])
        st.caption(f'모델: {ai["model"]} / 존재하는 문서 ID 인용: {len(ai["valid"])} / 미등록 인용: {len(ai["invalid"])}')
        if ai.get('issues'):
            st.error('자동 검증에서 확인이 필요한 사항이 발견됨. 이 AI 해석은 PDF에 포함되지 않습니다.')
            for issue in ai['issues']:st.write('• '+issue)
        else: st.success('숫자 대조와 문서 ID 형식 검사를 통과함. 문서 내용과 판단 타당성은 직접 검증 필요.')
    else:
        st.markdown('#### 자동 요약 · 규칙 기반')
        st.write(template_summary(x,r))
        st.caption('LLM 미연결·미호출. API 응답으로 가장한 문장은 포함하지 않습니다.')
    with st.expander('보고서 전체 미리보기'):st.markdown(md)
    st.markdown('#### 근거와 한계')
    st.write('현재 제공된 자료만으로 실제 납기·가격·허용 손실률·리액터 용량·STATCOM 필요성은 확정할 수 없습니다.')
    for c in BUILTIN:
        st.caption(f'[{c["id"]}] {c["name"]} / {c["locator"]} / {c["kind"]}')

else:
    st.subheader('06 / 케이블 길이별 시나리오 비교')
    st.write('**한 번에 변수 하나만 바꿔서** 결과가 어떻게 달라지는지 살펴봅니다. 이번 비교에서는 케이블 길이만 변경합니다.')
    if x.connection!='HVAC':
        st.warning('현재 VSC-HVDC 선택 상태입니다. AC 케이블 충전 무효전력 계산을 적용하지 않으므로 HVAC를 선택해야 길이 비교가 가능합니다.')
    else:
        chosen=st.multiselect('비교할 케이블 길이 (km)',options=[10,20,30,40,50,60,65,70,80,90,100,120,150,200],default=[30,50,80],max_selections=10,
                              help='현재 입력한 기준 길이는 자동 포함됩니다. 다른 조건은 고정됩니다.')
        comparison=compare_scenarios(x,chosen)
        st.caption(f'고정 조건: 정격 {x.capacity_mw:g}MW / 운전 {x.operating_mw:g}MW / {x.voltage_kv:g}kV / {x.circuits}회선 / C={x.capacitance_uf_km:g}μF/km / SCR={r.scr:.2f}')
        st.bar_chart(comparison,x='케이블 길이 (km)',y='충전 무효전력 (Mvar)',height=260)
        st.dataframe(comparison,use_container_width=True,hide_index=True)
        st.markdown('#### 조건 변화에 따른 SCM·일정 검토사항')
        st.dataframe(scenario_procurement_changes(x,comparison),use_container_width=True,hide_index=True)
        st.caption('우선순위는 수업용 가정이며 실제 리드타임·가격·COD 지연을 예측하거나 발주를 확정하지 않습니다.')
        st.markdown('#### 비교 결과 해석 (규칙 기반, AI 미사용)')
        for line in scenario_takeaways(x,comparison):st.write('- '+line)
        st.markdown('#### 기자재별 조달 검토 우선순위 (현재 입력값 기준)')
        st.dataframe(scm_review(x,r),use_container_width=True,hide_index=True)
        st.caption('우선순위는 수업용 예시 경계값에 따른 체크리스트입니다. 실제 설비 필요성·용량·가격·납기를 확정하지 않습니다.')
        st.markdown('#### 시나리오 비교 보고서 다운로드')
        st.caption('PDF에는 그래프·비교표·SCM 검토사항이 포함됩니다. LLM 분석은 실제 API 실행 시에만 표시됩니다.')
        comp_ai=st.session_state.get('comparison_ai')
        comp_key=state_digest(x,docs)+json.dumps(chosen)
        if comp_ai and comp_ai['fingerprint']!=comp_key:
            comp_ai=None
            st.session_state.comparison_ai=None
        if not BROWSER:
            st.download_button('시나리오 비교 PDF 다운로드',report_pdf_pretty(x,r,docs,comp_ai['text'] if comp_ai and not comp_ai.get('issues') else '',comparison,model=comp_ai['model'] if comp_ai and not comp_ai.get('issues') else ''),
                file_name='windgrid_scenario_comparison.pdf',mime='application/pdf',type='primary')
        else:
            st.info('브라우저 실행판에서는 PDF 대신 Streamlit 서버판에서 다운로드하세요.')
        st.download_button('시나리오 비교 JSON 다운로드',json.dumps({'baseline':asdict(x),'comparison':comparison,'review':scm_review(x,r)},ensure_ascii=False,indent=2),
            file_name='windgrid_scenario_comparison.json',mime='application/json')
        with st.expander('LLM으로 시나리오 비교 해석 (선택, 실제 Gemini API)',expanded=False):
            st.write('계산은 Python이 수행합니다. LLM은 계산 결과를 해석하고 문서 근거가 있는 조달 검토사항을 제안합니다.')
            if BROWSER:
                st.info('브라우저판에서는 API 호출을 지원하지 않습니다.')
            else:
                api_key=_secret('GEMINI_API_KEY')
                if api_key: st.success('Gemini API 키 설정 확인')
                else: st.info('Streamlit Cloud Secrets에 GEMINI_API_KEY를 설정하세요.')
                model_id=st.text_input('Gemini 모델 ID',value=_secret('GEMINI_MODEL','gemini-2.5-flash'),key='comp_model')
                evidence_docs=retrieve(docs,'해저케이블 무효전력 리액터 공급망 계통',6)
                payload={'baseline':asdict(x),'baseline_results':asdict(r),'comparison':comparison,
                         'scm_review':scm_review(x,r),'caveat':'검토 경계는 수업용 가정. 납기, 가격, 발주량, COD 지연은 미산출.'}
                prompt=llm_prompt(payload,evidence_docs)
                st.caption(f'외부 전송: 계산 입력/결과, 시나리오 {len(comparison)}개, 공개 문서 발췌 {len(evidence_docs)}개. 회사 내부자료를 올리지 마세요.')
                with st.expander('외부로 전송할 내용 확인'):st.text(prompt)
                agree=st.checkbox('입력과 문서 발췌가 외부 API로 전송되어도 되는 공개 자료임을 확인함',key='comp_agree')
                if st.button('Gemini로 시나리오 분석 생성',disabled=not(agree and api_key and model_id and evidence_docs),type='primary'):
                    try:
                        with st.spinner('실제 Gemini API 응답 대기 중...'):
                            response=call_gemini(api_key,model_id,prompt,st.session_state.get('gemini_working_api_version','v1beta') if st.session_state.get('gemini_working_model')==model_id else 'v1beta')
                        valid,invalid,issues=_ai_issues(response,evidence_docs,payload)
                        st.session_state.comparison_ai={'text':response,'fingerprint':comp_key,'model':model_id,'valid':valid,'invalid':invalid,'issues':issues}
                        st.rerun()
                    except Exception as err:st.error(str(err)[:300])
        if comp_ai:
            st.markdown('#### 실제 LLM 해석 (전문가 검증 전)')
            st.write(comp_ai['text'])
            st.caption(f'인용 ID 확인: {len(comp_ai["valid"])}개 / 미등록 ID: {len(comp_ai["invalid"])}개. ID 일치는 원문 내용 검증을 뜻하지 않습니다.')
            if comp_ai.get('issues'):
                st.error('자동 검증에서 확인 필요: PDF에는 이 AI 해석을 포함하지 않음')
                for issue in comp_ai['issues']:st.write('• '+issue)
            else: st.success('숫자 대조 및 문서 ID 형식 검사를 통과함. 원문 내용 검증은 별도 필요.')

st.markdown('<div class="wg-foot">김희진 교수님 스마트그리드 개인 프로젝트 · 공개 자료 기반 가상 단지 · 계산은 코드, 해석은 LLM<br>숫자 검증 / 규칙의 출처 / AI 인용 검증은 서로 다른 작업입니다.</div>',unsafe_allow_html=True)
