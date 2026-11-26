import logging
import os
import threading
import time
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("StockApp")

KRX_API_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
KRX_LOGIN_INIT_URL = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001.cmd"
KRX_LOGIN_JSP_URL = "https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc"
KRX_LOGIN_POST_URL = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd"
KRX_REFERER = "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

SESSION_TTL_SECONDS = 20 * 60   # 20분 세션 재사용
RESULT_CACHE_TTL_SECONDS = 300  # 5분 종목별 결과 캐시

INSTITUTION_TRAITS = {
    "연기금 등": {
        "role": "초장기 핵심 수급",
        "impact": "국민연금 등 장기 자금입니다. 꾸준한 순매수는 주가 하방을 탄탄하게 지지하는 중장기 신뢰 신호로 봅니다.",
    },
    "투신": {
        "role": "펀드·운용사 자금",
        "impact": "자산운용사 펀드 자금입니다. 실적 개선 기대감이 커질 때 유입되며 중기 상승 추세를 강화하는 경향이 있습니다.",
    },
    "금융투자": {
        "role": "증권사 단기·차익 매매",
        "impact": "증권사 자기매매 및 ETF 유동성공급(LP)·차익거래 비중이 커 단기 매매 성향이 강합니다. 만기일·배당락 전후 변동성에 유의하세요.",
    },
    "사모": {
        "role": "기민한 모멘텀 자금",
        "impact": "고수익을 노리는 공격적·단기 성향 자금입니다. 실적 서프라이즈나 이벤트 재료에 빠르게 반응하고 차익실현도 빠른 편입니다.",
    },
    "보험": {
        "role": "안정·가치형 기관",
        "impact": "배당과 안정적 실적을 중시하는 중장기 기관 자금입니다.",
    },
    "은행": {
        "role": "보수적 기관 자금",
        "impact": "비중은 크지 않으나 보수적인 자산 배분 성격의 자금입니다.",
    },
    "기타금융": {
        "role": "종금·저축은행 등",
        "impact": "기타 금융기관 자금으로, 전체 기관 수급의 보조 흐름으로 참고합니다.",
    },
}

EXTENDED_MARKET_GUIDES = [
    {
        "key": "lending_balance",
        "name": "대차잔고 (주식 대여 잔고)",
        "source_note": "해설 가이드 · 한국예탁결제원(SEIBro)·증권사 확인 항목",
        "summary": "기관·외국인이 주식을 빌려두고 아직 갚지 않은 잔고입니다. 공매도의 '선행 대기 물량' 성격이 강합니다.",
        "bull_impact": "대차잔고가 고점에서 빠르게 감소(상환 증가)하면 공매도 압력이 약해지고 반등(숏커버링) 여력이 커집니다.",
        "bear_impact": "주가 상승 중 대차잔고가 급증하면 향후 공매도 출회 가능성(단기 고점 경계 신호)으로 해석합니다.",
    },
    {
        "key": "credit_ratio",
        "name": "신용비율 (신용융자 잔고율)",
        "source_note": "해설 가이드 · 증권사 MTS/HTS 종목정보 확인 항목",
        "summary": "개인 투자자가 증권사에서 돈을 빌려('빚투') 매수한 주식 비중입니다.",
        "bull_impact": "신용비율이 1~3% 이하로 낮고 안정적이면 급락 시 강제청산(반대매매) 매물 부담이 적습니다.",
        "bear_impact": "신용비율이 5~7% 이상으로 과열되면 주가 하락 시 반대매매가 연쇄적으로 쏟아져 낙폭이 커질 수 있습니다.",
    },
    {
        "key": "stock_program",
        "name": "개별종목 프로그램 순매수",
        "source_note": "해설 가이드 · 위 시장 프로그램(실시간)과 함께 참고",
        "summary": "외국인·기관이 컴퓨터 알고리즘으로 여러 종목을 묶어(바스켓) 자동으로 매매하는 물량입니다.",
        "bull_impact": "비차익 프로그램 순매수가 꾸준히 유입되면 패시브·외국인 자금이 지수와 대형주를 동시에 밀어 올리는 힘으로 작용합니다.",
        "bear_impact": "장중 프로그램 매도가 급증하면 기업 펀더멘털과 무관하게 기계적 매도세로 주가가 눌릴 수 있습니다.",
    },
]


