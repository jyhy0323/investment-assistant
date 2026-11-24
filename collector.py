import logging
import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("StockApp")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _request_naver_json(url: str, label: str) -> tuple[dict | None, str | None]:
    """네이버 금융 API를 호출하고 409(일시 차단/충돌) 시 짧은 대기 후 1회 재시도한다."""
    for attempt in range(2):
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 409 and attempt == 0:
                logger.warning(f"[NAVER]    {label} 일시 409 응답 — 0.5초 후 재시도")
                time.sleep(0.5)
                continue
            if res.status_code == 404:
                return None, f"네이버 금융에서 해당 종목을 찾을 수 없습니다. (404)"
            if res.status_code != 200:
                return None, f"네이버 금융 {label} 접근 실패 (상태코드: {res.status_code})"
            return res.json(), None
        except requests.Timeout:
            logger.exception(f"[ERROR]    {label} 네트워크 타임아웃")
            return None, f"네이버 금융 {label} 응답 시간이 초과되었습니다. (네트워크 타임아웃)"
        except ValueError:
            logger.exception(f"[ERROR]    {label} JSON 변환 실패")
            return None, f"네이버 금융 {label} 응답을 JSON으로 변환하는 데 실패했습니다."
        except requests.RequestException:
            logger.exception(f"[ERROR]    {label} 연결 실패")
            return None, f"네이버 금융 {label} 서버에 연결하지 못했습니다."
    return None, f"네이버 금융 {label} 접근에 실패했습니다."


def validate_code(code: str) -> str | None:
    """종목코드가 6자리 숫자인지 검증하고, 오류 시 사용자 친화적 메시지를 반환한다."""
    if not code or not str(code).strip():
        return "종목코드가 입력되지 않았습니다."
    cleaned = str(code).strip()
    if not re.fullmatch(r"\d{6}", cleaned):
        return "종목코드는 6자리 숫자여야 합니다. (예: 000660)"
    return None


def clean_number(value: str | int | float | None, as_float: bool = False) -> int | float | None:
    """콤마(,)와 단위(배, %, 원 등)를 제거해 순수 숫자(int 또는 float)로 변환한다."""
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").replace("배", "").replace("원", "").strip()
    if not text or text == "-" or text.upper() == "N/A":
        return None
    try:
        return float(text) if as_float else int(float(text))
    except ValueError:
        return None


def parse_korean_amount(value: str | None) -> int | None:
    """'891조 9,312억' 같은 한글 금액 단위를 순수 원 단위 정수(int)로 변환한다."""
    if not value:
        return None
    text = str(value).replace(",", "").replace("원", "").strip()
    if not text or text == "-":
        return None

    # 조, 억, 만 단위가 포함된 경우 각각 파싱하여 합산
    if any(unit in text for unit in ("조", "억", "만")):
        total = 0
        matched = False
        for unit, multiplier in (("조", 10**12), ("억", 10**8), ("만", 10**4)):
            m = re.search(rf"([+-]?\d+(?:\.\d+)?)\s*{unit}", text)
            if m:
                total += int(float(m.group(1)) * multiplier)
                matched = True
        return total if matched else None

    return clean_number(text, as_float=False)


