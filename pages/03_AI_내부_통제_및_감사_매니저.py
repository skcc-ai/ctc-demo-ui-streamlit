#!/usr/bin/env python3
"""법인카드 정산 검토 시스템 - Streamlit App"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from pathlib import Path
import base64
import json
import logging
import ast

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="법인카드 정산 검토 시스템",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 스타일링
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .expense-card {
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        background-color: #f8f9fa;
    }
    .expense-header {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .expense-detail {
        margin: 0.3rem 0;
    }
    .status-pending {
        color: #ff9800;
        font-weight: bold;
    }
    .status-approved {
        color: #4caf50;
        font-weight: bold;
    }
    .status-rejected {
        color: #f44336;
        font-weight: bold;
    }
    .stream-container {
        background-color: #f0f2f6;
        color: #1f1f1f;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        min-height: 200px;
        max-height: 400px;
        overflow-y: auto;
        font-family: monospace;
        font-size: 0.9rem;
        line-height: 1.6;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .analysis-section {
        background-color: #e8f4f8;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .receipt-image {
        border: 2px solid #ddd;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .button-container {
        display: flex;
        gap: 1rem;
        margin-top: 2rem;
    }
    .stButton > button {
        width: 200px;
        height: 60px;
        font-size: 1.1rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# DB 설정
# ============================================================================

DB_CONFIG = {
    'host': 'dify-ctc-postgre.postgres.database.azure.com',
    'port': 5432,
    'user': 'adminuser',
    'password': 'Passw0rd!',
    'database': 'eca_demo',
    'db_type': 'postgresql',
    'table': 'expenses'
}

# 영수증 데이터 폴더 경로
RECEIPT_DATA_DIR = Path(__file__).parent / "data"


# ============================================================================
# DB 연결 및 조회 함수들
# ============================================================================

def get_db_connection():
    """PostgreSQL 데이터베이스 연결"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            connect_timeout=10
        )
        return conn
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {str(e)}")
        return None


def get_expense_list():
    """법인카드 정산 목록 조회 (DB에서 전체 목록 가져오기)"""
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # 전체 목록 조회 (id 기준 정렬)
            query = f"""
                SELECT * FROM {DB_CONFIG['table']}
                ORDER BY id
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            # 딕셔너리 리스트로 변환
            expenses = []
            for row in results:
                expense = dict(row)
                # 날짜 필드가 datetime 객체인 경우 문자열로 변환
                for key, value in expense.items():
                    if isinstance(value, datetime):
                        # timestamp 필드는 날짜와 시간 모두 표시
                        if key in ['payment_datetime', 'created_at']:
                            expense[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            expense[key] = value.strftime('%Y-%m-%d')
                expenses.append(expense)
            
            return expenses
    except Exception as e:
        st.error(f"데이터 조회 오류: {str(e)}")
        return []
    finally:
        conn.close()


def get_violations(expense_id: str) -> list:
    """violations 테이블에서 해당 정산 ID의 위반 항목 조회
    
    Args:
        expense_id: 정산 ID
    
    Returns:
        위반 항목 리스트
    """
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT violation_type, description, reference
                FROM violations
                WHERE expense_id = %s
                ORDER BY id
            """
            cursor.execute(query, (expense_id,))
            results = cursor.fetchall()
            
            # 딕셔너리 리스트로 변환
            violations = []
            for row in results:
                violations.append({
                    'violation_type': row.get('violation_type', ''),
                    'description': row.get('description', ''),
                    'reference': row.get('reference', '')
                })
            
            return violations
    except Exception as e:
        st.error(f"위반 항목 조회 오류: {str(e)}")
        return []
    finally:
        conn.close()