def _parse_int(val) -> int | None:
    if val is None:
        return None
    text = str(val).replace(",", "").strip()
    if not text or text == "-":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_float(val) -> float | None:
    if val is None:
        return None
    text = str(val).replace(",", "").replace("%", "").strip()
    if not text or text == "-":
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _format_eok(amount_won: int | None) -> str:
    if amount_won is None:
        return "-"
    sign = "+" if amount_won > 0 else ("-" if amount_won < 0 else "")
    abs_val = abs(amount_won)
    if abs_val >= 10**8:
        eok = abs_val / 10**8
        return f"{sign}{eok:,.1f}억원" if eok < 100 else f"{sign}{int(round(eok)):,}억원"
    if abs_val >= 10**4:
        return f"{sign}{int(round(abs_val / 10**4)):,}만원"
    return f"{sign}{abs_val:,}원"


def _get_krx_credentials() -> tuple[str, str]:
    krx_id = os.getenv("KRX_ID", "").strip()
    krx_pw = os.getenv("KRX_PW", "").strip()
    if not krx_id or krx_id.startswith("여기에") or not krx_pw or krx_pw.startswith("여기에"):
        return "", ""
    return krx_id, krx_pw


def is_krx_configured() -> bool:
    krx_id, krx_pw = _get_krx_credentials()
    return bool(krx_id and krx_pw)


