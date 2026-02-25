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

# ページ設定
st.set_page_config(
    page_title="法人カード精算審査システム",
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
    """PostgreSQL データベース接続"""
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
        st.error(f"データベース接続エラー: {str(e)}")
        return None


def get_expense_list():
    """法人カード精算一覧照会（DB から全件取得）"""
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
        st.error(f"データ取得エラー: {str(e)}")
        return []
    finally:
        conn.close()


def get_violations(expense_id: str) -> list:
    """violations テーブルから該当精算 ID の違反項目を取得
    
    Args:
        expense_id: 精算 ID
    
    Returns:
        違反項目のリスト
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
        st.error(f"違反項目の取得エラー: {str(e)}")
        return []
    finally:
        conn.close()


def get_expense_detail(expense_id: str) -> Dict[str, Any]:
    """特定精算 ID の詳細情報を取得
    
    Args:
        expense_id: 精算 ID
    
    Returns:
        精算詳細情報のディクショナリ
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
        st.error(f"精算詳細の取得エラー: {str(e)}")
        return None
    finally:
        conn.close()


def get_receipt_path(expense_id: str) -> str:
    """精算 ID に対応する領収書 PNG ファイルパスを取得
    
    Args:
        expense_id: 精算 ID
    
    Returns:
        領収書 PNG ファイルの絶対パス（文字列）
    """
    png_path = RECEIPT_DATA_DIR / f"{expense_id}.png"
    
    if png_path.exists():
        return str(png_path)
    else:
        # ファイルがない場合は None を返す
        st.warning(f"領収書ファイルが見つかりません: {expense_id}.png")
        return None


def display_png(file_path: str):
    """PNG ファイルを画像として表示
    
    Args:
        file_path: PNG ファイルパス
    """
    if file_path and Path(file_path).exists():
        st.image(file_path, use_container_width=True)
    else:
        st.error("領収書ファイルが見つかりません。")


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
    """応答から conversation ID を抽出"""
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
                f"응답에서 conversation ID를 찾을 수 없습니다. "
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
    
    1차 호출: message와 conversationId를 비운 상태로 보내 conversation ID만 확보합니다.
    2차 호출: 확보한 conversation ID를 사용해 expense_id를 message로 전송하고,
    그 응답에서 BOT 메시지를 반환합니다.
    
    두 번의 호출이 완료되면 더 이상 호출하지 않습니다.
    
    Returns:
        str: BOT 메시지들을 합친 문자열
    """
    # 반복 호출 방지: 이미 호출 중이면 중단
    if st.session_state.api_call_in_progress.get(expense_id, False):
        logger.warning(
            f"[호출 중단] expense_id: {expense_id}, "
            f"이미 호출이 진행 중입니다."
        )
        return "⏳ すでに呼び出しが進行中です。しばらくお待ちください。"
    
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
                f"[1回目呼び出し] expense_id: {expense_id}, "
                f"message: 空, conversationId: 空"
            )
            
            try:
                # 첫 호출: message와 conversationId를 빈 값으로
                response_data = _make_api_call("", "", expense_id)
                
                # 응답 전체 로그
                response_str = json.dumps(
                    response_data, ensure_ascii=False
                )[:1000]
                logger.info(
                    f"[1回目応答] expense_id: {expense_id}, "
                    f"レスポンス: {response_str}..."
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
                        f"[1回目失敗] expense_id: {expense_id}, "
                        f"Conversation ID を取得できませんでした。 "
                        f"全レスポンス: {response_str}"
                    )
                    error_msg = (
                        "❌ Conversation ID を取得できませんでした。"
                        "レスポンスを確認してください."
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
                    f"[1回目エラー] expense_id: {expense_id}, "
                    f"エラー: {str(e)}"
                )
                error_msg = f"❌ 1回目呼び出しエラー: {str(e)}"
                # 플래그 해제
                st.session_state.api_call_in_progress[expense_id] = False
                return error_msg
        
        # 두 번째 호출: conversation ID를 사용하여 expense_id를 메시지로 전송
        logger.info(
            f"[2回目呼び出し] expense_id: {expense_id}, "
            f"message: {expense_id}, "
            f"conversationId: {conversation_id[:50]}..."
        )
        
        # 두 번째 호출: conversation ID와 expense_id를 메시지로 전송
        response_data = _make_api_call(expense_id, conversation_id, expense_id)
        
        # 응답 파싱 및 BOT 메시지 추출
        logger.info(
            f"[2回目応答] expense_id: {expense_id}, "
            f"レスポンス受信完了"
        )
        
        # BOT 메시지 추출
        result = response_data.get('result', {})
        responses = result.get('responses', [])
        
        seen_message_ids = set()  # 중복 메세지 ID 방지
        bot_messages = []
        last_bot_message = None
        
        # 마지막 BOT 응답 찾기
        for resp in reversed(responses):
            if resp.get('sender') == 'BOT':
                last_bot_message = resp.get('message', '')
                break
        
        # 모든 BOT 메세지 수집
        for resp in responses:
            if resp.get('sender') == 'BOT':
                msg_id = resp.get('id', '')
                message = resp.get('message', '')
                
                if message and msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    bot_messages.append(message)
                    
                    logger.info(
                        f"[BOT メッセージ検出] ID: {msg_id}, "
                        f"メッセージ: {message[:100]}..."
                    )
        
        logger.info(
            f"[応答完了] expense_id: {expense_id}, "
            f"合計 {len(bot_messages)} 件の BOT メッセージ"
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
                    # ディクショナリ文字列を抽出
                    dict_str = last_bot_message[start_idx:]
                    # 閉じカッコを探索
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
        
        # BOT 메세지를 하나의 문자열로 결합
        result_text = "\n".join(bot_messages)
        
        # 완료 메세지 추가
        if bot_messages:
            result_text += "\n\n✅ 応答完了"
        else:
            result_text = "✅ 応答完了（BOT メッセージなし）"
        
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
    
    기존 conversation_id를 사용하여 message \"YES\"를 전송하고,
    응답에서 type이 \"llm\"인 message를 반환합니다.
    
    Returns:
        str: 메일 초안 내용 (type이 \"llm\"인 message)
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
        # API 호출: message를 \"YES\"로 전송
        logger.info(
            f"[소명 요청 호출] expense_id: {expense_id}, "
            f"message: YES, conversationId: {conversation_id[:50]}..."
        )
        
        response_data = _make_api_call("YES", conversation_id, expense_id)
        
        # 응답에서 type이 \"llm\"인 message를 추출
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
    """監査エージェント最終結果の取得
    
    ストリーム応答から最終結果をパースして返します。
    """
    try:
        # 스트림 내용에서 JSON 데이터 추출 시도
        result_data = {}
        bot_message_text = ""
        
        if stream_content:
            # JSON 形式のデータ探索
            try:
                # 最後の完全な JSON オブジェクトを探す
                lines = stream_content.split('\n')
                for line in reversed(lines):
                    line_stripped = line.strip()
                    if (line_stripped.startswith('{') or
                            line_stripped.startswith('[')):
                        try:
                            result_data = json.loads(line_stripped)
                            # BOT メッセージ抽出
                            bot_message_text = extract_bot_message(result_data)
                            break
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
        
        # API 応答から結果を抽出し構造化
        # 実際の API 応答形式に合わせて調整が必要
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
            "api_response": result_data,  # 全応答も含む
            "stream_content": stream_content,  # ストリーム全体
            "bot_message": bot_message_text  # BOT メッセージ
        }
    except Exception as e:
        st.error(f"結果処理エラー: {str(e)}")
        # エラー時は空データを返す
        st.warning("結果処理中にエラーが発生しました。")
        return {
            "expense_id": expense_id,
            "expense_details": {},
            "analysis": {},
            "receipt_image_url": "",
            "rejection_email_draft": "",
            "api_response": {},
            "stream_content": stream_content,
            "bot_message": ""
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
    """法人カード精算一覧画面"""
    st.markdown('<p class="main-header">💳 法人カード精算審査システム</p>', unsafe_allow_html=True)
    
    # 更新ボタン
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 再読み込み"):
            st.rerun()
    
    st.markdown("---")
    
    # 精算一覧取得（DB から取得）
    expenses = get_expense_list()
    
    # 統計情報
    st.markdown("### 📊 審査待ち状況")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("件数（合計）", len(expenses))
    with col2:
        total_amount = sum(exp['amount'] for exp in expenses)
        st.metric("金額合計", f"{total_amount:,}円")
    with col3:
        st.metric("平均金額", f"{int(total_amount/len(expenses)):,}円")
    with col4:
        st.metric("待機期間", "1〜5日")
    
    st.markdown("---")
    st.markdown("### 📋 精算一覧")
    
    # 精算 ID を短縮表示する関数
    def truncate_id(expense_id: str, max_length: int = 8) -> str:
        """精算 ID を一部だけ表示し … で省略する"""
        if not expense_id:
            return ''
        if len(expense_id) <= max_length:
            return expense_id
        return expense_id[:max_length] + '...'
    
    # 精算一覧をテーブル表示
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
    
    # テーブルデータ準備（精算 ID はフル表示）
    table_data = []
    for expense in expenses:
        expense_id = expense.get('id', '')
        table_data.append({
            "精算 ID": expense_id,
            "申請者": expense.get('user_name', ''),
            "加盟店": expense.get('business_name', ''),
            "分類": expense.get('business_type', ''),
            "金額": f"{expense.get('amount', 0):,}円",
            "利用日": expense.get('payment_datetime', '')
        })
    
    # データフレーム生成
    df = pd.DataFrame(table_data)
    
    # テーブル表示（行選択可能）
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # 行が選択されているか確認
    if len(event.selection.rows) > 0:
        selected_row_idx = event.selection.rows[0]
        if selected_row_idx < len(expenses):
            expense_id = expenses[selected_row_idx].get('id', '')
            st.session_state.selected_expense_id = expense_id
            st.session_state.show_review_dialog = True
            # 審査完了フラグは expense_id ごとに管理するためここではリセットしない
    
    # 詳細審査ダイアログ
    if st.session_state.get('show_review_dialog', False):
        selected_id = st.session_state.selected_expense_id
        show_review_dialog(selected_id)


# ============================================================================
# 다이얼로그: 검토 진행 상황
# ============================================================================

@st.dialog("🔍 精算詳細審査", width="large")
def show_review_dialog(expense_id: str):
    """審査進捗をダイアログで表示"""
    
    st.markdown(f"### 精算 ID: {expense_id}")
    st.markdown("---")
    
    # 審査進捗表示
    review_complete = st.session_state.review_complete.get(expense_id, False)
    
    if not review_complete:
        # API 呼び出しと結果受信（スピナー表示）
        with st.spinner("🤖 AI 監査エージェント分析中..."):
            try:
                result_content = call_audit_agent(expense_id)
                
                # 최종 결과 파싱
                st.session_state.audit_result = get_audit_result(
                    expense_id, result_content
                )
                # 審査完了フラグ設定（expense_id ごと）
                st.session_state.review_complete[expense_id] = True
            except Exception as e:
                st.error(f"処理エラー: {str(e)}")
                # エラー発生時は空の結果を設定
                st.session_state.audit_result = get_audit_result(
                    expense_id, ""
                )
                st.session_state.review_complete[expense_id] = True
                st.rerun()
    
    # 審査完了後はボタンのみ表示
    if st.session_state.review_complete.get(expense_id, False):
        st.success("✅ 審査が完了しました。")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "📊 詳細結果を見る",
                key=f"detail_btn_{expense_id}",
                use_container_width=True
            ):
                st.session_state.page = 'detail'
                st.session_state.stream_complete = True
                st.session_state.show_review_dialog = False
                st.rerun()
        
        with col2:
            if st.button(
                "❌ 閉じる",
                key=f"close_btn_{expense_id}",
                use_container_width=True
            ):
                st.session_state.show_review_dialog = False
                # 審査完了フラグは expense_id ごとに管理するためここではリセットしない
                st.rerun()


# ============================================================================
# 페이지 2: 정산 상세 검토
# ============================================================================

def show_expense_detail():
    """精算詳細審査結果画面（ダイアログで「詳細結果を見る」クリック時）"""
    expense_id = st.session_state.selected_expense_id
    
    # 戻るボタン
    if st.button("⬅️ 一覧に戻る"):
        st.session_state.page = 'list'
        st.session_state.selected_expense_id = None
        st.session_state.stream_complete = False
        st.session_state.audit_result = None
        # review_complete는 expense_id별로 관리하므로 여기서는 리셋하지 않음
        st.rerun()
    
    header_html = f'<p class="main-header">📊 詳細審査結果: {expense_id}</p>'
    st.markdown(header_html, unsafe_allow_html=True)
    st.markdown("---")
    
    # DB から実際の精算情報を取得
    expense_data = get_expense_detail(expense_id)
    
    if not expense_data:
        st.error("精算情報が見つかりません。")
        return
    
    # 審査結果表示（すでに完了済み）
    if st.session_state.audit_result:
        st.success("✅ 審査が完了しました。")
        st.markdown("---")
        
        # 2カラムレイアウト: 精算情報 | 領収書
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📄 精算情報")
            st.markdown(f"""
            **精算 ID:** {expense_data.get('id', '')}  
            **申請者:** {expense_data.get('user_name', '')}  
            **金額:** {expense_data.get('amount', 0):,}円  
            **加盟店:** {expense_data.get('business_name', '')}  
            **分類:** {expense_data.get('business_type', '')}  
            **利用日:** {expense_data.get('payment_datetime', '')}  
            **参加者数:** {expense_data.get('attendees_count', 0)}  
            **カード種別:** {expense_data.get('card_type', '')}
            """)
        
        with col2:
            st.markdown("### 🧾 領収書")
            # 精算 ID に対応する PNG ファイルパス取得
            receipt_path = get_receipt_path(expense_id)
            if receipt_path:
                display_png(receipt_path)
            else:
                st.error("領収書が見つかりません。")
        
        st.markdown("---")
        
        # 違反項目テーブル
        st.markdown("### 📋 違反項目")
        
        # DB から違反項目取得
        violations = get_violations(expense_id)
        
        if violations:
            # 表データ準備
            violation_data = []
            for idx, violation in enumerate(violations, start=1):
                violation_data.append({
                    "No": idx,
                    "違反項目": violation['violation_type'],
                    "内容": violation['description'],
                    "参照規程": violation['reference']
                })
            
            # データフレームで表示
            violation_df = pd.DataFrame(violation_data)
            st.dataframe(
                violation_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("違反項目はありません。")
        
        st.markdown("---")
        
        # 説明依頼ボタン
        st.markdown("### ✅ 最終判断")
        col1, col2, col3 = st.columns([1, 2, 2])
        
        with col1:
            if st.button(
                "📝 説明依頼",
                key="clarification_btn",
                use_container_width=True
            ):
                st.session_state.show_clarification_popup = True
                st.session_state.clarification_email_draft = None
                st.rerun()
        
        # 説明依頼メールポップアップ
        if st.session_state.get('show_clarification_popup', False):
            st.markdown("---")
            st.markdown("### 📧 説明依頼メール")
            
            # メール下書きがなければ API 呼び出し
            if st.session_state.get('clarification_email_draft') is None:
                with st.spinner("メール下書き生成中..."):
                    try:
                        email_draft = call_clarification_request(expense_id)
                        if email_draft:
                            st.session_state.clarification_email_draft = (
                                email_draft
                            )
                        else:
                            st.error("メール下書きを生成できません。")
                            st.session_state.show_clarification_popup = False
                            st.rerun()
                    except Exception as e:
                        st.error(f"メール下書き生成エラー: {str(e)}")
                        st.session_state.show_clarification_popup = False
                        st.rerun()
            
            # メール下書き表示
            clarification_email = st.session_state.get(
                'clarification_email_draft', ''
            )
            
            st.text_area(
                "メール内容",
                value=clarification_email,
                height=400,
                disabled=True
            )
            
            # 送信完了かどうか確認
            if st.session_state.get('mail_sent', False):
                st.success("✅ メール送信が完了しました。")
                st.markdown("---")
                
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    confirm_btn = st.button(
                        "確認",
                        key="confirm_mail_sent",
                        use_container_width=True
                    )
                    if confirm_btn:
                        # 一覧に戻る
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
                        "📤 送信",
                        key="send_clarification",
                        use_container_width=True
                    )
                    if send_btn:
                        with st.spinner("メール送信中..."):
                            try:
                                # Conversation ID 조회
                                conv_ids = st.session_state.conversation_ids
                                conversation_id = conv_ids.get(expense_id, "")
                                
                                if not conversation_id:
                                    st.error("Conversation ID がありません。")
                                    st.rerun()
                                    return
                                
                                # API 呼び出し: message として "YES" を送信
                                logger.info(
                                    f"[メール送信呼び出し] expense_id: {expense_id}, "
                                    f"message: YES, conversationId: "
                                    f"{conversation_id[:50]}..."
                                )
                                
                                # 応答のパースは不要、呼び出しのみ実施
                                _make_api_call(
                                    "YES", conversation_id, expense_id
                                )
                                
                                logger.info(
                                    f"[メール送信完了] expense_id: {expense_id}, "
                                    f"応答受信完了"
                                )
                                
                                # 送信完了フラグ設定
                                st.session_state.mail_sent = True
                                st.rerun()
                                
                            except Exception as e:
                                logger.error(
                                    f"[メール送信エラー] expense_id: {expense_id}, "
                                    f"エラー: {str(e)}"
                                )
                                st.error(f"メール送信エラー: {str(e)}")
                
                with col2:
                    cancel_btn = st.button(
                        "キャンセル",
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