def fetch_basic_info(code: str) -> dict:
    """
    Step 12 (1차): 네이버 금융 basic API에 User-Agent 헤더를 담아 요청하고
    정식 종목명(name)과 상단 시세(current_price, change_rate)를 파싱한다.
    """
    result = {
        "code": str(code).strip() if code else "",
        "name": None,
        "snapshot": {
            "current_price": None,
            "change_rate": None,
        },
        "financials": [],
        "news": [],
        "errors": [],
    }

    validation_error = validate_code(result["code"])
    if validation_error:
        result["errors"].append(validation_error)
        return result

    url = f"https://m.stock.naver.com/api/stock/{result['code']}/basic"
    logger.info(f"[NAVER]    네이버 금융 접근 시작 (User-Agent 적용) url={url}")

    data, err = _request_naver_json(url, "기본 시세")
    if err:
        logger.error(f"[ERROR]    {err}")
        result["errors"].append(err)
        return result

    stock_name = data.get("stockName")
    if not stock_name:
        msg = "정식 종목명을 파싱하지 못했습니다. (네이버 데이터 구조 변경 가능성)"
        logger.error(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result

    current_price = clean_number(data.get("closePrice"), as_float=False)
    change_rate = clean_number(data.get("fluctuationsRatio"), as_float=True)

    result["name"] = stock_name
    result["snapshot"]["current_price"] = current_price
    result["snapshot"]["change_rate"] = change_rate

    logger.info(f"[PARSE]    스냅샷 기본 시세 파싱 완료 (name={stock_name}, price={current_price})")
    return result


def fetch_integration_info(code: str, result: dict) -> dict:
    """
    Step 13 (2차): 네이버 금융 integration API에서 투자정보(시가총액, PER, PBR)를
    수집하고 콤마와 한글/기호 단위를 제거한 순수 숫자로 정제하여 snapshot에 추가한다.
    """
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    logger.info(f"[NAVER]    투자정보(PER/PBR/시총) 접근 시작 url={url}")

    data, err = _request_naver_json(url, "투자정보")
    if err:
        logger.error(f"[ERROR]    {err}")
        result["errors"].append(err)
        return result

    total_infos = data.get("totalInfos")
    if not isinstance(total_infos, list):
        msg = "투자정보(totalInfos) 데이터 구조가 예상과 다릅니다."
        logger.error(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result

    info_map = {item.get("code"): item.get("value") for item in total_infos if isinstance(item, dict)}

    result["snapshot"]["market_cap"] = parse_korean_amount(info_map.get("marketValue"))
    result["snapshot"]["per"] = clean_number(info_map.get("per"), as_float=True)
    result["snapshot"]["pbr"] = clean_number(info_map.get("pbr"), as_float=True)
    result["snapshot"]["foreign_rate"] = clean_number(info_map.get("foreignRate"), as_float=True)

    logger.info(
        f"[PARSE]    투자정보 파싱 완료 (market_cap={result['snapshot']['market_cap']}, "
        f"per={result['snapshot']['per']}, pbr={result['snapshot']['pbr']}, "
        f"foreign_rate={result['snapshot']['foreign_rate']})"
    )
    return result


def fetch_financials(code: str, result: dict) -> dict:
    """
    Step 14 (3차): 네이버 금융 finance/annual API에서 연간 기업실적분석(매출액, 영업이익, ROE)을
    파싱하고 (E) 추정치 여부에 따라 is_consensus 신호등(True/False)을 달아 financials에 추가한다.
    """
    url = f"https://m.stock.naver.com/api/stock/{code}/finance/annual"
    logger.info(f"[NAVER]    기업실적분석 접근 시작 url={url}")

    data, err = _request_naver_json(url, "기업실적")
    if err:
        logger.error(f"[ERROR]    {err}")
        result["errors"].append(err)
        return result

    finance_info = data.get("financeInfo")
    if not isinstance(finance_info, dict):
        msg = "기업실적(financeInfo) 데이터 구조가 예상과 다릅니다."
        logger.error(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result

    tr_titles = finance_info.get("trTitleList", [])
    row_list = finance_info.get("rowList", [])

    # 필요한 행(매출액, 영업이익, ROE)만 빠르게 조회할 수 있도록 매핑
    row_map = {
        row.get("title"): row.get("columns", {})
        for row in row_list
        if isinstance(row, dict)
    }

    revenue_cols = row_map.get("매출액", {})
    op_income_cols = row_map.get("영업이익", {})
    roe_cols = row_map.get("ROE", {})

    financials = []
    for title_item in tr_titles:
        key = title_item.get("key")
        raw_title = str(title_item.get("title", "")).strip()
        # 끝의 마침표나 (E) 표기를 정리하여 "2024.12" 형태로 통일
        period = raw_title.replace("(E)", "").strip().rstrip(".")
        is_consensus = (title_item.get("isConsensus") == "Y") or ("(E)" in raw_title)

        rev_eok = clean_number(revenue_cols.get(key, {}).get("value"), as_float=False)
        op_eok = clean_number(op_income_cols.get(key, {}).get("value"), as_float=False)
        roe_val = clean_number(roe_cols.get(key, {}).get("value"), as_float=True)

        # 네이버 실적 표의 매출액/영업이익은 '억원' 단위이므로 원 단위로 환산 (1억 = 10^8)
        revenue = rev_eok * 10**8 if rev_eok is not None else None
        operating_income = op_eok * 10**8 if op_eok is not None else None

        financials.append({
            "period": period,
            "period_type": "annual",
            "is_consensus": is_consensus,
            "revenue": revenue,
            "operating_income": operating_income,
            "roe": roe_val,
        })

    result["financials"] = financials
    logger.info(f"[PARSE]    기업실적분석 파싱 완료 (기간 {len(financials)}개)")
    return result


def fetch_serper_news(stock_name: str | None, result: dict) -> dict:
    """
    Step 15 (4차): 네이버에서 파싱한 정식 종목명으로 Serper News API를 호출해
    최신 관련 뉴스 5개를 수집한다. (API Key 미설정/실패 시 전체를 멈추지 않고 errors에 기록)
    """
    if not stock_name:
        msg = "정식 종목명이 없어 뉴스 검색을 건너뜁니다."
        logger.warning(f"[SERPER]   {msg}")
        result["errors"].append(msg)
        return result

    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key or api_key.startswith("여기에"):
        msg = "Serper API Key가 설정되지 않았습니다. (.env 파일을 확인하세요)"
        logger.error(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result

    url = "https://google.serper.dev/news"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    query = f"{stock_name} 주가"
    payload = {
        "q": query,
        "gl": "kr",
        "hl": "ko",
        "num": 10,
    }

    logger.info(f"[SERPER]   Serper News API 호출 시작 (query={query})")

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=7)
        if res.status_code != 200:
            msg = f"Serper News API 호출 실패 (상태코드: {res.status_code})"
            logger.error(f"[ERROR]    {msg}")
            result["errors"].append(msg)
            return result
        data = res.json()
    except requests.Timeout:
        msg = "Serper News API 응답 시간이 초과되었습니다. (네트워크 타임아웃)"
        logger.exception(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result
    except ValueError:
        msg = "Serper News API 응답을 JSON으로 변환하는 데 실패했습니다."
        logger.exception(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result
    except requests.RequestException:
        msg = "Serper News API 서버에 연결하지 못했습니다."
        logger.exception(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        return result

    raw_news = data.get("news", [])
    excluded_domains = ("story.pay.naver.com", "contents.premium.naver.com")
    news_list = []
    for item in raw_news:
        if not isinstance(item, dict):
            continue
        link = item.get("link", "")
        if any(domain in link for domain in excluded_domains):
            continue
        news_list.append({
            "title": item.get("title", ""),
            "url": link,
            "description": item.get("snippet", "") or item.get("source", ""),
            "published": item.get("date", ""),
        })
        if len(news_list) >= 5:
            break

    result["news"] = news_list
    logger.info(f"[SERPER]   뉴스 수집 완료 (수집 기사={len(news_list)}건)")
    return result


def _calc_streak(values: list[int | None]) -> int:
    """최신일부터 연속 순매수(+N) 또는 연속 순매도(-N) 거래일 수를 계산한다."""
    if not values or values[0] is None or values[0] == 0:
        return 0
    direction = 1 if values[0] > 0 else -1
    count = 0
    for v in values:
        if v is None or v == 0:
            break
        if (v > 0 and direction > 0) or (v < 0 and direction < 0):
            count += 1
        else:
            break
    return count * direction


def fetch_supply_demand(code: str, result: dict) -> dict:
    """
    네이버 금융 trend API(최근 20거래일)에서 개인·외국인·기관 일별 순매수 및
    외국인 지분율 추이를 수집하고 단기(5일)/중기(20일) 요약과 긍정·부정 신호를 생성한다.
    """
    url = f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize=20"
    logger.info(f"[NAVER]    수급 동향(20일) 접근 시작 url={url}")

    data, err = _request_naver_json(url, "수급 동향")
    if err:
        logger.error(f"[ERROR]    {err}")
        result["errors"].append(err)
        result["supply_demand"] = {}
        return result

    if not isinstance(data, list) or len(data) == 0:
        msg = "수급 동향 데이터가 비어 있거나 구조가 예상과 다릅니다."
        logger.warning(f"[ERROR]    {msg}")
        result["errors"].append(msg)
        result["supply_demand"] = {}
        return result

    daily_all = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_date = str(item.get("bizdate", ""))
        date_fmt = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else raw_date
        daily_all.append({
            "date": date_fmt,
            "foreigner_net": clean_number(item.get("foreignerPureBuyQuant"), as_float=False),
            "organ_net": clean_number(item.get("organPureBuyQuant"), as_float=False),
            "individual_net": clean_number(item.get("individualPureBuyQuant"), as_float=False),
            "foreign_ratio": clean_number(item.get("foreignerHoldRatio"), as_float=True),
            "close": clean_number(item.get("closePrice"), as_float=False),
        })

    def sum_net(rows: list[dict], key: str) -> int:
        return sum(r[key] for r in rows if r.get(key) is not None)

    rows_5 = daily_all[:5]
    rows_20 = daily_all[:20]

    days_5 = {
        "foreigner": sum_net(rows_5, "foreigner_net"),
        "organ": sum_net(rows_5, "organ_net"),
        "individual": sum_net(rows_5, "individual_net"),
    }
    days_20 = {
        "foreigner": sum_net(rows_20, "foreigner_net"),
        "organ": sum_net(rows_20, "organ_net"),
        "individual": sum_net(rows_20, "individual_net"),
    }

    streaks = {
        "foreigner": _calc_streak([r["foreigner_net"] for r in daily_all]),
        "organ": _calc_streak([r["organ_net"] for r in daily_all]),
        "individual": _calc_streak([r["individual_net"] for r in daily_all]),
    }

    latest_fr = daily_all[0]["foreign_ratio"] if daily_all else None
    oldest_fr = daily_all[-1]["foreign_ratio"] if daily_all else None
    fr_change_20d = (
        round(latest_fr - oldest_fr, 2)
        if (latest_fr is not None and oldest_fr is not None)
        else None
    )

    positive = []
    negative = []

    # 단기(5일) 수급 패턴
    if days_5["foreigner"] > 0 and days_5["organ"] > 0:
        positive.append("단기(5일) 외국인과 기관이 동시에 순매수(쌍끌이) 유입 중입니다.")
    elif days_5["foreigner"] < 0 and days_5["organ"] < 0 and days_5["individual"] > 0:
        negative.append("단기(5일) 외국인·기관이 동시 매도하고 개인이 물량을 받아내는 구간입니다.")

    # 중기(20일) 수급 패턴
    if days_20["foreigner"] > 0 and days_20["organ"] > 0:
        positive.append("중기(20일) 외국인과 기관의 동반 매수세가 누적되고 있습니다.")
    elif days_20["foreigner"] < 0 and days_20["organ"] < 0 and days_20["individual"] > 0:
        negative.append("중기(20일) 외국인·기관 이탈이 이어지며 개인 순매수가 누적된 상태입니다.")

    # 연속 매매 추세
    if streaks["foreigner"] >= 3:
        positive.append(f"외국인이 최근 {streaks['foreigner']}거래일 연속 순매수를 이어가고 있습니다.")
    elif streaks["foreigner"] <= -3:
        negative.append(f"외국인이 최근 {abs(streaks['foreigner'])}거래일 연속 순매도 중입니다.")

    if streaks["organ"] >= 3:
        positive.append(f"기관이 최근 {streaks['organ']}거래일 연속 순매수를 이어가고 있습니다.")
    elif streaks["organ"] <= -3:
        negative.append(f"기관이 최근 {abs(streaks['organ'])}거래일 연속 순매도 중입니다.")

    # 외국인 지분율 변화 (20일)
    if fr_change_20d is not None:
        if fr_change_20d >= 0.2:
            positive.append(f"최근 20거래일간 외국인 지분율이 +{fr_change_20d:.2f}%p 상승했습니다.")
        elif fr_change_20d <= -0.2:
            negative.append(f"최근 20거래일간 외국인 지분율이 {fr_change_20d:.2f}%p 하락했습니다.")

    if not positive:
        positive.append("뚜렷한 단기/중기 메이저(외인·기관) 매수 집중 신호는 아직 약한 편입니다.")
    if not negative:
        negative.append("현재 수급상 두드러진 메이저 이탈이나 개인 쏠림 경고 신호는 보이지 않습니다.")

    result["supply_demand"] = {
        "days_5": days_5,
        "days_20": days_20,
        "streaks": streaks,
        "foreign_ratio_latest": latest_fr,
        "foreign_ratio_20d_ago": oldest_fr,
        "foreign_ratio_change_20d": fr_change_20d,
        "signals": {
            "positive": positive,
            "negative": negative,
        },
        "daily": daily_all[:5],
    }

    logger.info(
        f"[PARSE]    수급 동향 파싱 완료 (5일 외인={days_5['foreigner']}, 기관={days_5['organ']}, "
        f"개인={days_5['individual']}, 외인지분변화={fr_change_20d})"
    )
    return result


def collect_all(code: str) -> dict:
    """종목코드를 받아 시세, 투자정보, 기업실적, 수급 동향, Serper 뉴스를 순차 수집한다."""
    result = fetch_basic_info(code)
    if not result.get("name"):
        return result

    result = fetch_integration_info(result["code"], result)
    result = fetch_financials(result["code"], result)
    result = fetch_supply_demand(result["code"], result)
    result = fetch_serper_news(result["name"], result)
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    import json
    sample = collect_all("000660")
    logger.info(f"[TEST]     테스트 결과: {json.dumps(sample, ensure_ascii=False)}")