class _KrxSessionManager:
    """KRX 정보데이터시스템 로그인 세션과 ISIN·종목 조회 캐시를 관리한다."""

    def __init__(self):
        self._lock = threading.Lock()
        self._session: requests.Session | None = None
        self._login_ts: float = 0.0
        self._isin_cache: dict[str, dict] = {}
        self._result_cache: dict[str, tuple[float, dict]] = {}

    def _create_logged_in_session(self) -> tuple[requests.Session | None, str | None]:
        krx_id, krx_pw = _get_krx_credentials()
        if not krx_id or not krx_pw:
            return None, "KRX 로그인 정보(KRX_ID, KRX_PW)가 .env에 설정되지 않았습니다."

        sess = requests.Session()
        sess.headers.update({
            "User-Agent": USER_AGENT,
            "Referer": KRX_LOGIN_INIT_URL,
        })

        try:
            sess.get(KRX_LOGIN_INIT_URL, timeout=10)
            sess.get(KRX_LOGIN_JSP_URL, timeout=10)

            payload = {
                "mbrNm": "",
                "telNo": "",
                "di": "",
                "certType": "",
                "mbrId": krx_id,
                "pw": krx_pw,
            }
            res = sess.post(KRX_LOGIN_POST_URL, data=payload, timeout=10)
            data = res.json()
            err_code = data.get("_error_code", "")

            if err_code == "CD011":
                logger.info("[KRX]       중복 로그인(CD011) 감지 — 기존 세션 해제 후 재로그인")
                payload["skipDup"] = "Y"
                res = sess.post(KRX_LOGIN_POST_URL, data=payload, timeout=10)
                data = res.json()
                err_code = data.get("_error_code", "")

            if err_code != "CD001":
                err_msg = data.get("_error_message", "알 수 없는 로그인 오류")
                logger.error(f"[KRX]       KRX 로그인 실패 (code={err_code}, msg={err_msg})")
                return None, f"KRX 로그인에 실패했습니다. ({err_msg})"

            sess.headers["Referer"] = KRX_REFERER
            logger.info("[KRX]       KRX 정보데이터시스템 로그인 성공")
            return sess, None
        except requests.Timeout:
            logger.exception("[KRX]       KRX 로그인 타임아웃")
            return None, "KRX 로그인 응답 시간이 초과되었습니다."
        except Exception:
            logger.exception("[KRX]       KRX 로그인 중 예기치 않은 오류")
            return None, "KRX 로그인 처리 중 오류가 발생했습니다."

    def get_session(self, force_refresh: bool = False) -> tuple[requests.Session | None, str | None]:
        with self._lock:
            now = time.time()
            if (
                not force_refresh
                and self._session is not None
                and (now - self._login_ts) < SESSION_TTL_SECONDS
            ):
                return self._session, None

            sess, err = self._create_logged_in_session()
            if err or sess is None:
                self._session = None
                self._login_ts = 0.0
                return None, err

            self._session = sess
            self._login_ts = now
            return self._session, None

    def post_json(self, params: dict, label: str) -> tuple[dict | None, str | None]:
        """KRX getJsonData.cmd 호출. 세션 만료(LOGOUT/400) 시 자동 재로그인 후 1회 재시도."""
        for attempt in range(2):
            sess, err = self.get_session(force_refresh=(attempt == 1))
            if err or sess is None:
                return None, err
            try:
                res = sess.post(KRX_API_URL, data=params, timeout=10)
                if res.status_code == 400 or "LOGOUT" in res.text[:50]:
                    if attempt == 0:
                        logger.warning(f"[KRX]       {label} 세션 만료 감지 — 재로그인 후 재시도")
                        continue
                    return None, f"KRX {label} 조회 실패 (세션 인증 만료)"
                if res.status_code != 200:
                    return None, f"KRX {label} 조회 실패 (상태코드: {res.status_code})"
                return res.json(), None
            except requests.Timeout:
                logger.warning(f"[KRX]       {label} 요청 타임아웃")
                return None, f"KRX {label} 응답 시간이 초과되었습니다."
            except ValueError:
                if attempt == 0:
                    continue
                return None, f"KRX {label} 응답을 JSON으로 파싱하지 못했습니다."
            except requests.RequestException:
                logger.exception(f"[KRX]       {label} 네트워크 오류")
                return None, f"KRX {label} 서버에 연결하지 못했습니다."
        return None, f"KRX {label} 조회에 실패했습니다."

    def resolve_isin(self, stock_code: str) -> tuple[dict | None, str | None]:
        """6자리 종목코드를 KRX 표준코드(ISIN) 및 시장코드(STK/KSQ)로 변환한다."""
        code = str(stock_code).strip()
        if code in self._isin_cache:
            return self._isin_cache[code], None

        for bld in ("dbms/comm/finder/finder_stkisu", "dbms/comm/finder/finder_secuprodisu"):
            data, err = self.post_json(
                {
                    "bld": bld,
                    "locale": "ko_KR",
                    "mktsel": "ALL",
                    "searchText": code,
                },
                "종목코드 검색",
            )
            if err or not isinstance(data, dict):
                continue
            for row in data.get("block1", []):
                if str(row.get("short_code", "")).strip() == code:
                    info = {
                        "full_code": str(row.get("full_code", "")).strip(),
                        "short_code": code,
                        "name": str(row.get("codeName", "")).strip(),
                        "market_code": str(row.get("marketCode", "STK")).strip() or "STK",
                        "market_name": str(row.get("marketEngName", "KOSPI")).strip() or "KOSPI",
                    }
                    self._isin_cache[code] = info
                    return info, None

        return None, f"KRX에서 종목코드({code})의 표준코드(ISIN)를 찾지 못했습니다."

    def get_cached_result(self, code: str) -> dict | None:
        item = self._result_cache.get(code)
        if not item:
            return None
        ts, data = item
        if time.time() - ts < RESULT_CACHE_TTL_SECONDS:
            return data
        return None

    def set_cached_result(self, code: str, data: dict) -> None:
        self._result_cache[code] = (time.time(), data)


_krx_manager = _KrxSessionManager()


