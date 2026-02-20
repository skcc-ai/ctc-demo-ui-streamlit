#!/usr/bin/env python3
"""법인카드 정산 검토 시스템 - Streamlit App"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Dict, Any, Generator
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from pathlib import Path
import base64

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
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        min-height: 200px;
        max-height: 400px;
        overflow-y: auto;
        font-family: monospace;
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
    """정산 ID에 해당하는 영수증 PDF 파일 경로 가져오기
    
    Args:
        expense_id: 정산 ID
    
    Returns:
        영수증 PDF 파일의 절대 경로 (문자열)
    """
    pdf_path = RECEIPT_DATA_DIR / f"{expense_id}.pdf"
    
    if pdf_path.exists():
        return str(pdf_path)
    else:
        # 파일이 없으면 None 반환
        st.warning(f"영수증 파일을 찾을 수 없습니다: {expense_id}.pdf")
        return None


def display_pdf(file_path: str):
    """PDF 파일을 iframe으로 표시
    
    Args:
        file_path: PDF 파일 경로
    """
    if file_path and Path(file_path).exists():
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        pdf_display = f'''
            <iframe src="data:application/pdf;base64,{base64_pdf}" 
                    width="100%" height="800" type="application/pdf"
                    style="border: 2px solid #ddd; border-radius: 8px;">
            </iframe>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.error("영수증 파일을 찾을 수 없습니다.")


def call_audit_agent_mcp(
    expense_id: str,
    username: str = "skax_10071",
    password: str = "skax_10071!1",
    project: str = "CTC-STG"
) -> Dict[str, Any]:
    """MCP API를 통해 감사 에이전트 호출
    
    Args:
        expense_id: 정산 ID
        username: Master AI 로그인 사용자 ID
        password: Master AI 로그인 비밀번호
        project: 프로젝트명
    
    Returns:
        API 응답 결과
    """
    url = "https://ctc-dify-stg.skax.co.kr/mcp-app/servers/master_agent/tools/expense_audit_agent/call"
    
    payload = {
        "query": expense_id,
        "username": username,
        "password": password,
        "project": project
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"MCP API 호출 오류: {str(e)}")
        return {"success": False, "error": str(e)}


def call_audit_agent_stream(
    expense_id: str
) -> Generator[str, None, None]:
    """감사 에이전트 호출 (스트림 응답)
    
    MCP API를 호출하여 실시간으로 진행 상황을 표시합니다.
    """
    messages = [
        "🔍 감사 에이전트를 호출하고 있습니다...",
        f"\n✅ 정산 ID: {expense_id}",
        "\n📋 정산 정보를 조회하고 있습니다...",
        "\n🔎 영수증 이미지를 분석하고 있습니다...",
        "\n📊 사내 정산 규정을 확인하고 있습니다...",
        "\n🤖 AI 에이전트가 종합 분석 중...",
        "\n⏳ 잠시만 기다려주세요..."
    ]
    
    for msg in messages:
        time.sleep(1)
        yield msg


def get_audit_result(expense_id: str) -> Dict[str, Any]:
    """감사 에이전트 최종 결과 조회
    
    MCP API를 호출하여 실제 결과를 가져옵니다.
    """
    # [검증용] 실제 에이전트 호출 주석처리
    # MCP API 호출
    # api_response = call_audit_agent_mcp(expense_id)
    # 
    # if not api_response.get('success', False):
    #     # API 호출 실패 시 목업 데이터 반환
    #     st.warning("MCP API 호출에 실패하여 목업 데이터를 표시합니다.")
    #     return get_mock_audit_result(expense_id)
    # 
    # # API 응답에서 결과 추출
    # result = api_response.get('result', {})
    # 
    # # 결과 구조화 (API 응답 구조에 맞게 조정 필요)
    # return {
    #     "expense_id": expense_id,
    #     "expense_details": result.get('expense_details', {}),
    #     "analysis": result.get('analysis', {}),
    #     "receipt_image_url": result.get('receipt_image_url', 'sample.png'),
    #     "rejection_email_draft": result.get('rejection_email_draft', '')
    # }
    
    # [검증용] 2초 딜레이 후 테스트 메시지 반환
    time.sleep(2)
    
    return {
        "expense_id": expense_id,
        "expense_details": {
            "user_name": "테스트 사용자",
            "amount": 100000,
            "business_name": "테스트 업체",
            "business_type": "테스트",
            "payment_datetime": "2024-02-20",
            "attendees_count": 1,
            "card_type": "법인카드"
        },
        "analysis": {
            "compliance_status": "에이전트 검증 완료",
            "findings": [
                "✅ 에이전트 검증 완료"
            ],
            "recommendation": "검증 완료",
            "risk_level": "없음",
            "confidence": 1.0
        },
        "receipt_image_url": "sample.png",
        "rejection_email_draft": "에이전트 검증 완료"
    }


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
    - Agent MCP를 통해 정산 처리 에이전트 호출
    - 승인/반려 처리 및 메일 발송
    - 예: agent_mcp.chat_with_agent(
          query=f"정산 처리: {expense_id}, 결정: {decision}",
          username=username,
          password=password,
          project=project,
          agent_uuid="expense_process_agent_uuid"
      )
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

if 'review_complete' not in st.session_state:
    st.session_state.review_complete = False


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
            st.session_state.review_complete = False
    
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
    if not st.session_state.get('review_complete', False):
        st.markdown("#### 🤖 AI 감사 에이전트 분석 중...")
        
        # 로딩 표시
        with st.spinner("분석 중입니다. 잠시만 기다려주세요..."):
            # MCP API 호출하여 결과 가져오기
            st.session_state.audit_result = get_audit_result(expense_id)
            st.session_state.review_complete = True
    
    # 검토 완료 후 결과 표시
    if st.session_state.get('review_complete', False):
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
                st.session_state.review_complete = False
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
        st.session_state.review_complete = False
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
            # 정산 ID에 해당하는 PDF 파일 경로 가져오기
            receipt_path = get_receipt_path(expense_id)
            if receipt_path:
                display_pdf(receipt_path)
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
                st.rerun()
        
        # 소명 요청 메일 팝업
        if st.session_state.get('show_clarification_popup', False):
            st.markdown("---")
            st.markdown("### 📧 소명 요청 메일")
            
            # 메일 초안 표시 (실제 DB 데이터 사용)
            clarification_email = f"""