def get_expense_detail(expense_id: str) -> Dict[str, Any]:
    """특정 정산 ID의 상세 정보 조회
    
    Args:
        expense_id: 정산 ID
    
    Returns:
        정산 상세 정보 딕셔너리
    """
    conn = get_db_connection()
    if conn is None:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = f"""
                SELECT * FROM {DB_CONFIG['table']}
                WHERE id = %s
            """
            cursor.execute(query, (expense_id,))
            result = cursor.fetchone()
            
            if result:
                expense = dict(result)
                # 날짜 필드가 datetime 객체인 경우 문자열로 변환
                for key, value in expense.items():
                    if isinstance(value, datetime):
                        if key in ['payment_datetime', 'created_at']:
                            expense[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            expense[key] = value.strftime('%Y-%m-%d')
                return expense
            else:
                return None
    except Exception as e:
        st.error(f"정산 상세 조회 오류: {str(e)}")
        return None
    finally:
        conn.close()


def get_receipt_path(expense_id: str) -> str:
    """정산 ID에 해당하는 영수증 PNG 파일 경로 가져오기
    
    Args:
        expense_id: 정산 ID
    
    Returns:
        영수증 PNG 파일의 절대 경로 (문자열)
    """
    png_path = RECEIPT_DATA_DIR / f"{expense_id}.png"
    
    if png_path.exists():
        return str(png_path)
    else:
        # 파일이 없으면 None 반환
        st.warning(f"영수증 파일을 찾을 수 없습니다: {expense_id}.png")
        return None


def display_png(file_path: str):
    """PNG 파일을 이미지로 표시
    
    Args:
        file_path: PNG 파일 경로
    """
    if file_path and Path(file_path).exists():
        st.image(file_path, use_container_width=True)
    else:
        st.error("영수증 파일을 찾을 수 없습니다.")


def extract_bot_message(json_data: Dict[str, Any]) -> str:
    """JSON 응답에서 봇 메시지만 추출
    
    Args:
        json_data: API 응답 JSON 데이터
    
    Returns:
        봇 메시지 문자열 (없으면 빈 문자열)
    """
    try:
        # result.responses 배열에서 봇 메시지 추출
        result = json_data.get('result', {})
        responses = result.get('responses', [])
        
        bot_messages = []
        for response in responses:
            if response.get('sender') == 'BOT':
                message = response.get('message', '')
                if message:
                    bot_messages.append(message)
        
        # 봇 메시지들을 합쳐서 반환
        if bot_messages:
            return '\n'.join(bot_messages)
        
        # 다른 형식의 응답 처리
        if 'message' in json_data and json_data.get('sender') == 'BOT':
            return json_data.get('message', '')
        
        return ''
    except Exception:
        return ''


def _make_api_call(
    message: str,
    conversation_id: str,
    expense_id: str
) -> Dict[str, Any]:
    """API 호출 헬퍼 함수 (동기 방식)"""
    app_id = "TExNQXBwOjY5OTNmNzY1NGIwODRkM2FiNzVhNjY1Nw=="
    api_url = (
        f"https://backend.alli.ai/webapi/apps/{app_id}/run"
    )
    api_key = "SUKYXKTTRPYVAHHOFTSWQYWS3QFSONQJYA"
    
    payload = {
        "chat": {
            "message": message
        },
        "conversationId": conversation_id,
        "isStateful": True,
        "model": "sync"
    }
    
    headers = {
        "Content-Type": "application/json",
        "API-KEY": api_key
    }
    
    msg_preview = (
        f"{message[:50]}..." if message else "빈 값"
    )
    conv_preview = (
        f"{conversation_id[:50]}..." if conversation_id else "빈 값"
    )
    logger.info(
        f"[API 호출] expense_id: {expense_id}, "
        f"message: {msg_preview}, "
        f"conversationId: {conv_preview}"
    )
    
    # 동기 방식으로 API 호출
    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=300
        )
        
        logger.info(
            f"[API 응답 상태] expense_id: {expense_id}, "
            f"상태 코드: {response.status_code}"
        )
        
        # 에러 응답인 경우 상세 로그
        if response.status_code >= 400:
            logger.error(
                f"[API 호출 에러] expense_id: {expense_id}, "
                f"상태 코드: {response.status_code}, "
                f"응답 헤더: {dict(response.headers)}, "
                f"응답 내용: {response.text[:1000]}"
            )
        
        response.raise_for_status()
        
        # JSON 응답 파싱
        result = response.json()
        logger.info(
            f"[API 응답] expense_id: {expense_id}, "
            f"응답 수신 완료"
        )
        
        return result
        
    except requests.exceptions.HTTPError as e:
        logger.error(
            f"[API HTTP 에러] expense_id: {expense_id}, "
            f"상태 코드: {e.response.status_code if e.response else 'N/A'}, "
            f"응답 내용: {e.response.text[:1000] if e.response else str(e)}, "
            f"요청 URL: {api_url}, "
            f"요청 페이로드: {json.dumps(payload, ensure_ascii=False)}"
        )
        raise
    except requests.exceptions.RequestException as e:
        logger.error(
            f"[API 요청 에러] expense_id: {expense_id}, "
            f"에러: {str(e)}, "
            f"요청 URL: {api_url}, "
            f"요청 페이로드: {json.dumps(payload, ensure_ascii=False)}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[API 기타 에러] expense_id: {expense_id}, "
            f"에러: {str(e)}, "
            f"요청 URL: {api_url}"
        )
        raise


