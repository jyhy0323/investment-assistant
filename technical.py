import logging
import math
from datetime import datetime, timedelta
import FinanceDataReader as fdr
from collector import validate_code

logger = logging.getLogger("StockApp")


def _to_int(val) -> int | None:
    """numpy/pandas 숫자를 순수 Python int로 안전하게 변환한다."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(round(f))
    except (TypeError, ValueError):
        return None


def _to_float(val, digits: int = 2) -> float | None:
    """numpy/pandas 숫자를 순수 Python float로 안전하게 변환한다."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None


def fetch_ohlcv_dataframe(code: str, days: int = 180):
    """
    Step 6 (1차): FinanceDataReader로 최근 6개월(기본 180일) 일봉(OHLCV) DataFrame을 조회한다.
    """
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    logger.info(f"[FDR]       FinanceDataReader 주가 데이터 조회 시작 (code={code}, {start_str}~{end_str})")
    df = fdr.DataReader(code, start_str, end_str)
    return df


def extract_recent_candles(df, count: int = 10) -> list[dict]:
    """DataFrame의 최근 N거래일 일봉을 순수 Python 타입 딕셔너리 리스트로 정제한다."""
    if df is None or df.empty:
        return []

    candles = []
    tail_df = df.tail(count)
    for idx, row in tail_df.iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        candles.append({
            "date": date_str,
            "open": _to_int(row.get("Open")),
            "high": _to_int(row.get("High")),
            "low": _to_int(row.get("Low")),
            "close": _to_int(row.get("Close")),
            "volume": _to_int(row.get("Volume")),
        })
    return candles


def collect_technical_basic(code: str) -> dict:
    """1차 테스트용: 일봉 조회 및 최근 10거래일 정제 데이터를 반환한다."""
    cleaned_code = str(code).strip() if code else ""
    result = {
        "code": cleaned_code,
        "as_of": None,
        "price_summary": {},
        "recent_candles": [],
        "errors": [],
    }

    validation_error = validate_code(cleaned_code)
    if validation_error:
        result["errors"].append(validation_error)
        return result

    try:
        df = fetch_ohlcv_dataframe(cleaned_code, days=180)
    except Exception:
        msg = f"FinanceDataReader에서 종목({cleaned_code}) 주가 데이터를 불러오지 못했습니다."
        logger.exception(f"[ERROR]     {msg}")
        result["errors"].append(msg)
        return result

    if df is None or df.empty:
        msg = f"종목({cleaned_code})의 최근 주가 데이터가 비어 있습니다."
        logger.warning(f"[ERROR]     {msg}")
        result["errors"].append(msg)
        return result

    candles = extract_recent_candles(df, count=10)
    result["recent_candles"] = candles
    result["as_of"] = candles[-1]["date"] if candles else None
    logger.info(f"[FDR]       FinanceDataReader 주가 데이터 조회 완료 (총 {len(df)}거래일, 최근 {len(candles)}일 정제)")
    return result


def calculate_rsi(close_series, period: int = 14) -> float | None:
    """Wilder 방식으로 RSI(14)를 계산해 소수점 2자리 float로 반환한다."""
    if close_series is None or len(close_series) < period + 1:
        return None
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0 if last_gain > 0 else 50.0
    rs = last_gain / last_loss
    rsi = 100 - (100 / (1 + rs))
    return _to_float(rsi, digits=2)


def calculate_price_summary(df) -> dict:
    """DataFrame으로부터 이동평균선(MA5/20/60), 20일 고/저가, RSI(14)를 계산한다."""
    if df is None or df.empty:
        return {}

    close = df["Close"]
    latest_row = df.iloc[-1]
    recent_20 = df.tail(20)

    ma5 = _to_int(close.tail(5).mean()) if len(df) >= 5 else None
    ma20 = _to_int(close.tail(20).mean()) if len(df) >= 20 else None
    ma60 = _to_int(close.tail(60).mean()) if len(df) >= 60 else None

    return {
        "latest_close": _to_int(latest_row.get("Close")),
        "volume": _to_int(latest_row.get("Volume")),
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "rsi_14": calculate_rsi(close, period=14),
        "high_20d": _to_int(recent_20["High"].max()),
        "low_20d": _to_int(recent_20["Low"].min()),
    }


