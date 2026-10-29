"""Educational, deterministic grid indicators. Not a grid-compliance or design tool.

Source: user's Smart Grid interest-area report, sections 2/4/5.
Qc follows the report. Equal parallel circuits, load-current-only I²R loss,
SCR = short-circuit MVA / rated MW, and demo bands are implementation assumptions.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from math import isfinite, pi, sqrt
import hashlib
import json

MODEL_VERSION = '0.1.0-education'

@dataclass(frozen=True)
class Inputs:
    project: str = '서남해 가상 해상풍력 500 MW'
    capacity_mw: float = 500.0
    operating_mw: float = 500.0
    length_km: float = 65.0
    voltage_kv: float = 154.0
    connection: str = 'HVAC'
    short_circuit_mva: float = 1400.0
    cod: str = '2033-12'
    capacitance_uf_km: float = 0.2
    resistance_ohm_km: float = 0.03
    frequency_hz: float = 60.0
    power_factor: float = 1.0
    circuits: int = 2
    demo_rules: bool = True

    def validate(self) -> None:
        nonnegative = ('operating_mw', 'length_km', 'capacitance_uf_km', 'resistance_ohm_km')
        positive = ('capacity_mw', 'voltage_kv', 'short_circuit_mva', 'frequency_hz', 'power_factor')
        for name in nonnegative + positive:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f'{name}: 유한한 숫자를 입력하세요.')
            if value < 0 or (name in positive and value <= 0):
                raise ValueError(f'{name}: 입력 범위를 확인하세요.')
        if self.operating_mw > self.capacity_mw:
            raise ValueError('운전 유효전력은 단지 정격용량보다 클 수 없습니다.')
        if self.power_factor > 1:
            raise ValueError('역률은 0보다 크고 1 이하여야 합니다.')
        if isinstance(self.circuits, bool) or not isinstance(self.circuits, int) or not 1 <= self.circuits <= 20:
            raise ValueError('병렬 회선 수는 1~20의 정수여야 합니다.')
        if self.connection not in ('HVAC', 'VSC-HVDC'):
            raise ValueError('연계 방식은 HVAC 또는 VSC-HVDC입니다.')
        import re
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', self.cod):
            raise ValueError('목표 COD는 YYYY-MM 형식으로 입력하세요.')
        if not self.project.strip() or len(self.project) > 120:
            raise ValueError('프로젝트명은 1~120자로 입력하세요.')

@dataclass(frozen=True)
class Results:
    qc_per_circuit_mvar: float | None
    qc_total_mvar: float | None
    current_per_circuit_a: float | None
    load_loss_mw: float | None
    load_loss_percent: float | None
    scr: float
    qc_capacity_ratio: float | None
    notes: tuple[str, ...]

DEMO_RULES = {
    'Qc/정격MW': '0.20 미만: 참고 / 0.20 이상~0.40 미만: 주의 / 0.40 이상: 검토 우선',
    '부하전류 저항손실률': '1% 미만: 참고 / 1% 이상~3% 미만: 주의 / 3% 이상: 검토 우선',
    'SCR': '3 이상: 참고 / 2 이상~3 미만: 주의 / 2 미만: 검토 우선',
}

MODEL_NOTES = (
    '정상상태 간이 계산입니다. 조류계산, 전압 안정도·고조파·과도 해석은 수행하지 않습니다.',
    '전압은 선간 RMS, 정전용량과 저항은 상별·km당 값이며 병렬 회선은 동일하다고 가정합니다.',
    'Qc는 보상 전 충전 무효전력의 크기입니다. 발주할 리액터 용량 또는 실제 순무효전력이 아닙니다.',
    '저항손실은 부하전류 성분만의 I²R 계산입니다. 충전전류·시스·유전체·변압기·컨버터 손실은 제외합니다.',
    '케이블 허용전류, N-1, 계통 접속 가능 여부는 판정하지 않습니다.',
    'SCR은 단일 연계점의 단순 참고지표입니다. 낮은 값만으로 불안정 또는 STATCOM 필요성을 확정하지 않습니다.',
    '기본 C·R·회선 수 및 판정 경계는 시연 가정입니다. 제조사 자료나 실제 계통기준으로 검증되지 않았습니다.',
    '기자재 목록은 검토 후보이며 공급사, 가격, 납기, 발주 수량을 확정하지 않습니다.',
)

def calculate(x: Inputs) -> Results:
    x.validate()
    scr = x.short_circuit_mva / x.capacity_mw
    if x.connection == 'VSC-HVDC':
        return Results(None, None, None, None, None, scr, None,
            MODEL_NOTES + ('VSC-HVDC는 AC 케이블 식을 적용하지 않습니다. DC 케이블·변환소 모델이 없어 해당 값은 미산출입니다.',))
    # (kV*1000)^2 * 2*pi*f * (uF/km*1e-6) * km / 1e6 -> Mvar
    qc_one = x.voltage_kv**2 * 2*pi*x.frequency_hz*x.capacitance_uf_km*x.length_km*1e-6
    qc_total = qc_one*x.circuits
    amps = x.operating_mw*1000/(sqrt(3)*x.voltage_kv*x.power_factor*x.circuits)
    loss = x.circuits * 3 * amps**2 * x.resistance_ohm_km*x.length_km / 1e6
    pct = loss/x.operating_mw*100 if x.operating_mw > 0 else None
    return Results(qc_one, qc_total, amps, loss, pct, scr, qc_total/x.capacity_mw, MODEL_NOTES)

def screening(x: Inputs, r: Results) -> list[dict]:
    if x.connection != 'HVAC' or not x.demo_rules:
        reason = 'HVDC 상세 모델 미구현' if x.connection != 'HVAC' else '예시 규칙 미적용'
        return [{'항목': k, '검토 수준': '판정 보류', '근거': reason, '점수': None}
                for k in ('케이블 충전 무효전력', '부하전류 저항손실', '계통 강도(SCR)')]
    q = r.qc_capacity_ratio or 0
    p = r.load_loss_percent
    scores = [2 if q >= .4 else 1 if q >= .2 else 0,
              None if p is None else 2 if p >= 3 else 1 if p >= 1 else 0,
              2 if r.scr < 2 else 1 if r.scr < 3 else 0]
    names = ['케이블 충전 무효전력', '부하전류 저항손실', '계통 강도(SCR)']
    why = [f'Qc/정격MW = {q:.3f} · 수업용 경계 0.20 / 0.40',
           '운전출력 0 MW: 손실률 미정의' if p is None else f'{p:.2f}% · 수업용 경계 1% / 3%',
           f'SCR = {r.scr:.2f} · 수업용 경계 2 / 3']
    return [{'항목': k, '검토 수준': ['참고','주의','검토 우선'][s] if s is not None else '판정 보류',
             '근거': w, '점수': s} for k,s,w in zip(names,scores,why)]

def overall(rows: list[dict]) -> str:
    scores = [row['점수'] for row in rows if row['점수'] is not None]
    return ['참고','주의','검토 우선'][max(scores)] if scores else '판정 보류'

def equipment(x: Inputs, r: Results) -> list[dict]:
    if x.connection != 'HVAC':
        return [dict(기자재='VSC-HVDC 변환소', 상태='상세 모델 필요', 검토사항='변환소·DC 케이블·AC 접속점 요구사항을 별도 확인', 공급망영향='납기·가격 미확인 / 현재 모델로 경제성 비교 불가', 근거='관심영역 보고서 §2·§4')]
    return [
        dict(기자재='Shunt Reactor', 상태='검토 후보' if (r.qc_total_mvar or 0)>0 else '입력상 Qc 없음', 검토사항='필요 보상량·해상/육상 배치·개폐 단계 확인', 공급망영향='OSS 배치 시 중량·설계 영향 / OnSS 배치 시 부지 영향', 근거='관심영역 보고서 §2'),
        dict(기자재='STATCOM / WTG 컨버터', 상태='요건 확인', 검토사항='WTG 가용 Q와 접속점의 동적 전압 요구사항 비교', 공급망영향='별도 장치 필요 여부·사양 확정 후 조달 범위 결정', 근거='관심영역 보고서 §2·§3'),
        dict(기자재='변압기 / 해저케이블', 상태='사양 검토', 검토사항='정격·회선 구성·허용전류·손실 자료 확인', 공급망영향='제조사 공개 자료 및 납기 근거 확보 필요', 근거='관심영역 보고서 §1·§4'),
        dict(기자재='GIS / 차단기', 상태='별도 해석', 검토사항='개폐 서지·보호협조는 현재 계산 범위 밖', 공급망영향='계통·기자재 인터페이스 확인 / 자동 사양 확정 금지', 근거='관심영역 보고서 §2·§5'),
    ]

def compare_lengths(x: Inputs) -> list[dict]:
    rows = []
    for km in sorted(set([30.0, 50.0, float(x.length_km), 80.0])):
        rr = calculate(replace(x, length_km=km))
        rows.append({'길이 (km)': km, '충전 무효전력 (Mvar)': rr.qc_total_mvar,
                     '부하전류 저항손실 (MW)': rr.load_loss_mw})
    return rows

def state_digest(x: Inputs, snippets: list[dict]) -> str:
    data = json.dumps({'inputs':asdict(x),'snippets':snippets},ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def template_summary(x: Inputs, r: Results) -> str:
    if x.connection != 'HVAC':
        return (f'{x.project}: VSC-HVDC 선택으로 AC 케이블 충전 무효전력과 손실 계산은 적용하지 않았습니다. '
                f'SCR 참고값은 {r.scr:.2f}입니다. 변환소 모델·정격·제어 조건 확보 후 별도 분석이 필요합니다. '
                '이 문장은 규칙 기반 템플릿이며 LLM 생성 결과가 아닙니다.')
    return (f'{x.voltage_kv:g} kV, {x.length_km:g} km, {x.circuits}회선의 가정에서 보상 전 충전 무효전력은 '
            f'총 {r.qc_total_mvar:.2f} Mvar(회선당 {r.qc_per_circuit_mvar:.2f} Mvar)입니다. '
            f'부하전류 성분의 저항손실은 {r.load_loss_mw:.2f} MW이며 전체 송전손실은 아닙니다. '
            f'SCR {r.scr:.2f}는 상세 계통 검토를 위한 참고값입니다. 리액터의 필요량·배치와 '
            'WTG의 무효전력 능력을 먼저 확인하고, STATCOM 필요성은 실제 계통요건·동적 해석으로 판단해야 합니다. '
            '기자재 사양이 확정되기 전에는 발주 수량·가격·납기·COD 영향을 확정하지 않습니다. [과제 보고서 §2·§4·§5]')