제목: [법인카드 정산 소명 요청] {expense_id}

{expense_data.get('user_name', '')}님께,

안녕하세요. 경영지원팀입니다.

제출하신 법인카드 정산 건({expense_id})에 대해 다음과 같은 사항에 대한 소명을 요청드립니다:

[소명 요청 사항]
"""
            
            # 위반 항목들을 소명 요청 내용에 추가
            if violations:
                for idx, violation in enumerate(violations, start=1):
                    clarification_email += f"\n{idx}. {violation['violation_type']}: {violation['description']}"
            
            clarification_email += """

위 사항에 대해 소명자료와 함께 회신해 주시기 바랍니다.

소명 제출 기한: 3영업일 이내
제출 방법: 경영지원팀 이메일 회신

문의사항이 있으시면 경영지원팀으로 연락 주시기 바랍니다.

감사합니다.
"""
            
            st.text_area(
                "메일 내용",
                value=clarification_email,
                height=400,
                disabled=True
            )
            
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                send_btn = st.button(
                    "📤 전송",
                    key="send_clarification",
                    use_container_width=True
                )
                if send_btn:
                    with st.spinner("메일 전송 중..."):
                        time.sleep(1)  # 전송 시뮬레이션
                    
                    st.success("✅ 메일 전송이 완료되었습니다.")
                    time.sleep(2)
                    # 목록으로 돌아가기
                    st.session_state.page = 'list'
                    st.session_state.selected_expense_id = None
                    st.session_state.stream_complete = False
                    st.session_state.audit_result = None
                    st.session_state.show_clarification_popup = False
                    st.session_state.review_complete = False
                    st.rerun()
            
            with col2:
                cancel_btn = st.button(
                    "취소",
                    key="cancel_clarification",
                    use_container_width=True
                )
                if cancel_btn:
                    st.session_state.show_clarification_popup = False
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
