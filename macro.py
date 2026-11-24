import logging
import math
import os
import time
from datetime import datetime, timedelta
import FinanceDataReader as fdr
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("StockApp")

_MACRO_CACHE = {"ts": 0.0, "data": None}
CACHE_TTL_SECONDS = 300  # 5분 캐시

MACRO_SYMBOLS = [
    {
        "key": "kospi",
        "symbol": "KS11",
        "name": "코스피 (KOSPI)",
        "category": "증시",
        "unit": "",
        "tip": "한국 대표 종합주가지수입니다. 국내 증시 전체의 방향성을 보여줍니다.",
    },
    {
        "key": "nasdaq",
        "symbol": "IXIC",
        "name": "나스닥 (NASDAQ)",
        "category": "증시",
        "unit": "",
        "tip": "미국 기술주 중심 지수로, 한국 반도체·AI 종목과 연동성이 매우 높습니다.",
    },
    {
        "key": "vix",
        "symbol": "^VIX",
        "name": "공포지수 (VIX)",
        "category": "파생·변동성",
        "unit": "",
        "tip": "미국 S&P500 옵션(파생시장) 변동성 지수입니다. 20 이상이면 경계, 30 이상이면 공포 구간으로 봅니다.",
    },
    {
        "key": "us10y",
        "symbol": "^TNX",
        "name": "미 10년 국채금리",
        "category": "금리",
        "unit": "%",
        "tip": "글로벌 시장금리의 기준점입니다. 급등하면 기술주·성장주의 밸류에이션 부담이 커집니다.",
    },
    {
        "key": "usdkrw",
        "symbol": "USD/KRW",
        "name": "원/달러 환율",
        "category": "환율",
        "unit": "원",
        "tip": "환율이 급등(원화 약세)하면 외국인 투자자의 국내 주식 매도 압력이 커지는 경향이 있습니다.",
    },
    {
        "key": "wti",
        "symbol": "CL=F",
        "name": "WTI 국제유가",
        "category": "전쟁·에너지",
        "unit": "$",
        "tip": "전쟁·중동 지정학 리스크의 바로미터입니다. 유가 급등은 인플레이션과 금리 인하 지연을 자극합니다.",
    },
    {
        "key": "gold",
        "symbol": "GC=F",
        "name": "국제 금 (Gold)",
        "category": "안전자산",
        "unit": "$",
        "tip": "전쟁·경기침체 등 지정학 불안이 커질수록 자금이 몰리는 대표적인 안전자산입니다.",
    },
]

MAJOR_EVENT_GUIDES = [
    {
        "name": "미국 FOMC 기준금리 결정",
        "cycle": "연 8회 (약 6주 간격)",
        "impact": "금리 인하·완화 시그널 → 증시 우호적 / 매파적(고금리 유지) → 성장주 변동성 확대",
    },
    {
        "name": "미국 CPI (소비자물가지수)",
        "cycle": "매월 중순 (한국시간 21:30 / 22:30)",
        "impact": "예상치 하회(물가 둔화) → 금리 인하 기대 상승 / 예상치 상회 → 증시 하방 압력",
    },
    {
        "name": "미국 비농업 고용보고서 & 실업률",
        "cycle": "매월 첫째 주 금요일",
        "impact": "적당한 둔화 → 연착륙 호재 / 급격한 고용 악화 → 경기침체 공포 자극",
    },
    {
        "name": "미국 PCE 물가지수",
        "cycle": "매월 말",
        "impact": "연준(Fed)이 가장 중시하는 물가 지표로 FOMC 금리 경로에 직접 영향",
    },
    {
        "name": "한국은행 금융통화위원회 (금통위)",
        "cycle": "연 8회",
        "impact": "국내 기준금리·환율·은행/부동산/내수주 수급 방향성 결정",
    },
    {
        "name": "선물·옵션 동시만기일 (네 마녀의 날)",
        "cycle": "매년 3·6·9·12월 둘째 목(한국) / 셋째 금(미국)",
        "impact": "파생시장 포지션 청산·롤오버로 장 막판 거래량과 단기 변동성 급증",
    },
]


def _safe_float(val, digits: int = 2) -> float | None:
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None


def _fetch_serper_topic(query: str, num: int = 5) -> list[dict]:
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key or api_key.startswith("여기에"):
        return []
    try:
        res = requests.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": "kr", "hl": "ko", "num": num},
            timeout=6,
        )
        if res.status_code != 200:
            return []
        items = []
        for row in res.json().get("news", [])[:num]:
            if not isinstance(row, dict):
                continue
            items.append({
                "title": row.get("title", ""),
                "url": row.get("link", ""),
                "description": row.get("snippet", "") or row.get("source", ""),
                "published": row.get("date", ""),
            })
        return items
    except Exception:
        logger.warning(f"[MACRO]     Serper 검색 실패 (query={query})")
        return []