def _fetch_institutional_breakdown(isin: str, days: int) -> list[dict]:
    """MDCSTAT02301로 최근 N일(달력 기준) 기관 세부 투자주체별 순매수 수량·거래대금을 조회한다."""
    end_dt = datetime.now()
    strt_dt = end_dt - timedelta(days=days)
    data, err = _krx_manager.post_json(
        {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT02301",
            "locale": "ko_KR",
            "inqTpCd": "1",
            "trdVolVal": "2",
            "askBid": "3",
            "isuCd": isin,
            "strtDd": strt_dt.strftime("%Y%m%d"),
            "endDd": end_dt.strftime("%Y%m%d"),
            "share": "1",
            "money": "1",
        },
        f"기관별 세부 매동({days}일)",
    )
    if err or not isinstance(data, dict):
        return []

    rows = []
    for item in data.get("output", []):
        name = str(item.get("INVST_TP_NM", "")).strip()
        if name not in INSTITUTION_TRAITS:
            continue
        net_vol = _parse_int(item.get("NETBID_TRDVOL")) or 0
        net_val = _parse_int(item.get("NETBID_TRDVAL")) or 0
        trait = INSTITUTION_TRAITS[name]
        rows.append({
            "name": name,
            "net_vol": net_vol,
            "net_val": net_val,
            "role": trait["role"],
            "impact": trait["impact"],
        })

    # 순매수 거래대금 절대값이 큰 주체 순으로 정렬
    rows.sort(key=lambda r: abs(r["net_val"]), reverse=True)
    return rows


def _fetch_short_volume(isin: str) -> dict:
    """MDCSTAT30102로 최근 30일 개별종목 공매도 거래량 및 공매도 거래비중(%)을 조회한다."""
    end_dt = datetime.now()
    strt_dt = end_dt - timedelta(days=30)
    data, err = _krx_manager.post_json(
        {
            "bld": "dbms/MDC/STAT/srt/MDCSTAT30102",
            "locale": "ko_KR",
            "isuCd": isin,
            "strtDd": strt_dt.strftime("%Y%m%d"),
            "endDd": end_dt.strftime("%Y%m%d"),
            "share": "1",
            "money": "1",
        },
        "공매도 거래비중",
    )
    if err or not isinstance(data, dict):
        return {}

    raw_rows = data.get("OutBlock_1", [])
    daily = []
    for row in raw_rows:
        dt = str(row.get("TRD_DD", "")).replace("/", "-").strip()
        if not dt:
            continue
        daily.append({
            "date": dt,
            "short_vol": _parse_int(row.get("CVSRTSELL_TRDVOL")),
            "total_vol": _parse_int(row.get("ACC_TRDVOL")),
            "short_ratio_pct": _parse_float(row.get("TRDVOL_WT")),
            "short_val": _parse_int(row.get("CVSRTSELL_TRDVAL")),
        })

    if not daily:
        return {}

    latest = daily[0]
    ratios_5 = [d["short_ratio_pct"] for d in daily[:5] if d["short_ratio_pct"] is not None]
    avg_5d = round(sum(ratios_5) / len(ratios_5), 2) if ratios_5 else None

    latest_ratio = latest.get("short_ratio_pct")
    if latest_ratio is None:
        level, label, comment = "neutral", "데이터 없음", "최근 공매도 거래비중 수치가 집계되지 않았습니다."
    elif latest_ratio >= 15.0:
        level = "high"
        label = "경계 (단기 공매도 집중)"
        comment = (
            f"최근 공매도 거래비중이 {latest_ratio:.2f}%로 매우 높습니다(15%↑). "
            "단기 하락 베팅이 몰려 주가 상방 탄력이 강하게 눌릴 수 있어 추격 매수에 유의해야 합니다."
        )
    elif latest_ratio >= 10.0:
        level = "medium"
        label = "주의 (공매도 비중 확대)"
        comment = (
            f"최근 공매도 거래비중이 {latest_ratio:.2f}%로 높은 편입니다(10%↑). "
            "단기 하방 압력이 커질 수 있는 구간이므로 수급 반전 여부를 함께 확인하세요."
        )
    else:
        level = "low"
        label = "안정 (공매도 비중 낮음)"
        comment = (
            f"최근 공매도 거래비중이 {latest_ratio:.2f}%(5일 평균 {avg_5d if avg_5d is not None else '-'}%)로 "
            "낮은 수준입니다. 단기 공매도에 의한 인위적 하방 압력은 크지 않은 상태입니다."
        )

    return {
        "latest_date": latest["date"],
        "latest_ratio_pct": latest_ratio,
        "latest_vol": latest["short_vol"],
        "latest_val": latest["short_val"],
        "avg_5d_ratio_pct": avg_5d,
        "level": level,
        "label": label,
        "comment": comment,
        "daily": daily[:5],
    }


