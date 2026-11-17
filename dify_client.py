import json
import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("StockApp")

MODE_KEY_MAP = {
    "fundamental": ("DIFY_FUNDAMENTAL_API_KEY", "투자종목분석"),
    "technical": ("DIFY_TECHNICAL_API_KEY", "지표해석기"),
}


def build_analysis_prompt(mode: str, stock_data: dict, user_question: str = "") -> str:
    """수집된 JSON 데이터와 사용자 질문을 조합해 Dify 챗봇에 보낼 query 문자열을 만든다."""
    data_json = json.dumps(stock_data, ensure_ascii=False, indent=2)

    if user_question and user_question.strip():
        return f"{user_question.strip()}\n\n[참고 데이터]\n{data_json}"

    if mode == "fundamental":
        return (
            "아래는 네이버 금융과 Serper 뉴스에서 수집한 종목 데이터입니다. "
            "초보자도 이해하기 쉽게 핵심 시세, 밸류에이션, 실적(확정/추정치 구분), 최신 뉴스 이슈를 정리해 주세요.\n\n"
            f"{data_json}"
        )

    return (
        "아래는 FinanceDataReader로 수집한 최근 일봉 및 기술적 지표(이동평균선, RSI, 20일 고저가) 데이터입니다. "
        "초보자도 이해하기 쉽게 현재 주가 위치, 이동평균선 배열, RSI 과매수/과매도 여부를 객관적으로 해석해 주세요.\n\n"
        f"{data_json}"
    )


def ask_dify(
    mode: str,
    query: str,
    conversation_id: str = "",
    inputs: dict | None = None,
    user_id: str = "investment-assistant-user",
) -> dict:
    """
    Step 9: Dify 일반 챗봇 API (POST /v1/chat-messages)를 호출하여
    AI 답변(answer)과 대화 ID(conversation_id)를 반환한다.
    """
    if mode not in MODE_KEY_MAP:
        msg = f"지원하지 않는 Dify 모드입니다: {mode}"
        logger.error(f"[ERROR]     {msg}")
        return {"answer": None, "conversation_id": conversation_id or "", "error": msg}

    env_name, app_label = MODE_KEY_MAP[mode]
    api_key = os.getenv(env_name, "").strip()
    if not api_key or api_key.startswith("여기에"):
        msg = f"Dify '{app_label}' API Key({env_name})가 설정되지 않았습니다. (.env 파일을 확인하세요)"
        logger.warning(f"[DIFY]      {msg}")
        return {"answer": None, "conversation_id": conversation_id or "", "error": msg}

    base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
    url = f"{base_url}/chat-messages"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": inputs or {},
        "query": query,
        "response_mode": "blocking",
        "conversation_id": conversation_id or "",
        "user": user_id,
    }

    logger.info(f"[DIFY]      Dify 챗봇 API(/chat-messages) 호출 시작 (mode={mode}, app={app_label})")

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=45)
        if res.status_code != 200:
            try:
                err_detail = res.json().get("message", res.text[:200])
            except ValueError:
                err_detail = res.text[:200]
            msg = f"Dify '{app_label}' 호출 실패 (상태코드: {res.status_code}, 사유: {err_detail})"
            logger.error(f"[ERROR]     {msg}")
            return {"answer": None, "conversation_id": conversation_id or "", "error": msg}

        data = res.json()
    except requests.Timeout:
        msg = f"Dify '{app_label}' 응답 시간이 초과되었습니다. (네트워크 타임아웃)"
        logger.exception(f"[ERROR]     {msg}")
        return {"answer": None, "conversation_id": conversation_id or "", "error": msg}
    except ValueError:
        msg = f"Dify '{app_label}' 응답을 JSON으로 변환하는 데 실패했습니다."
        logger.exception(f"[ERROR]     {msg}")
        return {"answer": None, "conversation_id": conversation_id or "", "error": msg}
    except requests.RequestException:
        msg = f"Dify '{app_label}' 서버에 연결하지 못했습니다."
        logger.exception(f"[ERROR]     {msg}")
        return {"answer": None, "conversation_id": conversation_id or "", "error": msg}

    answer = data.get("answer")
    new_conv_id = data.get("conversation_id", conversation_id or "")
    logger.info(f"[DIFY]      Dify '{app_label}' 응답 완료 (길이={len(answer or '')}자)")

    return {
        "answer": answer,
        "conversation_id": new_conv_id,
        "error": None,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    test_res = ask_dify("technical", "테스트 인사입니다. 한 줄로만 인사해 주세요.")
    logger.info(f"[TEST]      Dify 연결 테스트 결과: error={test_res['error']}, answer={str(test_res['answer'])[:80]}")
