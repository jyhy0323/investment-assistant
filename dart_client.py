import io
import json
import logging
import os
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("StockApp")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = tempfile.gettempdir() if os.getenv("VERCEL") else BASE_DIR
CORP_MAP_CACHE = os.path.join(_CACHE_DIR, "dart_corp_map.json")
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7일 캐시

POSITIVE_KEYWORDS = (
    "자기주식",
    "자사주",
    "주식소각",
    "단일판매",
    "공급계약",
    "현금ㆍ현물배당",
    "현금배당",
    "무상증자",
)

NEGATIVE_KEYWORDS = (
    "유상증자",
    "전환사채",
    "신주인수권부사채",
    "교환사채",
    "감자결정",
    "횡령",
    "배임",
    "관리종목",
    "불성실공시",
    "최대주주변경",
    "소송등의제기",
)


def _get_dart_key() -> str:
    key = os.getenv("DART_API_KEY", "").strip()
    if not key or key.startswith("여기에"):
        return ""
    return key


def _load_corp_map(api_key: str) -> tuple[dict | None, str | None]:
    """종목코드(6자리) -> DART 고유번호(8자리) 매핑을 로컬 캐시에서 불러오거나 새로 다운로드한다."""
    if os.path.exists(CORP_MAP_CACHE):
        try:
            age = time.time() - os.path.getmtime(CORP_MAP_CACHE)
            if age < CACHE_TTL_SECONDS:
                with open(CORP_MAP_CACHE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, dict) and len(cached) > 100:
                    return cached, None
        except Exception:
            logger.warning("[DART]      고유번호 캐시 읽기 실패 — 새로 다운로드합니다.")

    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    logger.info("[DART]      Open DART 고유번호 매핑 파일(CORPCODE.xml) 다운로드 시작")
    try:
        res = requests.get(url, params={"crtfc_key": api_key}, timeout=15)
        if res.status_code != 200:
            return None, f"DART 고유번호 목록 다운로드 실패 (상태코드: {res.status_code})"

        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            xml_name = zf.namelist()[0]
            xml_bytes = zf.read(xml_name)

        root = ET.fromstring(xml_bytes)
        corp_map = {}
        for item in root.findall("list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            if len(stock_code) == 6 and corp_code:
                corp_map[stock_code] = corp_code

        try:
            with open(CORP_MAP_CACHE, "w", encoding="utf-8") as f:
                json.dump(corp_map, f, ensure_ascii=False)
            logger.info(f"[DART]      고유번호 매핑 캐시 저장 완료 (상장사 {len(corp_map)}개)")
        except OSError:
            logger.warning("[DART]      캐시 파일 쓰기 권한 없음 — 메모리 결과만 사용합니다.")
        return corp_map, None
    except zipfile.BadZipFile:
        return None, "DART API 키가 유효하지 않거나 응답이 ZIP 형식이 아닙니다."
    except requests.Timeout:
        return None, "DART 고유번호 다운로드 시간이 초과되었습니다."
    except Exception:
        logger.exception("[ERROR]     DART 고유번호 매핑 생성 실패")
        return None, "DART 고유번호 매핑 생성 중 오류가 발생했습니다."


def _classify_disclosure(title: str) -> tuple[str, str]:
    """공시 제목 키워드로 주린이 참고용 태그(positive/negative/info)와 라벨을 분류한다."""
    compact = title.replace(" ", "")
    for kw in NEGATIVE_KEYWORDS:
        if kw in compact:
            return "negative", "주의 확인"
    for kw in POSITIVE_KEYWORDS:
        if kw in compact:
            return "positive", "호재 참고"
    return "info", "일반 공시"


def fetch_dart_disclosures(stock_code: str, days: int = 90, limit: int = 8) -> tuple[list[dict], str | None]:
    """
    Open DART list.json API로 최근 3개월(기본 90일) 공식 공시 목록을 조회한다.
    (API Key는 절대 로그에 출력하지 않는다.)
    """
    api_key = _get_dart_key()
    if not api_key:
        return [], "DART API Key가 설정되지 않았습니다. (.env 파일을 확인하세요)"

    corp_map, err = _load_corp_map(api_key)
    if err or not corp_map:
        return [], err or "DART 고유번호 매핑을 불러오지 못했습니다."

    corp_code = corp_map.get(str(stock_code).strip())
    if not corp_code:
        return [], f"DART에서 종목코드({stock_code})의 기업 고유번호를 찾지 못했습니다."

    end_dt = datetime.now()
    bgn_dt = end_dt - timedelta(days=days)
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_dt.strftime("%Y%m%d"),
        "end_de": end_dt.strftime("%Y%m%d"),
        "page_count": limit,
    }

    logger.info(f"[DART]      Open DART 공시 조회 시작 (code={stock_code}, corp_code={corp_code})")

    try:
        res = requests.get("https://opendart.fss.or.kr/api/list.json", params=params, timeout=7)
        if res.status_code != 200:
            return [], f"DART 공시 조회 실패 (상태코드: {res.status_code})"
        data = res.json()
    except requests.Timeout:
        return [], "DART 공시 서버 응답 시간이 초과되었습니다."
    except ValueError:
        return [], "DART 공시 응답을 JSON으로 변환하는 데 실패했습니다."
    except requests.RequestException:
        return [], "DART 공시 서버에 연결하지 못했습니다."

    status = data.get("status")
    if status == "013":
        # 013: 조회된 데이터가 없음 (정상 응답)
        logger.info(f"[DART]      최근 {days}일간 등록된 공시가 없습니다. (code={stock_code})")
        return [], None
    if status != "000":
        msg = data.get("message", "알 수 없는 오류")
        return [], f"DART API 오류 (코드 {status}: {msg})"

    disclosures = []
    for item in data.get("list", [])[:limit]:
        title = str(item.get("report_nm", "")).strip()
        rcept_no = str(item.get("rcept_no", "")).strip()
        raw_dt = str(item.get("rcept_dt", "")).strip()
        date_fmt = f"{raw_dt[:4]}-{raw_dt[4:6]}-{raw_dt[6:8]}" if len(raw_dt) == 8 else raw_dt
        tag, tag_label = _classify_disclosure(title)

        disclosures.append({
            "title": title,
            "date": date_fmt,
            "submitter": str(item.get("flr_nm", "")).strip(),
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else "",
            "tag": tag,
            "tag_label": tag_label,
        })

    logger.info(f"[DART]      공시 수집 완료 (code={stock_code}, {len(disclosures)}건)")
    return disclosures, None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    items, error = fetch_dart_disclosures("000660")
    logger.info(f"[TEST]      DART 테스트 결과: count={len(items)}, error={error}")
    for it in items[:3]:
        logger.info(f"  - [{it['date']}] ({it['tag_label']}) {it['title']}")
