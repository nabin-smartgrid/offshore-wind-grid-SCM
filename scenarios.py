"""Educational scenario comparison and procurement screening. Demo-only thresholds."""
from dataclasses import replace
from core import Inputs, Results, calculate, screening, overall

def scm_review(x: Inputs, r: Results) -> list[dict]:
    if x.connection != 'HVAC':
        return [dict(기자재='VSC-HVDC 변환소 및 DC 케이블', 우선순위='상세 모델 필요', 검토이유='AC 케이블 간이식을 적용하지 않음', 구매확인='변환소 구성, 공급 범위, 제조사 자료와 납기 확인')]
    q=r.qc_capacity_ratio or 0
    reactor='우선 검토' if q>=.4 else '추가 검토' if q>=.2 else '기본 확인' if q>0 else '현재 입력상 Qc 없음'
    statcom='우선 검토' if r.scr<2 else '추가 검토' if r.scr<3 else '기본 확인'
    loss=r.load_loss_percent
    cable='판정 보류' if loss is None else '우선 검토' if loss>=3 else '추가 검토' if loss>=1 else '기본 확인'
    return [
      dict(기자재='Shunt Reactor',우선순위=reactor,검토이유=f'Qc/정격MW={q:.3f} (수업용 경계 0.20/0.40)',구매확인='보상량, OSS/OnSS 배치, 개폐 단계, Topside 중량 및 부지 영향'),
      dict(기자재='STATCOM / WTG 컨버터',우선순위=statcom,검토이유=f'단순 SCR={r.scr:.2f} (수업용 경계 2/3), 설치 확정 아님',구매확인='WTG 가용 Q, 접속점 요구사항, 동적 해석 결과'),
      dict(기자재='해저케이블 / 변압기',우선순위=cable,검토이유='운전출력 0 MW' if loss is None else f'부하전류 저항손실률={loss:.2f}% (총 손실 아님)',구매확인='허용전류, 열적정격, 회선 수, 제조사 데이터시트'),
      dict(기자재='GIS / 차단기',우선순위='별도 해석',검토이유='개폐 서지 및 보호협조는 현재 모델 밖',구매확인='서지 해석, 계통·기자재 인터페이스, 사양 확정 후 발주'),
    ]

def compare_scenarios(base: Inputs, lengths: list[float]) -> list[dict]:
    """Change only length; keep other inputs fixed."""
    if base.connection != 'HVAC':return []
    values=sorted(set([float(base.length_km)]+[float(v) for v in lengths]))
    if not 1<=len(values)<=12 or any(v<0 or v>500 for v in values):
        raise ValueError('케이블 길이 시나리오는 0~500 km, 최대 12개입니다.')
    out=[]
    for km in values:
        x=replace(base,length_km=km);r=calculate(x);actions=scm_review(x,r)
        out.append({'케이블 길이 (km)':km,'충전 무효전력 (Mvar)':round(r.qc_total_mvar,3),
                    '부하전류 저항손실 (MW)':round(r.load_loss_mw,3),
                    '저항손실률 (%)':None if r.load_loss_percent is None else round(r.load_loss_percent,3),
                    '단순 SCR':round(r.scr,3),'리액터 검토':actions[0]['우선순위'],
                    '케이블 검토':actions[2]['우선순위'],'종합 예시 수준':overall(screening(x,r)),
                    '기준 시나리오':abs(km-base.length_km)<1e-9})
    return out

def scenario_takeaways(base: Inputs, rows: list[dict]) -> list[str]:
    if not rows:return ['HVDC 선택 시 AC 케이블 간이식의 길이 비교는 적용하지 않습니다.']
    first,last=rows[0],rows[-1]
    ratio='비교 불가' if first['충전 무효전력 (Mvar)']==0 else f"{last['충전 무효전력 (Mvar)']/first['충전 무효전력 (Mvar)']:.2f}배"
    return [f"길이 {first['케이블 길이 (km)']:g} km에서 {last['케이블 길이 (km)']:g} km로 비교하면 Qc가 {ratio} 변화합니다. 다른 입력값은 고정했습니다.",
      '케이블 길이에 따라 리액터 검토 우선순위가 달라질 수 있지만, Qc는 리액터 발주 용량이 아닙니다.',
      'SCR은 길이만 변경하면 변하지 않습니다. 단락용량이나 정격용량을 바꿔야 달라집니다.',
      '실제 추가 설비, 비용, 납기, COD 지연은 근거 자료가 없어 산정하지 않았습니다.']