def collect_macro_overview(force_refresh: bool = False) -> dict:
    """7대 거시·지정학 지표, 시장 위험도 신호등, 발표 예정 일정 및 지정학 속보를 수집한다."""
    now_ts = time.time()
    if not force_refresh and _MACRO_CACHE["data"] and (now_ts - _MACRO_CACHE["ts"] < CACHE_TTL_SECONDS):
        return _MACRO_CACHE["data"]

    logger.info("[MACRO]     거시·지정학 7대 지표 수집 시작")
    start_str = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    indicators = []
    val_map = {}

    for meta in MACRO_SYMBOLS:
        latest_val = None
        change_pct = None
        try:
            df = fdr.DataReader(meta["symbol"], start_str)
            if df is not None and not df.empty:
                latest_val = _safe_float(df["Close"].iloc[-1], 2)
                if len(df) >= 2:
                    prev = float(df["Close"].iloc[-2])
                    if prev and latest_val is not None:
                        change_pct = _safe_float(((latest_val - prev) / prev) * 100.0, 2)
        except Exception:
            logger.warning(f"[MACRO]     지표 조회 실패 ({meta['symbol']})")

        val_map[meta["key"]] = {"value": latest_val, "change_pct": change_pct}
        indicators.append({
            "key": meta["key"],
            "name": meta["name"],
            "category": meta["category"],
            "unit": meta["unit"],
            "value": latest_val,
            "change_pct": change_pct,
            "tip": meta["tip"],
        })

    # 시장 위험도 신호등 판정 (VIX, 미10년금리, 유가, 환율 종합)
    risk_score = 0
    risk_notes = []

    vix = val_map.get("vix", {}).get("value")
    if vix is not None:
        if vix >= 30:
            risk_score += 2
            risk_notes.append(f"VIX 공포지수가 {vix}로 공포(30↑) 구간입니다. 파생·증시 변동성이 매우 큽니다.")
        elif vix >= 20:
            risk_score += 1
            risk_notes.append(f"VIX 공포지수가 {vix}로 경계(20↑) 구간입니다. 단기 흔들림에 유의하세요.")
        else:
            risk_notes.append(f"VIX 공포지수가 {vix}로 비교적 안정된 심리 구간(20 미만)입니다.")

    us10y = val_map.get("us10y", {}).get("value")
    if us10y is not None:
        if us10y >= 4.5:
            risk_score += 1
            risk_notes.append(f"미 10년물 국채금리가 {us10y}%로 높은 수준이라 성장주·기술주에 금리 부담이 있습니다.")
        else:
            risk_notes.append(f"미 10년물 국채금리가 {us10y}%로 증시 부담이 비교적 완화된 수준입니다.")

    wti = val_map.get("wti", {}).get("value")
    if wti is not None and wti >= 85:
        risk_score += 1
        risk_notes.append(f"국제유가(WTI)가 ${wti}로 높아 지정학·인플레이션 경계가 필요합니다.")

    usdkrw = val_map.get("usdkrw", {}).get("value")
    if usdkrw is not None and usdkrw >= 1400:
        risk_score += 1
        risk_notes.append(f"원/달러 환율이 {usdkrw:,.1f}원으로 고환율 구간이라 외국인 수급 변동성에 주의해야 합니다.")

    if risk_score >= 3:
        risk_level = "high"
        risk_label = "경계·공포 (리스크 관리 우선)"
    elif risk_score >= 1:
        risk_level = "medium"
        risk_label = "주의·관찰 (변동성 체크)"
    else:
        risk_level = "low"
        risk_label = "안정 (우호적 거시 환경)"

    geo_news = _fetch_serper_topic("증시 금리 유가 전쟁 지정학", num=5)
    upcoming_news = _fetch_serper_topic("이번주 주요 경제지표 일정 FOMC CPI 금통위 실적발표", num=5)

    result = {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "risk_level": risk_level,
        "risk_label": risk_label,
        "risk_notes": risk_notes,
        "indicators": indicators,
        "upcoming_news": upcoming_news,
        "event_guides": MAJOR_EVENT_GUIDES,
        "geo_news": geo_news,
        "errors": [],
    }

    _MACRO_CACHE["ts"] = now_ts
    _MACRO_CACHE["data"] = result
    logger.info(f"[MACRO]     거시·지정학 데이터 수집 완료 (risk={risk_level}, geo_news={len(geo_news)}, upcoming={len(upcoming_news)})")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    d = collect_macro_overview(force_refresh=True)
    logger.info(f"[TEST]      risk={d['risk_label']}, indicators={len(d['indicators'])}, upcoming={len(d['upcoming_news'])}, geo={len(d['geo_news'])}")
