import os
import re
import sys
import requests
from datetime import datetime

# Windows 콘솔 인코딩 대응
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

def extract_stock_code(line: str) -> str | None:
    """텍스트 한 줄에서 6자리 종목 코드 추출 (URL 포함)."""
    clean = line.split("#")[0].strip()
    if not clean:
        return None

    # URL 또는 6자리 숫자 종목 코드 탐색
    match = re.search(r"\b(\d{6})\b", clean)
    if match:
        return match.group(1)
    return None

def fetch_stock_info(code: str) -> dict | None:
    """네이버 금융 모바일 API로부터 종목의 실시간 정보 조회."""
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code != 200:
            return None
        return res.json()
    except Exception as e:
        print(f"[{code}] 조회 오류: {e}")
        return None

def get_fluctuation_mark(info: dict) -> str:
    """상승/하락/보합 표시 문자열 반환."""
    try:
        ratio = float(info.get("fluctuationsRatio", 0.0))
    except Exception:
        ratio = 0.0

    if ratio > 0:
        return f"+{ratio}% ▲"
    elif ratio < 0:
        return f"{ratio}% ▼"
    return f"{ratio}% -"

def main():
    print("=" * 70)
    print(f"[네이버 금융 관심 종목 실시간 시세] ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 70)

    if not os.path.exists(STOCKS_FILE):
        print(f"❌ '{STOCKS_FILE}' 파일이 없습니다. 먼저 파일을 생성해 주세요.")
        return

    with open(STOCKS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    codes = []
    for line in lines:
        code = extract_stock_code(line)
        if code and code not in codes:
            codes.append(code)

    if not codes:
        print(f"⚠️ '{STOCKS_FILE}'에 등록된 종목 코드가 없습니다.")
        return

    header = f"{'종목명':<14} | {'종목코드':<8} | {'현재가(원)':>12} | {'전일대비':>10} | {'등락률':>10}"
    print(header)
    print("-" * 70)

    for code in codes:
        info = fetch_stock_info(code)
        if not info:
            print(f"{'조회 실패':<14} | {code:<8} | {'-':>12} | {'-':>10} | {'-':>10}")
            continue

        name = info.get("stockName", "알 수 없음")
        close_price = info.get("closePrice", "0")
        diff_price = info.get("compareToPreviousClosePrice", "0")
        ratio_str = get_fluctuation_mark(info)

        print(f"{name:<14} | {code:<8} | {close_price:>12} | {diff_price:>10} | {ratio_str:>10}")

    print("=" * 70)
    print(f"💡 종목 추가 및 관리는 메모장 파일 ({STOCKS_FILE}) 에서 수정하시면 됩니다.\n")

if __name__ == "__main__":
    main()
