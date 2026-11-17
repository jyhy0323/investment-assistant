import os
import logging
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from collector import collect_all

# .env 파일에서 환경변수 로드
load_dotenv()

# 로깅 기본 설정 (마스터 프롬프트 절대 규칙: print 대신 logging 사용)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("StockApp")

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    """메인 웹페이지(templates/index.html)를 반환한다."""
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health_check():
    """
    서버 상태 및 API 키 설정 여부만 반환하는 헬스체크 라우트.
    (절대 규칙: API Key 값 자체는 보안상 절대 반환하지 않음)
    """
    serper_key = os.getenv("SERPER_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    serper_configured = bool(serper_key and not serper_key.startswith("여기에"))
    gemini_configured = bool(gemini_key and not gemini_key.startswith("여기에"))

    logger.info(f"[HEALTH] 상태 점검 요청 - Serper 설정: {serper_configured}, Gemini 설정: {gemini_configured}")

    return jsonify({
        "status": "ok",
        "service": "Stock Data Collector & Briefing Tool",
        "api_keys": {
            "serper_news_api": "configured" if serper_configured else "missing",
            "gemini_api": "configured" if gemini_configured else "missing"
        }
    }), 200


@app.route("/fetch", methods=["POST"])
def fetch_stock():
    """종목코드를 받아 네이버 금융 데이터와 Serper 뉴스를 통합 수집하여 반환한다."""
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()

    logger.info(f"[REQUEST]  POST /fetch code={code}")

    if not code:
        msg = "종목코드가 입력되지 않았습니다."
        logger.warning(f"[ERROR]    {msg}")
        return jsonify({
            "code": "",
            "name": None,
            "snapshot": {},
            "financials": [],
            "news": [],
            "errors": [msg],
        }), 400

    try:
        data = collect_all(code)
    except Exception:
        msg = "데이터 수집 중 예기치 않은 서버 오류가 발생했습니다."
        logger.exception(f"[ERROR]    {msg}")
        return jsonify({
            "code": code,
            "name": None,
            "snapshot": {},
            "financials": [],
            "news": [],
            "errors": [msg],
        }), 500

    error_count = len(data.get("errors", []))
    logger.info(
        f"[RESPONSE] 수집 완료 / name={data.get('name')}, "
        f"financials={len(data.get('financials', []))}건, "
        f"news={len(data.get('news', []))}건, errors={error_count}건"
    )

    status_code = 400 if (not data.get("name") and error_count > 0) else 200
    return jsonify(data), status_code


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"[START] Flask 서버 시작 (Debug: {debug_mode}) - http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=debug_mode)