def _fetch_short_balance(isin: str) -> dict:
    """MDCSTAT30502로 최근 45일 개별종목 공매도 순보유잔고 및 잔고비중(%)을 조회한다. (T+2 공시)"""
    end_dt = datetime.now()
    strt_dt = end_dt - timedelta(days=45)
    data, err = _krx_manager.post_json(
        {
            "bld": "dbms/MDC/STAT/srt/MDCSTAT30502",
            "locale": "ko_KR",
            "isuCd": isin,
            "strtDd": strt_dt.strftime("%Y%m%d"),
            "endDd": end_dt.strftime("%Y%m%d"),
            "share": "1",
            "money": "1",
        },
        "공매도 잔고비중",
    )
    if err or not isinstance(data, dict):
        return {}

    raw_rows = data.get("OutBlock_1", [])
    daily = []
    for row in raw_rows:
        dt = str(row.get("RPT_DUTY_OCCR_DD", "")).replace("/", "-").strip()
        if not dt:
            continue
        daily.append({
            "date": dt,
            "balance_qty": _parse_int(row.get("BAL_QTY")),
            "balance_amt": _parse_int(row.get("BAL_AMT")),
            "balance_ratio_pct": _parse_float(row.get("BAL_RTO")),
            "listed_shares": _parse_int(row.get("LIST_SHRS")),
        })

    if not daily:
        return {}

    latest = daily[0]
    ref_idx = min(4, len(daily) - 1)
    prev = daily[ref_idx]

    qty_change = (
        latest["balance_qty"] - prev["balance_qty"]
        if (latest["balance_qty"] is not None and prev["balance_qty"] is not None)
        else None
    )
    ratio_change = (
        round(latest["balance_ratio_pct"] - prev["balance_ratio_pct"], 2)
        if (latest["balance_ratio_pct"] is not None and prev["balance_ratio_pct"] is not None)
        else None
    )

    bal_ratio = latest.get("balance_ratio_pct")
    if bal_ratio is None:
        level, label, comment = "neutral", "데이터 없음", "공매도 잔고 데이터가 집계되지 않았습니다."
    elif bal_ratio >= 3.0 and (qty_change is None or qty_change >= 0):
        level = "high"
        label = "경계 (중기 잔고 부담 높음)"
        comment = (
            f"상장주식 대비 공매도 잔고비중이 {bal_ratio:.2f}%로 높고 누적되는 흐름입니다(3%↑). "
            "중기적 하락 베팅 물량이 쌓여 있어 반등 시 매도 압력이 이어질 수 있습니다."
        )
    elif bal_ratio >= 1.5 and qty_change is not None and qty_change < 0:
        level = "positive"
        label = "숏커버링 관찰 (잔고 감소)"
        comment = (
            f"공매도 잔고비중({bal_ratio:.2f}%)이 최근 5거래일간 {abs(qty_change):,}주 줄어들고 있습니다. "
            "공매도 세력이 주식을 되사서 갚는(숏커버링) 흐름이 이어지면 주가 반등 탄력이 커질 수 있습니다."
        )
    elif bal_ratio >= 1.5:
        level = "medium"
        label = "주의 (잔고 추이 관찰)"
        comment = (
            f"공매도 잔고비중이 {bal_ratio:.2f}%로 중간 수준입니다. "
            "잔고가 3% 이상으로 추가 확대되는지, 줄어드는지 추세를 지켜볼 구간입니다."
        )
    else:
        level = "low"
        label = "안정 (잔고 부담 미미)"
        comment = (
            f"공매도 잔고비중이 {bal_ratio:.2f}%({latest['date']} 기준, T+2 공시)로 매우 낮습니다. "
            "중기 공매도 잔고로 인한 주가 압박 우려는 크지 않은 수준입니다."
        )

    return {
        "latest_date": latest["date"],
        "balance_qty": latest["balance_qty"],
        "balance_amt": latest["balance_amt"],
        "balance_ratio_pct": bal_ratio,
        "qty_change_5d": qty_change,
        "ratio_change_5d_pctp": ratio_change,
        "level": level,
        "label": label,
        "comment": comment,
        "daily": daily[:5],
    }


