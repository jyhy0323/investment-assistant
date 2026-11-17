import os
import re
import sys
import requests
from datetime import datetime

# Windows 콘솔 한글/특수문자 인코딩 설정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCKS_FILE = os.path.join(BASE_DIR, "stocks.txt")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def extract_stock_codes_from_file(file_path: str) -> list[str]:
    """메모장 내용 중 URL이나 텍스트에서 6자리 종목 코드들을 중복 없이 추출."""
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    codes = []
    # 네이버 금융 URL 패턴: /stock/000660 또는 단독 6자리 숫자
    url_matches = re.findall(r"/stock/(\d{6})", content)
    for c in url_matches:
        if c not in codes:
            codes.append(c)

    # URL 외에 일반 6자리 숫자 라인 탐색
    for line in content.splitlines():
        clean = line.split("#")[0].strip()
        match = re.search(r"\b(\d{6})\b", clean)
        if match:
            code = match.group(1)
            if code not in codes:
                codes.append(code)

    return codes

def fetch_json(url: str) -> dict | None:
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"  [API 오류] {url} : {e}")
    return None

def analyze_stock(code: str):
    """1) 시세, 2) 투자정보, 3) 기업실적분석 3개 구역 통합 분석."""
    # 1. API 호출
    basic = fetch_json(f"https://m.stock.naver.com/api/stock/{code}/basic")
    integ = fetch_json(f"https://m.stock.naver.com/api/stock/{code}/integration")
    annual = fetch_json(f"https://m.stock.naver.com/api/stock/{code}/finance/annual")

    if not basic:
        print(f"❌ [{code}] 종목 기본 정보를 불러올 수 없습니다.\n")
        return

    name = basic.get("stockName", "알 수 없음")
    close_price = basic.get("closePrice", "0")
    diff_price = basic.get("compareToPreviousClosePrice", "0")
    ratio = basic.get("fluctuationsRatio", "0.0")

    try:
        f_ratio = float(ratio)
        ratio_symbol = f"+{f_ratio}% ▲" if f_ratio > 0 else (f"{f_ratio}% ▼" if f_ratio < 0 else f"{f_ratio}% -")
    except Exception:
        ratio_symbol = f"{ratio}%"

    print("=" * 75)
    print(f"📌 [{name} ({code})] 네이버 금융 3대 핵심 지표 분석")
    print("=" * 75)

    # 1구역: 시세 정보
    print("\n[ 1. 왼쪽 상단 시세 ]")
    print(f"  - 현재가      : {close_price}원 ({diff_price}원, {ratio_symbol})")

    # totalInfos 매핑
    info_map = {}
    if integ and "totalInfos" in integ:
        for item in integ["totalInfos"]:
            info_map[item.get("code")] = item.get("value", "-")

    open_p = info_map.get("openPrice", "-")
    high_p = info_map.get("highPrice", "-")
    low_p = info_map.get("lowPrice", "-")
    vol = info_map.get("accumulatedTradingVolume", "-")
    val = info_map.get("accumulatedTradingValue", "-")

    print(f"  - 오늘 시가   : {open_p}원")
    print(f"  - 오늘 고/저가: 고가 {high_p}원 / 저가 {low_p}원")
    print(f"  - 거래량/대금 : {vol}주 / {val}")

    # 2구역: 투자 정보 (가치 & 수급)
    print("\n[ 2. 시세 밑 투자정보 ]")
    market_cap = info_map.get("marketValue", "-")
    h_52 = info_map.get("highPriceOf52Weeks", "-")
    l_52 = info_map.get("lowPriceOf52Weeks", "-")
    f_rate = info_map.get("foreignRate", "-")
    per = info_map.get("per", "-")
    cns_per = info_map.get("cnsPer", "-")
    pbr = info_map.get("pbr", "-")
    div_yield = info_map.get("dividendYieldRatio", "-")

    print(f"  - 시가총액    : {market_cap}")
    print(f"  - 52주 최고/저: 최고 {h_52}원 / 최저 {l_52}원")
    print(f"  - 외인소진율  : {f_rate}")
    print(f"  - PER / 추정PER: {per} / 추정 {cns_per}")
    print(f"  - PBR         : {pbr}")
    print(f"  - 배당수익률  : {div_yield}")

    # 3구역: 기업실적분석 (재무제표)
    print("\n[ 3. 아래쪽 기업실적분석 (연간 실적 추이) ]")
    if annual and "financeInfo" in annual:
        f_info = annual["financeInfo"]
        tr_titles = f_info.get("trTitleList", [])
        period_names = [t.get("title") for t in tr_titles]
        period_keys = [t.get("key") for t in tr_titles]

        # 주요 타겟 항목 필터링
        target_rows = ["매출액", "영업이익", "당기순이익", "영업이익률", "ROE", "부채비율", "EPS", "PER"]
        
        # 테이블 헤더
        header_str = f"  {'항목':<10}"
        for p in period_names:
            header_str += f" | {p:>12}"
        print(header_str)
        print("  " + "-" * (12 + len(period_names) * 15))

        for row in f_info.get("rowList", []):
            title = row.get("title")
            if title in target_rows:
                row_str = f"  {title:<10}"
                col_data = row.get("columns", {})
                for k in period_keys:
                    val = col_data.get(k, {}).get("value", "-")
                    row_str += f" | {val:>12}"
                print(row_str)
    else:
        print("  ⚠️ 기업실적 데이터를 불러올 수 없습니다.")

    print("\n" + "=" * 75 + "\n")

def main():
    print(f"🚀 네이버 금융 종목 종합 분석기 실행 중... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    
    codes = extract_stock_codes_from_file(STOCKS_FILE)
    if not codes:
        print(f"⚠️ '{STOCKS_FILE}'에서 종목 코드 또는 네이버 금융 링크를 찾을 수 없습니다.")
        return

    print(f"🔎 메모장에서 발견한 종목 목록: {codes}\n")

    for code in codes:
        analyze_stock(code)

    print("✅ 모든 종목 조회가 완료되었습니다.")
    print(f"💡 종목 수정/추가는 '{STOCKS_FILE}' 메모장에서 진행하시면 됩니다.")

if __name__ == "__main__":
    main()
