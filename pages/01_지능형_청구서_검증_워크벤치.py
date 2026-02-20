import streamlit as st

st.set_page_config(
    page_title="streamlit-folium documentation",
    page_icon=":world_map:️",
    layout="wide",
)


"# 동적 청구서 정합성 검증"

"""
Dynamic Invoice Reconciliation Agent
"""

import streamlit as st
import psycopg2
import pandas as pd

# DB 연결 함수
def get_db_connection():
    return psycopg2.connect(
        host="dify-ctc-postgre.postgres.database.azure.com",
        database="invoice_demo",
        user="adminuser",
        password="Passw0rd!",
        port=5432,
        sslmode="require"
    )

def get_table_data(query):
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df

st.markdown("""
<style>
.st-ay {
    display: none !important;
}
div[role="radiogroup"] label {
    margin-bottom: 0.4rem !important;
}
</style>
""", unsafe_allow_html=True)
sub = st.sidebar.radio("", ["발주서 목록", "청구서 검증 요청 현황"])

if sub == "발주서 목록":

    st.subheader("발주서 목록")
    df = get_table_data("SELECT * FROM po_header")

    selected = st.dataframe(
        df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if selected.selection.rows:
        row_idx = selected.selection.rows[0]
        row = df.iloc[row_idx]

        st.divider()
        st.subheader("📋 발주서 상세 정보")

        for col in df.columns:
            st.markdown(f"**{col}**: {row[col]}")

elif sub == "청구서 검증 요청 현황":

    col1, col2 = st.columns([8, 2])
    with col1:
        st.subheader("청구서 검증 요청 현황")
    with col2:
        if st.button("📄 청구서 업로드", use_container_width=True):
            st.session_state.show_upload = True
    if st.session_state.get("show_upload", False):
        uploaded_file = st.file_uploader("PDF 파일을 선택하세요", type=["pdf"])
        if uploaded_file:
            with st.spinner("청구서 분석 중..."):
                try:
                    import json
                    import requests
                    response = requests.post(
                        "https://backend.alli.ai/webapi/apps/TExNQXBwOjY5OTU1Yjk4ZDY1ODkzOGM1YmVkYzliMQ==/run",
                        headers={
                            "API-KEY": "SUKYXKTTRPYVAHHOFTSWQYWS3QFSONQJYA",
                            "Content-Type": "application/json"
                        },
                        data=json.dumps({
                            "chat": {
                                "message": uploaded_file.name,
                                "source": {
                                    "knowledgeBaseIds": [],
                                    "folderIds": [],
                                    "webSites": []
                                }
                            },
                            "inputs": {
                                "ANY_ADDITIONAL_PROPERTY": "anything"
                            },
                            "mode": "sync",
                            "isStateful": False,
                            "conversationId": "",
                            "llmModel": "",
                            "llmPromptId": "",
                            "gaPromptGroupId": "",
                            "temperature": 0,
                            "requiredVariables": []
                        })
                    )

                    if response.status_code == 200:
                        st.success("✅ 업로드 및 분석 완료!")
                        st.json(response.json())  # 응답 결과 표시
                    else:
                        st.error(f"❌ 오류 발생: {response.status_code}")

                except Exception as e:
                    st.error(f"❌ API 호출 실패: {e}")

            st.session_state.show_upload = False

    df = get_table_data("SELECT * FROM invoice")

    # 선택 가능한 테이블
    selected = st.dataframe(
        df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # 행 선택 시 상세 페이지
    if selected.selection.rows:
        row_idx = selected.selection.rows[0]
        row = df.iloc[row_idx]

        st.divider()
        st.subheader("📋 상세 정보")

        # UNMATCHED 여부에 따라 맨 위에 표시
        if row["match_status"] in ["UNMATCHED", "DISCREPANCY"]:
            st.error("⚠️ 불일치 발주 내역")
            po_number = row["po_number"]
            detail_df = get_table_data(f"""
                SELECT * FROM v_po_invoice_reconciliation
                WHERE po_number = '{po_number}'
            """)
            st.dataframe(detail_df, use_container_width=True)
            st.divider()
        else:
            st.success("✅ 불일치 발주 내역 없음")
            st.divider()

        # 상세 정보
        for col in df.columns:
            st.markdown(f"**{col}**: {row[col]}")