def _fetch_market_program(market_code: str, market_name: str) -> dict:
    """MDCSTAT02601로 소속 시장(KOSPI/KOSDAQ)의 최근 5거래일 프로그램 차익/비차익 순매수를 조회한다."""
    mkt_id = market_code if market_code in ("STK", "KSQ") else "STK"
    end_dt = datetime.now()
    strt_dt = end_dt - timedelta(days=7)
    data, err = _krx_manager.post_json(
        {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT02601",
            "locale": "ko_KR",
            "mktId": mkt_id,
            "strtDd": strt_dt.strftime("%Y%m%d"),
            "endDd": end_dt.strftime("%Y%m%d"),
            "share": "1",
            "money": "1",
        },
        f"{market_name} 프로그램매매",
    )
    if err or not isinstance(data, dict):
        return {}

    out = data.get("output", [])
    if not out:
        return {}

    arb_val = 0
    non_arb_val = 0
    total_val = 0
    arb_vol = 0
    non_arb_vol = 0
    for row in out:
        tp = str(row.get("ITM_TP_NM", "")).strip()
        net_val = _parse_int(row.get("NETBID_TRDVAL")) or 0
        net_vol = _parse_int(row.get("NETBID_TRDVOL")) or 0
        if tp == "차익":
            arb_val = net_val
            arb_vol = net_vol
        elif tp == "비차익":
            non_arb_val = net_val
            non_arb_vol = net_vol
        elif tp == "전체":
            total_val = net_val

    if total_val == 0:
        total_val = arb_val + non_arb_val

    if non_arb_val > 0 and total_val > 0:
        level = "positive"
        label = "프로그램 매수 우위 (시장 수급 우호)"
        comment = (
            f"최근 1주일 {market_name} 시장에서 비차익 프로그램이 {_format_eok(non_arb_val)} 순매수 유입 중입니다. "
            "외국인·기관의 바스켓(패시브) 매수세가 시장 전반과 대형주 주가를 밀어 올리는 우호적 환경입니다."
        )
    elif non_arb_val < 0 and total_val < 0:
        level = "negative"
        label = "프로그램 매도 우위 (기계적 매도 주의)"
        comment = (
            f"최근 1주일 {market_name} 시장에서 비차익 프로그램이 {_format_eok(non_arb_val)} 순매도 출회 중입니다. "
            "종목 자체 악재가 없어도 지수 연동 바스켓 매도로 단기 하방 압력을 받을 수 있습니다."
        )
    else:
        level = "neutral"
        label = "프로그램 수급 혼조 (중립)"
        comment = (
            f"최근 1주일 {market_name} 시장 프로그램 수급은 차익({_format_eok(arb_val)})과 "
            f"비차익({_format_eok(non_arb_val)})이 엇갈리는 중립 흐름입니다."
        )

    return {
        "market_name": market_name,
        "period_label": "최근 1주 누적",
        "arbitrage_net_val": arb_val,
        "arbitrage_net_vol": arb_vol,
        "non_arbitrage_net_val": non_arb_val,
        "non_arbitrage_net_vol": non_arb_vol,
        "total_net_val": total_val,
        "level": level,
        "label": label,
        "comment": comment,
    }