def _extract_conversation_id(
    response_data: Dict[str, Any],
    expense_id: str
) -> str:
    """응답에서 conversation ID 추출"""
    try:
        result = response_data.get('result', {})
        conversation = result.get('conversation', {})
        conv_id = conversation.get('id', '')
        
        if conv_id:
            conv_ids = st.session_state.conversation_ids
            if (expense_id not in conv_ids or
                    conv_ids[expense_id] != conv_id):
                conv_ids[expense_id] = conv_id
                logger.info(
                    f"[Conversation ID 저장] "
                    f"expense_id: {expense_id}, "
                    f"conversation_id: {conv_id[:50]}..."
                )
            return conv_id
        else:
            logger.warning(
                f"[Conversation ID 추출 실패] "
                f"응답에서 conversation ID를 찾을 수 없음. "
                f"응답: {json.dumps(response_data, ensure_ascii=False)[:500]}..."
            )
            return ""
    except Exception as e:
        logger.error(
            f"[Conversation ID 추출 실패] {str(e)}, "
            f"응답: {json.dumps(response_data, ensure_ascii=False)[:500]}..."
        )
        return ""


def call_audit_agent(expense_id: str) -> str:
    """감사 에이전트 호출 (동기 방식)
    
    첫 호출: message와 conversationId를 빈 값으로 보내고,
    conversation ID만 추출 (응답은 표시하지 않음)
    
    두 번째 호출: conversation ID를 사용하여 expense_id를 메시지로 전송,
    이 응답부터 봇 메시지를 반환
    
    두 번의 호출이 완료되면 더 이상 호출하지 않음
    
    Returns:
        str: 봇 메시지들을 합친 문자열
    """
    # 반복 호출 방지: 이미 호출 중이면 중단
    if st.session_state.api_call_in_progress.get(expense_id, False):
        logger.warning(
            f"[호출 중단] expense_id: {expense_id}, "
            f"이미 호출이 진행 중입니다."
        )
        return "⏳ 이미 호출이 진행 중입니다. 잠시만 기다려주세요."
    
    # 호출 시작 시 이전 플래그 리셋 (재호출 허용)
    if expense_id in st.session_state.conversation_init_failed:
        del st.session_state.conversation_init_failed[expense_id]
    if expense_id in st.session_state.api_call_completed:
        del st.session_state.api_call_completed[expense_id]
    
    # 호출 시작 플래그 설정
    st.session_state.api_call_in_progress[expense_id] = True
    
    try:
        # Conversation ID 조회 (expense_id별로 관리)
        conversation_id = st.session_state.conversation_ids.get(expense_id, "")
        
        # 첫 호출: conversation ID가 없으면 먼저 conversation ID 획득
        if not conversation_id:
            logger.info(
                f"[첫 호출] expense_id: {expense_id}, "
                f"message: 빈 값, conversationId: 빈 값"
            )
            
            try:
                # 첫 호출: message와 conversationId를 빈 값으로
                response_data = _make_api_call("", "", expense_id)
                
                # 응답 전체 로그
                response_str = json.dumps(
                    response_data, ensure_ascii=False
                )[:1000]
                logger.info(
                    f"[첫 호출 응답] expense_id: {expense_id}, "
                    f"응답: {response_str}..."
                )
                
                # Conversation ID 추출
                conversation_id = _extract_conversation_id(
                    response_data, expense_id
                )
                
                if not conversation_id:
                    # 실패 플래그 설정
                    failed = st.session_state.conversation_init_failed
                    failed[expense_id] = True
                    response_str = json.dumps(
                        response_data, ensure_ascii=False
                    )
                    logger.error(
                        f"[첫 호출 실패] expense_id: {expense_id}, "
                        f"Conversation ID를 얻지 못함. "
                        f"전체 응답: {response_str}"
                    )
                    error_msg = (
                        "❌ Conversation ID를 얻지 못했습니다. "
                        "응답을 확인하세요."
                    )
                    # 플래그 해제
                    st.session_state.api_call_in_progress[expense_id] = False
                    return error_msg
                
                logger.info(
                    f"[첫 호출 완료] expense_id: {expense_id}, "
                    f"conversation_id 획득: {conversation_id[:50]}..."
                )
                
            except Exception as e:
                # 실패 플래그 설정
                st.session_state.conversation_init_failed[expense_id] = True
                logger.error(
                    f"[첫 호출 오류] expense_id: {expense_id}, "
                    f"오류: {str(e)}"
                )
                error_msg = f"❌ 첫 호출 오류: {str(e)}"
                # 플래그 해제
                st.session_state.api_call_in_progress[expense_id] = False
                return error_msg
        
        # 두 번째 호출: conversation ID를 사용하여 expense_id를 메시지로 전송
        logger.info(
            f"[두 번째 호출] expense_id: {expense_id}, "
            f"message: {expense_id}, "
            f"conversationId: {conversation_id[:50]}..."
        )
        
        # 두 번째 호출: conversation ID와 expense_id를 메시지로 전송
        response_data = _make_api_call(expense_id, conversation_id, expense_id)
        
        # 응답 파싱 및 봇 메시지 추출
        logger.info(
            f"[두 번째 호출 응답] expense_id: {expense_id}, "
            f"응답 수신 완료"
        )
        
        # 봇 메시지 추출
        result = response_data.get('result', {})
        responses = result.get('responses', [])
        
        seen_message_ids = set()  # 중복 메시지 ID 방지
        bot_messages = []
        last_bot_message = None
        
        # 마지막 BOT 응답 찾기
        for resp in reversed(responses):
            if resp.get('sender') == 'BOT':
                last_bot_message = resp.get('message', '')
                break
        
        # 모든 BOT 메시지 수집
        for resp in responses:
            if resp.get('sender') == 'BOT':
                msg_id = resp.get('id', '')
                message = resp.get('message', '')
                
                if message and msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    bot_messages.append(message)
                    
                    logger.info(
                        f"[봇 메시지 발견] ID: {msg_id}, "
                        f"메시지: {message[:100]}..."
                    )
        
        logger.info(
            f"[응답 완료] expense_id: {expense_id}, "
            f"총 {len(bot_messages)}개 봇 메시지"
        )
        
        # 마지막 메시지에서 위반항목 데이터 추출
        violation_data = None
        if last_bot_message:
            try:
                # message에서 딕셔너리 형태의 문자열 찾기
                # {'success': True, 'columns': [...], 'rows': [...]} 형태
                start_idx = last_bot_message.find("{'success'")
                if start_idx == -1:
                    start_idx = last_bot_message.find('{"success"')
                
                if start_idx != -1:
                    # 딕셔너리 문자열 추출
                    dict_str = last_bot_message[start_idx:]
                    # 닫는 중괄호 찾기
                    brace_count = 0
                    end_idx = -1
                    for i, char in enumerate(dict_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx > 0:
                        dict_str = dict_str[:end_idx]
                        # 문자열을 딕셔너리로 변환
                        violation_data = ast.literal_eval(dict_str)
                        logger.info(
                            f"[위반항목 데이터 추출] expense_id: {expense_id}, "
                            f"columns: {violation_data.get('columns', [])}, "
                            f"rows 수: {len(violation_data.get('rows', []))}"
                        )
            except Exception as e:
                logger.warning(
                    f"[위반항목 파싱 실패] expense_id: {expense_id}, "
                    f"오류: {str(e)}"
                )
        
        # 위반항목 데이터를 세션 상태에 저장
        if violation_data and violation_data.get('success'):
            st.session_state.violation_data = {
                'columns': violation_data.get('columns', []),
                'rows': violation_data.get('rows', [])
            }
        
        # 봇 메시지를 문자열로 합치기
        result_text = "\n".join(bot_messages)
        
        # 완료 메시지 추가
        if bot_messages:
            result_text += "\n\n✅ 응답 완료"
        else:
            result_text = "✅ 응답 완료 (봇 메시지 없음)"
        
        # 두 번째 호출 완료 플래그 설정 (재호출 방지)
        st.session_state.api_call_completed[expense_id] = True
        logger.info(
            f"[호출 완료] expense_id: {expense_id}, "
            f"두 번의 호출이 완료되어 더 이상 호출하지 않음"
        )
        
        return result_text
            
    except requests.exceptions.RequestException as e:
        logger.error(f"[API 호출 오류] {str(e)}")
        return f"❌ API 호출 오류: {str(e)}"
    except Exception as e:
        logger.error(f"[처리 오류] {str(e)}")
        return f"❌ 처리 오류: {str(e)}"
    finally:
        # 호출 완료 플래그 해제 (반복 호출 방지)
        st.session_state.api_call_in_progress[expense_id] = False
        logger.info(
            f"[호출 완료] expense_id: {expense_id}, "
            f"플래그 해제"
        )


def call_clarification_request(expense_id: str) -> str:
    """소명 요청 메일 초안 생성 API 호출
    
    기존 conversation_id를 사용하여 message "YES"를 전송하고,
    응답에서 type이 "llm"인 message를 반환합니다.
    
    Returns:
        str: 메일 초안 내용 (type이 "llm"인 message)
    """
    # Conversation ID 조회
    conversation_id = st.session_state.conversation_ids.get(expense_id, "")
    
    if not conversation_id:
        logger.error(
            f"[소명 요청 실패] expense_id: {expense_id}, "
            f"Conversation ID가 없습니다."
        )
        return ""
    
    try:
        # API 호출: message를 "YES"로 전송
        logger.info(
            f"[소명 요청 호출] expense_id: {expense_id}, "
            f"message: YES, conversationId: {conversation_id[:50]}..."
        )
        
        response_data = _make_api_call("YES", conversation_id, expense_id)
        
        # 응답에서 type이 "llm"인 message 추출
        result = response_data.get('result', {})
        responses = result.get('responses', [])
        
        for resp in responses:
            if resp.get('type') == 'llm' and resp.get('sender') == 'BOT':
                message = resp.get('message', '')
                logger.info(
                    f"[메일 초안 추출] expense_id: {expense_id}, "
                    f"메일 초안 길이: {len(message)}"
                )
                return message
        
        logger.warning(
            f"[메일 초안 없음] expense_id: {expense_id}, "
            f"type이 'llm'인 응답을 찾을 수 없습니다."
        )
        return ""
        
    except Exception as e:
        logger.error(
            f"[소명 요청 오류] expense_id: {expense_id}, "
            f"오류: {str(e)}"
        )
        return ""


def get_audit_result(expense_id: str, stream_content: str = "") -> Dict[str, Any]:
    """감사 에이전트 최종 결과 조회
    
    스트림 응답에서 최종 결과를 파싱하여 반환합니다.
    """
    try:
        # 스트림 내용에서 JSON 데이터 추출 시도
        result_data = {}
        bot_message_text = ""
        
        if stream_content:
            # JSON 형식의 데이터 찾기
            try:
                # 마지막 완전한 JSON 객체 찾기
                lines = stream_content.split('\n')
                for line in reversed(lines):
                    line_stripped = line.strip()
                    if (line_stripped.startswith('{') or
                            line_stripped.startswith('[')):
                        try:
                            result_data = json.loads(line_stripped)
                            # 봇 메시지 추출
                            bot_message_text = extract_bot_message(result_data)
                            break
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
        
        # API 응답에서 결과 추출 및 구조화
        # 응답 구조에 맞게 조정 필요 (실제 API 응답 형식에 따라 수정)
        return {
            "expense_id": expense_id,
            "expense_details": result_data.get('expense_details', {}),
            "analysis": result_data.get('analysis', {}),
            "receipt_image_url": result_data.get(
                'receipt_image_url', 'sample.png'
            ),
            "rejection_email_draft": result_data.get(
                'rejection_email_draft', ''
            ),
            "api_response": result_data,  # 전체 응답도 포함
            "stream_content": stream_content,  # 스트림 전체 내용
            "bot_message": bot_message_text  # 봇 메시지
        }
    except Exception as e:
        st.error(f"결과 처리 오류: {str(e)}")
        # 오류 발생 시 목업 데이터 반환
        st.warning("결과 처리 중 오류가 발생하여 목업 데이터를 표시합니다.")
        return get_mock_audit_result(expense_id)


def get_mock_audit_result(expense_id: str) -> Dict[str, Any]:
    """목업: 감사 에이전트 최종 결과 (백업용)"""
    return {
        "expense_id": expense_id,
        "expense_details": {
            "user_name": "홍길동",
            "amount": 245000,
            "business_name": "서울 비즈니스 호텔",
            "business_type": "숙박",
            "payment_datetime": "2024-02-10",
            "attendees_count": 1,
            "card_type": "법인카드"
        },
        "analysis": {
            "compliance_status": "적합",
            "findings": [
                "✅ 영수증 금액과 신청 금액 일치",
                "✅ 출장 신청서와 날짜 일치",
                "✅ 숙박비 상한액 내 지출 (1박당 300,000원 이하)",
                "✅ 영수증 이미지 품질 양호",
                ("⚠️ 참고: 호텔 등급이 비교적 높은 편이나 "
                 "규정 내 범위임")
            ],
            "recommendation": "승인",
            "risk_level": "낮음",
            "confidence": 0.95
        },
        "receipt_image_url": "sample.png",
        "rejection_email_draft": """
제목: [법인카드 정산 반려] {expense_id} - {business_name}

{user_name}님께,

안녕하세요. 경영지원팀입니다.

제출하신 법인카드 정산 건({expense_id})을 검토한 결과, 다음과 같은 사유로 반려 처리되었습니다:

[반려 사유]
- (여기에 반려 사유가 표시됩니다)

정산을 다시 제출하시려면 아래 사항을 확인해 주시기 바랍니다:
1. 영수증 이미지의 명확성 확인
2. 정산 금액과 영수증 금액 일치 여부
3. 사내 정산 규정 준수 여부

문의사항이 있으시면 경영지원팀으로 연락 주시기 바랍니다.

감사합니다.
"""
    }


def call_process_agent(
    expense_id: str,
    decision: str,
    email_confirmed: bool = False
) -> Dict[str, Any]:
    """목업: 정산 처리 에이전트 호출

    실제 연동 시:
    - 정산 처리 에이전트 호출
    - 승인/반려 처리 및 메일 발송
    """
    time.sleep(1)  # API 호출 시뮬레이션
    
    if decision == "승인":
        return {
            "success": True,
            "expense_id": expense_id,
            "decision": decision,
            "message": "정산이 승인되었습니다.",
            "processed_at": datetime.now().isoformat(),
            "notification_sent": True
        }
    else:  # 반려
        return {
            "success": True,
            "expense_id": expense_id,
            "decision": decision,
            "message": "정산이 반려되었습니다.",
            "processed_at": datetime.now().isoformat(),
            "email_sent": email_confirmed,
            "notification_sent": True
        }


# ============================================================================
# Session State 초기화
# ============================================================================

if 'page' not in st.session_state:
    st.session_state.page = 'list'  # 'list' 또는 'detail'

if 'selected_expense_id' not in st.session_state:
    st.session_state.selected_expense_id = None

if 'audit_result' not in st.session_state:
    st.session_state.audit_result = None

if 'stream_complete' not in st.session_state:
    st.session_state.stream_complete = False

# 다이얼로그 관련 상태
if 'show_review_dialog' not in st.session_state:
    st.session_state.show_review_dialog = False

# 검토 완료 플래그 (expense_id별로 관리)
if 'review_complete' not in st.session_state:
    st.session_state.review_complete = {}

# Conversation ID 관리 (expense_id별로 저장)
if 'conversation_ids' not in st.session_state:
    st.session_state.conversation_ids = {}

# 첫 호출 실패 플래그 (expense_id별로 관리)
if 'conversation_init_failed' not in st.session_state:
    st.session_state.conversation_init_failed = {}

# 호출 중 플래그 (expense_id별로 관리, 반복 호출 방지)
if 'api_call_in_progress' not in st.session_state:
    st.session_state.api_call_in_progress = {}

# 호출 완료 플래그 (expense_id별로 관리, 재호출 방지)
if 'api_call_completed' not in st.session_state:
    st.session_state.api_call_completed = {}

# 위반항목 데이터 저장
if 'violation_data' not in st.session_state:
    st.session_state.violation_data = None

# 소명 요청 메일 초안 저장
if 'clarification_email_draft' not in st.session_state:
    st.session_state.clarification_email_draft = None

# 메일 전송 완료 플래그
if 'mail_sent' not in st.session_state:
    st.session_state.mail_sent = False


# ============================================================================
# 페이지 1: 법인카드 정산 목록
# ============================================================================

def show_expense_list():
    """법인카드 정산 목록 화면"""
    st.markdown('<p class="main-header">💳 법인카드 정산 검토 시스템</p>', unsafe_allow_html=True)
    
    # 새로고침 버튼
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    st.markdown("---")
    
    # 정산 목록 조회 (DB에서 조회)
    expenses = get_expense_list()
    
    # 통계 정보
    st.markdown("### 📊 검토 대기 현황")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("전체 건수", len(expenses))
    with col2:
        total_amount = sum(exp['amount'] for exp in expenses)
        st.metric("총 금액", f"{total_amount:,}원")
    with col3:
        st.metric("평균 금액", f"{int(total_amount/len(expenses)):,}원")
    with col4:
        st.metric("대기 기간", "1-5일")
    
    st.markdown("---")
    st.markdown("### 📋 정산 목록")
    
    # 정산 ID를 줄여서 표시하는 함수
    def truncate_id(expense_id: str, max_length: int = 8) -> str:
        """정산 ID를 일부만 표시하고 ...으로 줄임"""
        if not expense_id:
            return ''
        if len(expense_id) <= max_length:
            return expense_id
        return expense_id[:max_length] + '...'
    
    # 정산 목록을 테이블로 표시
    st.markdown("""
    <style>
    .dataframe {
        font-size: 0.875rem;
    }
    .dataframe th {
        background-color: #1f77b4;
        color: white;
        font-weight: bold;
        padding: 10px;
        text-align: center;
    }
    .dataframe td {
        padding: 10px;
        text-align: center;
        border-bottom: 1px solid #ddd;
    }
    .dataframe tr {
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .dataframe tr:hover {
        background-color: #e3f2fd;
        transform: scale(1.01);
    }
    .dataframe tr.selected {
        background-color: #1976d2 !important;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 테이블 데이터 준비 (정산 ID는 전체 표시)
    table_data = []
    for expense in expenses:
        expense_id = expense.get('id', '')
        table_data.append({
            "정산 ID": expense_id,
            "신청자": expense.get('user_name', ''),
            "가맹점": expense.get('business_name', ''),
            "분류": expense.get('business_type', ''),
            "금액": f"{expense.get('amount', 0):,}원",
            "사용일": expense.get('payment_datetime', '')
        })
    
    # 데이터프레임 생성
    df = pd.DataFrame(table_data)
    
    # 테이블 표시 (행 선택 가능)
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # 행이 선택되었는지 확인
    if len(event.selection.rows) > 0:
        selected_row_idx = event.selection.rows[0]
        if selected_row_idx < len(expenses):
            expense_id = expenses[selected_row_idx].get('id', '')
            st.session_state.selected_expense_id = expense_id
            st.session_state.show_review_dialog = True
            # 검토 완료 플래그는 expense_id별로 관리하므로 여기서는 리셋하지 않음
    
    # 상세 검토 다이얼로그
    if st.session_state.get('show_review_dialog', False):
        selected_id = st.session_state.selected_expense_id
        show_review_dialog(selected_id)


# ============================================================================
# 다이얼로그: 검토 진행 상황
# ============================================================================

@st.dialog("🔍 정산 상세 검토", width="large")
def show_review_dialog(expense_id: str):
    """검토 진행 상황을 다이얼로그로 표시"""
    
    st.markdown(f"### 정산 ID: {expense_id}")
    st.markdown("---")
    
    # 검토 진행 상황 표시
    review_complete = st.session_state.review_complete.get(expense_id, False)
    
    if not review_complete:
        # API 호출 및 결과 수신 (스피너 표시)
        with st.spinner("🤖 AI 감사 에이전트 분석 중..."):
            try:
                result_content = call_audit_agent(expense_id)
                
                # 최종 결과 파싱
                st.session_state.audit_result = get_audit_result(
                    expense_id, result_content
                )
                # 검토 완료 플래그 설정 (expense_id별)
                st.session_state.review_complete[expense_id] = True
            except Exception as e:
                st.error(f"처리 오류: {str(e)}")
                # 오류 발생 시 목업 데이터 사용
                audit_result = get_mock_audit_result(expense_id)
                st.session_state.audit_result = audit_result
                st.session_state.review_complete[expense_id] = True
                st.rerun()
    
    # 검토 완료 후 버튼만 표시
    if st.session_state.review_complete.get(expense_id, False):
        st.success("✅ 검토가 완료되었습니다!")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "📊 상세 결과 보기",
                key=f"detail_btn_{expense_id}",
                use_container_width=True
            ):
                st.session_state.page = 'detail'
                st.session_state.stream_complete = True
                st.session_state.show_review_dialog = False
                st.rerun()
        
        with col2:
            if st.button(
                "❌ 닫기",
                key=f"close_btn_{expense_id}",
                use_container_width=True
            ):
                st.session_state.show_review_dialog = False
                # 검토 완료 플래그는 expense_id별로 관리하므로 여기서는 리셋하지 않음
                st.rerun()


# ============================================================================
# 페이지 2: 정산 상세 검토
# ============================================================================

def show_expense_detail():
    """정산 상세 검토 결과 화면 (다이얼로그에서 '상세 결과 보기' 클릭 시)"""
    expense_id = st.session_state.selected_expense_id
    
    # 뒤로가기 버튼
    if st.button("⬅️ 목록으로 돌아가기"):
        st.session_state.page = 'list'
        st.session_state.selected_expense_id = None
        st.session_state.stream_complete = False
        st.session_state.audit_result = None
        # review_complete는 expense_id별로 관리하므로 여기서는 리셋하지 않음
        st.rerun()
    
    header_html = f'<p class="main-header">📊 상세 검토 결과: {expense_id}</p>'
    st.markdown(header_html, unsafe_allow_html=True)
    st.markdown("---")
    
    # DB에서 실제 정산 정보 조회
    expense_data = get_expense_detail(expense_id)
    
    if not expense_data:
        st.error("정산 정보를 찾을 수 없습니다.")
        return
    
    # 검토 결과 표시 (이미 완료된 상태)
    if st.session_state.audit_result:
        st.success("✅ 검토가 완료되었습니다!")
        st.markdown("---")
        
        # 2단 레이아웃: 정산 정보 | 영수증
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📄 정산 정보")
            st.markdown(f"""
            **정산 ID:** {expense_data.get('id', '')}  
            **신청자:** {expense_data.get('user_name', '')}  
            **금액:** {expense_data.get('amount', 0):,}원  
            **가맹점:** {expense_data.get('business_name', '')}  
            **분류:** {expense_data.get('business_type', '')}  
            **사용일:** {expense_data.get('payment_datetime', '')}  
            **참석자 수:** {expense_data.get('attendees_count', 0)}  
            **카드 타입:** {expense_data.get('card_type', '')}
            """)
        
        with col2:
            st.markdown("### 🧾 영수증")
            # 정산 ID에 해당하는 PNG 파일 경로 가져오기
            receipt_path = get_receipt_path(expense_id)
            if receipt_path:
                display_png(receipt_path)
            else:
                st.error("영수증을 찾을 수 없습니다.")
        
        st.markdown("---")
        
        # 위반 항목 표
        st.markdown("### 📋 위반 항목")
        
        # DB에서 위반 항목 조회
        violations = get_violations(expense_id)
        
        if violations:
            # 표 데이터 준비
            violation_data = []
            for idx, violation in enumerate(violations, start=1):
                violation_data.append({
                    "No": idx,
                    "위반항목": violation['violation_type'],
                    "내용": violation['description'],
                    "참조 규정": violation['reference']
                })
            
            # 데이터프레임으로 표시
            violation_df = pd.DataFrame(violation_data)
            st.dataframe(
                violation_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("위반 항목이 없습니다.")
        
        st.markdown("---")
        
        # 소명 요청 버튼
        st.markdown("### ✅ 최종 결정")
        col1, col2, col3 = st.columns([1, 2, 2])
        
        with col1:
            if st.button(
                "📝 소명 요청",
                key="clarification_btn",
                use_container_width=True
            ):
                st.session_state.show_clarification_popup = True
                st.session_state.clarification_email_draft = None
                st.rerun()
        
        # 소명 요청 메일 팝업
        if st.session_state.get('show_clarification_popup', False):
            st.markdown("---")
            st.markdown("### 📧 소명 요청 메일")
            
            # 메일 초안이 없으면 API 호출
            if st.session_state.get('clarification_email_draft') is None:
                with st.spinner("메일 초안 생성 중..."):
                    try:
                        email_draft = call_clarification_request(expense_id)
                        if email_draft:
                            st.session_state.clarification_email_draft = (
                                email_draft
                            )
                        else:
                            st.error("메일 초안을 생성할 수 없습니다.")
                            st.session_state.show_clarification_popup = False
                            st.rerun()
                    except Exception as e:
                        st.error(f"메일 초안 생성 오류: {str(e)}")
                        st.session_state.show_clarification_popup = False
                        st.rerun()
            
            # 메일 초안 표시
            clarification_email = st.session_state.get(
                'clarification_email_draft', ''
            )
            
            st.text_area(
                "메일 내용",
                value=clarification_email,
                height=400,
                disabled=True
            )
            
            # 전송 완료 여부 확인
            if st.session_state.get('mail_sent', False):
                st.success("✅ 메일 전송이 완료되었습니다.")
                st.markdown("---")
                
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    confirm_btn = st.button(
                        "확인",
                        key="confirm_mail_sent",
                        use_container_width=True
                    )
                    if confirm_btn:
                        # 목록으로 돌아가기
                        st.session_state.page = 'list'
                        st.session_state.selected_expense_id = None
                        st.session_state.stream_complete = False
                        st.session_state.audit_result = None
                        st.session_state.show_clarification_popup = False
                        st.session_state.review_complete = {}
                        st.session_state.clarification_email_draft = None
                        st.session_state.mail_sent = False
                        st.rerun()
            else:
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    send_btn = st.button(
                        "📤 전송",
                        key="send_clarification",
                        use_container_width=True
                    )
                    if send_btn:
                        with st.spinner("메일 전송 중..."):
                            try:
                                # Conversation ID 조회
                                conv_ids = st.session_state.conversation_ids
                                conversation_id = conv_ids.get(expense_id, "")
                                
                                if not conversation_id:
                                    st.error("Conversation ID가 없습니다.")
                                    st.rerun()
                                    return
                                
                                # API 호출: message를 "YES"로 전송
                                logger.info(
                                    f"[메일 전송 호출] expense_id: {expense_id}, "
                                    f"message: YES, conversationId: "
                                    f"{conversation_id[:50]}..."
                                )
                                
                                # 응답 파싱 불필요, 호출만 수행
                                _make_api_call(
                                    "YES", conversation_id, expense_id
                                )
                                
                                logger.info(
                                    f"[메일 전송 완료] expense_id: {expense_id}, "
                                    f"응답 수신 완료"
                                )
                                
                                # 전송 완료 플래그 설정
                                st.session_state.mail_sent = True
                                st.rerun()
                                
                            except Exception as e:
                                logger.error(
                                    f"[메일 전송 오류] expense_id: {expense_id}, "
                                    f"오류: {str(e)}"
                                )
                                st.error(f"메일 전송 오류: {str(e)}")
                
                with col2:
                    cancel_btn = st.button(
                        "취소",
                        key="cancel_clarification",
                        use_container_width=True
                    )
                    if cancel_btn:
                        st.session_state.show_clarification_popup = False
                        st.session_state.clarification_email_draft = None
                        st.rerun()


# ============================================================================
# 메인 라우팅
# ============================================================================

def main():
    """메인 애플리케이션"""
    
    if st.session_state.page == 'list':
        show_expense_list()
    elif st.session_state.page == 'detail':
        show_expense_detail()


if __name__ == "__main__":
    main()