def extract_chart_series(df, count: int = 60) -> list[dict]:
    """최근 N거래일 종가와 MA5/MA20/MA60 이동평균선 시계열을 차트용으로 정제한다."""
    if df is None or df.empty:
        return []

    work = df.copy()
    work["MA5"] = work["Close"].rolling(5).mean()
    work["MA20"] = work["Close"].rolling(20).mean()
    work["MA60"] = work["Close"].rolling(60).mean()

    series = []
    for idx, row in work.tail(count).iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        series.append({
            "date": date_str,
            "close": _to_int(row.get("Close")),
            "ma5": _to_int(row.get("MA5")),
            "ma20": _to_int(row.get("MA20")),
            "ma60": _to_int(row.get("MA60")),
        })
    return series


def calculate_period_returns(df) -> dict:
    """최근 1주(5거래일), 1개월(21거래일), 3개월(63거래일), 6개월(전체 시작일) 수익률(%)을 계산한다."""
    if df is None or len(df) < 2:
        return {"1w": None, "1m": None, "3m": None, "6m": None}

    close = df["Close"]
    latest = float(close.iloc[-1])
    n = len(close)

    def _ret(offset: int) -> float | None:
        if n <= offset:
            base = float(close.iloc[0])
        else:
            base = float(close.iloc[-1 - offset])
        if base == 0:
            return None
        return _to_float(((latest - base) / base) * 100.0, digits=2)

    return {
        "1w": _ret(5) if n >= 6 else None,
        "1m": _ret(21) if n >= 22 else None,
        "3m": _ret(63) if n >= 64 else None,
        "6m": _ret(n - 1),
    }


def collect_technical(code: str) -> dict:
    """Step 7 (2차): 일봉 조회(1회), 기술적 지표 계산, 기간별 수익률, 최근 10거래일 및 60일 차트 시계열을 통합 반환한다."""
    cleaned_code = str(code).strip() if code else ""
    result = {
        "code": cleaned_code,
        "as_of": None,
        "price_summary": {},
        "period_returns": {},
        "recent_candles": [],
        "chart_series": [],
        "errors": [],
    }

    validation_error = validate_code(cleaned_code)
    if validation_error:
        result["errors"].append(validation_error)
        return result

    try:
        df = fetch_ohlcv_dataframe(cleaned_code, days=180)
        if df is None or df.empty:
            msg = f"종목({cleaned_code})의 최근 주가 데이터가 비어 있습니다."
            logger.warning(f"[ERROR]     {msg}")
            result["errors"].append(msg)
            return result

        candles = extract_recent_candles(df, count=10)
        result["recent_candles"] = candles
        result["as_of"] = candles[-1]["date"] if candles else None
        result["price_summary"] = calculate_price_summary(df)
        result["period_returns"] = calculate_period_returns(df)
        result["chart_series"] = extract_chart_series(df, count=60)
        logger.info(
            f"[FDR]       기술적 지표 계산 완료 "
            f"(close={result['price_summary'].get('latest_close')}, "
            f"ma20={result['price_summary'].get('ma20')}, "
            f"rsi_14={result['price_summary'].get('rsi_14')})"
        )
    except Exception:
        msg = f"종목({cleaned_code})의 기술적 지표 수집 중 오류가 발생했습니다."
        logger.exception(f"[ERROR]     {msg}")
        result["errors"].append(msg)

    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    import json
    sample = collect_technical("000660")
    logger.info(
        f"[TEST]      테스트 결과: {json.dumps({**sample, 'recent_candles': sample['recent_candles'][-2:]}, ensure_ascii=False)}"
    )