def _build_impact_summary(inst_5d: list[dict], inst_20d: list[dict], short_vol: dict, short_bal: dict, program: dict) -> dict:
    """KRX 수급·공매도·프로그램 데이터를 종합해 주린이 눈높이 주가 영향 핵심 요약을 만든다."""
    positive = []
    negative = []

    inst_map_20 = {r["name"]: r for r in inst_20d}
    inst_map_5 = {r["name"]: r for r in inst_5d}

    # 1. 연기금 & 투신 (장기/질 좋은 기관 수급)
    pension_20 = inst_map_20.get("연기금 등", {}).get("net_val", 0)
    pension_5 = inst_map_5.get("연기금 등", {}).get("net_val", 0)
    trust_20 = inst_map_20.get("투신", {}).get("net_val", 0)
    fin_inv_5 = inst_map_5.get("금융투자", {}).get("net_val", 0)

    if pension_20 > 0 and pension_5 >= 0:
        positive.append(
            f"장기 자금인 '연기금'이 최근 1개월간 {_format_eok(pension_20)} 순매수하며 주가 하방을 지지하고 있습니다."
        )
    elif pension_20 < 0 and pension_5 < 0:
        negative.append(
            f"장기 자금인 '연기금'이 최근 1개월간 {_format_eok(pension_20)} 순매도하며 비중을 줄이는 흐름입니다."
        )

    if trust_20 > 0:
        positive.append(
            f"자산운용사 펀드 자금('투신')이 최근 1개월간 {_format_eok(trust_20)} 순매수 유입 중입니다."
        )
    elif trust_20 < 0:
        negative.append(
            f"'투신(펀드)'에서 최근 1개월간 {_format_eok(trust_20)} 매물이 나오고 있습니다."
        )

    if abs(fin_inv_5) > 0 and fin_inv_5 > 0 and pension_5 <= 0 and trust_20 <= 0:
        negative.append(
            f"최근 기관 매수가 단기 성향인 '금융투자'({_format_eok(fin_inv_5)}) 위주라면 만기일·차익실현 시 되돌림 변동성에 유의해야 합니다."
        )

    # 2. 공매도 거래비중 & 잔고
    if short_vol.get("level") in ("high", "medium"):
        negative.append(short_vol["comment"])
    elif short_vol.get("level") == "low":
        positive.append(
            f"최근 공매도 거래비중이 {short_vol.get('latest_ratio_pct')}%로 낮아 단기 공매도 압박이 크지 않습니다."
        )

    if short_bal.get("level") == "high":
        negative.append(short_bal["comment"])
    elif short_bal.get("level") == "positive":
        positive.append(short_bal["comment"])
    elif short_bal.get("level") == "low":
        positive.append(
            f"공매도 잔고비중이 {short_bal.get('balance_ratio_pct')}%로 낮아 중기 공매도 부담이 미미합니다."
        )

    # 3. 시장 프로그램 수급
    if program.get("level") == "positive":
        positive.append(
            f"소속 시장({program.get('market_name')}) 비차익 프로그램 순매수({_format_eok(program.get('non_arbitrage_net_val'))})가 주가에 우호적입니다."
        )
    elif program.get("level") == "negative":
        negative.append(
            f"소속 시장({program.get('market_name')}) 비차익 프로그램 순매도({_format_eok(program.get('non_arbitrage_net_val'))})로 단기 지수 하방 압력이 있습니다."
        )

    if not positive:
        positive.append("KRX 세부 수급·공매도 기준으로 뚜렷한 장기 기관 집중 매수 신호는 아직 약합니다.")
    if not negative:
        negative.append("KRX 세부 수급·공매도 기준으로 두드러진 공매도 과열이나 연기금 이탈 경고는 보이지 않습니다.")

    return {"positive": positive, "negative": negative}


