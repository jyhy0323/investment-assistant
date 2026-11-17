import os
import logging
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from collector import collect_all
from technical import collect_technical
from dify_client import ask_dify, build_analysis_prompt

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


@app.route("/test", methods=["GET"])
def test_page():
    """기존 1차 데이터 수집기 확인용 화면(templates/test.html)을 반환한다."""
    return render_template("test.html")

@app.route("/health", methods=["GET"])
def health_check():
    """
    서버 상태 및 API 키 설정 여부만 반환하는 헬스체크 라우트.
    (절대 규칙: API Key 값 자체는 보안상 절대 반환하지 않음)
    """
    serper_key = os.getenv("SERPER_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    dify_fund_key = os.getenv("DIFY_FUNDAMENTAL_API_KEY", "").strip()
    dify_tech_key = os.getenv("DIFY_TECHNICAL_API_KEY", "").strip()

    serper_configured = bool(serper_key and not serper_key.startswith("여기에"))
    gemini_configured = bool(gemini_key and not gemini_key.startswith("여기에"))
    dify_fund_configured = bool(dify_fund_key and not dify_fund_key.startswith("여기에"))
    dify_tech_configured = bool(dify_tech_key and not dify_tech_key.startswith("여기에"))

    logger.info(
        f"[HEALTH] 상태 점검 요청 - Serper: {serper_configured}, Gemini: {gemini_configured}, "
        f"Dify(종목분석): {dify_fund_configured}, Dify(지표해석): {dify_tech_configured}"
    )

    return jsonify({
        "status": "ok",
        "service": "Stock Data Collector & Dify AI Briefing App",
        "api_keys": {
            "serper_news_api": "configured" if serper_configured else "missing",
            "gemini_api": "configured" if gemini_configured else "missing",
            "dify_fundamental_api": "configured" if dify_fund_configured else "missing",
            "dify_technical_api": "configured" if dify_tech_configured else "missing"
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


@app.route("/technical", methods=["POST"])
def fetch_technical():
    """종목코드를 받아 FinanceDataReader 기반 주가 및 기술적 지표 JSON을 반환한다."""
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()

    logger.info(f"[REQUEST]  POST /technical code={code}")

    if not code:
        msg = "종목코드가 입력되지 않았습니다."
        logger.warning(f"[ERROR]    {msg}")
        return jsonify({
            "code": "",
            "as_of": None,
            "price_summary": {},
            "recent_candles": [],
            "errors": [msg],
        }), 400

    try:
        data = collect_technical(code)
    except Exception:
        msg = "기술적 지표 수집 중 예기치 않은 서버 오류가 발생했습니다."
        logger.exception(f"[ERROR]    {msg}")
        return jsonify({
            "code": code,
            "as_of": None,
            "price_summary": {},
            "recent_candles": [],
            "errors": [msg],
        }), 500

    error_count = len(data.get("errors", []))
    logger.info(
        f"[RESPONSE] 기술적 지표 완료 / code={code}, "
        f"candles={len(data.get('recent_candles', []))}일, errors={error_count}건"
    )

    status_code = 400 if (not data.get("price_summary") and error_count > 0) else 200
    return jsonify(data), status_code


@app.route("/analyze", methods=["POST"])
def analyze_stock():
    """
    Step 10: 수집된 데이터(네이버+Serper 또는 FDR)를 해당 Dify 챗봇(/chat-messages)에 보내
    AI 분석 답변(answer)과 conversation_id를 반환한다.
    """
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    mode = str(payload.get("mode", "fundamental")).strip()
    question = str(payload.get("question", "")).strip()
    conversation_id = str(payload.get("conversation_id", "")).strip()
    cached_data = payload.get("cached_data")

    logger.info(f"[REQUEST]  POST /analyze mode={mode} code={code} has_conv={bool(conversation_id)}")

    if mode not in ("fundamental", "technical"):
        msg = f"지원하지 않는 분석 모드입니다: {mode}"
        logger.warning(f"[ERROR]    {msg}")
        return jsonify({"mode": mode, "code": code, "data": None, "answer": None, "conversation_id": "", "errors": [msg]}), 400

    # 후속 질문(conversation_id가 있고 question이 있는 경우)이면 재수집 없이 바로 Dify에 질문
    if conversation_id and question:
        dify_res = ask_dify(mode=mode, query=question, conversation_id=conversation_id)
        errors = [dify_res["error"]] if dify_res.get("error") else []
        return jsonify({
            "mode": mode,
            "code": code,
            "data": cached_data,
            "answer": dify_res.get("answer"),
            "conversation_id": dify_res.get("conversation_id", conversation_id),
            "errors": errors,
        }), 200

    if not code:
        msg = "종목코드가 입력되지 않았습니다."
        logger.warning(f"[ERROR]    {msg}")
        return jsonify({"mode": mode, "code": "", "data": None, "answer": None, "conversation_id": "", "errors": [msg]}), 400

    # 1) 데이터 수집 (이미 프론트에서 넘긴 cached_data가 있으면 재활용, 없으면 직접 수집)
    if isinstance(cached_data, dict) and cached_data.get("code") == code:
        collected = cached_data
    else:
        collected = collect_all(code) if mode == "fundamental" else collect_technical(code)

    errors = list(collected.get("errors", []))
    has_valid_data = bool(collected.get("name")) if mode == "fundamental" else bool(collected.get("price_summary"))

    if not has_valid_data:
        return jsonify({
            "mode": mode,
            "code": code,
            "data": collected,
            "answer": None,
            "conversation_id": "",
            "errors": errors,
        }), 400

    # 2) Dify 챗봇 호출 (Dify 실패 시에도 수집된 원천 데이터는 정상 반환)
    query = build_analysis_prompt(mode=mode, stock_data=collected, user_question=question)
    dify_res = ask_dify(mode=mode, query=query, conversation_id=conversation_id)
    if dify_res.get("error"):
        errors.append(dify_res["error"])

    logger.info(
        f"[RESPONSE] 분석 완료 / mode={mode}, code={code}, "
        f"answer_len={len(dify_res.get('answer') or '')}, errors={len(errors)}건"
    )

    return jsonify({
        "mode": mode,
        "code": code,
        "data": collected,
        "answer": dify_res.get("answer"),
        "conversation_id": dify_res.get("conversation_id", ""),
        "errors": errors,
    }), 200


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"[START] Flask 서버 시작 (Debug: {debug_mode}) - http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=debug_mode)