def fetch_krx_deep_supply(stock_code: str, force_refresh: bool = False) -> tuple[dict, str | None]:
    """
    KRX 정보데이터시스템 로그인 세션을 통해 국내 종목의
    1) 기관별 세부 매동 (단기 1주 / 중기 1개월)
    2) 공매도 거래량·거래비중(%) 추이
    3) 공매도 순보유잔고·잔고비중(%) 추이
    4) 소속 시장 프로그램매매(차익·비차익) 순매수
    5) 주가 영향 자동 해석 + 확장 지표(대차잔고·신용비율·개별 프로그램) 해설 가이드
    를 통합 수집해 반환한다.
    """
    code = str(stock_code).strip()
    if not is_krx_configured():
        return {
            "available": False,
            "reason": "KRX 로그인 정보(KRX_ID, KRX_PW)가 .env에 설정되지 않았습니다.",
            "extended_guides": EXTENDED_MARKET_GUIDES,
        }, None

    if not force_refresh:
        cached = _krx_manager.get_cached_result(code)
        if cached is not None:
            logger.info(f"[KRX]       캐시된 KRX 심층 수급 데이터 반환 (code={code})")
            return cached, None

    logger.info(f"[KRX]       KRX 심층 수급·공매도 데이터 수집 시작 (code={code})")
    isin_info, err = _krx_manager.resolve_isin(code)
    if err or not isin_info:
        logger.warning(f"[KRX]       ISIN 조회 실패 (code={code}): {err}")
        return {
            "available": False,
            "reason": err or "KRX 종목 정보를 찾지 못했습니다.",
            "extended_guides": EXTENDED_MARKET_GUIDES,
        }, err

    isin = isin_info["full_code"]
    market_code = isin_info["market_code"]
    market_name = isin_info["market_name"]

    inst_short = _fetch_institutional_breakdown(isin, days=10)
    inst_mid = _fetch_institutional_breakdown(isin, days=30)
    short_vol = _fetch_short_volume(isin)
    short_bal = _fetch_short_balance(isin)
    program = _fetch_market_program(market_code, market_name)

    impact_summary = _build_impact_summary(inst_short, inst_mid, short_vol, short_bal, program)

    result = {
        "available": True,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "isin": isin,
        "market_name": market_name,
        "institutional_short": inst_short,
        "institutional_mid": inst_mid,
        "short_volume": short_vol,
        "short_balance": short_bal,
        "market_program": program,
        "impact_summary": impact_summary,
        "extended_guides": EXTENDED_MARKET_GUIDES,
    }

    _krx_manager.set_cached_result(code, result)
    logger.info(
        f"[KRX]       KRX 심층 수급 수집 완료 (code={code}, inst={len(inst_mid)}주체, "
        f"short_ratio={short_vol.get('latest_ratio_pct')}%, short_bal={short_bal.get('balance_ratio_pct')}%)"
    )
    return result, None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    import json
    res, err = fetch_krx_deep_supply("000660", force_refresh=True)
    logger.info(f"[TEST]      KRX 테스트 완료: available={res.get('available')}, err={err}")
    logger.info(json.dumps({
        "market_name": res.get("market_name"),
        "top_inst_mid": [(r["name"], r["net_val"]) for r in (res.get("institutional_mid") or [])[:4]],
        "short_volume": {k: res.get("short_volume", {}).get(k) for k in ("latest_date", "latest_ratio_pct", "label")},
        "short_balance": {k: res.get("short_balance", {}).get(k) for k in ("latest_date", "balance_ratio_pct", "label")},
        "market_program": {k: res.get("market_program", {}).get(k) for k in ("market_name", "total_net_val", "label")},
    }, ensure_ascii=False))
