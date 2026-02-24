import streamlit as st
import psycopg2
import pandas as pd
from azure.storage.blob import BlobServiceClient
import fitz  # pymupdf
import os

conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if conn_str is None: conn_str = os.environ.get("AZURE_CONNECTION_STRING")


def get_pdf_from_blob(pdf_path):
    connection_string = conn_str
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container="invoice-docs", blob=pdf_path)
    pdf_bytes = blob_client.download_blob().readall()
    return pdf_bytes

def display_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(2, 2)  # 해상도 2배
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        st.image(img_bytes, use_container_width=True, caption=f"Page {page_num + 1}")

def upload_pdf_to_blob(uploaded_file):
    connection_string = conn_str
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container="invoice-docs", blob=uploaded_file.name)
    blob_client.upload_blob(uploaded_file.getvalue(), overwrite=True)
    return uploaded_file.name

def highlight_discrepancy(row):
    if row["match_result"] == "MATCHED":
        return ["background-color: #e8fff0"] * len(row)
    else:
        return ["background-color: #fff0f0"] * len(row)
def fmt(val, compare_val=None):
    if pd.isna(val):
        return ":red[없음]"
    try:
        formatted = f"{float(val):,.0f}"
    except:
        formatted = str(val)
    if compare_val is not None and not pd.isna(compare_val) and val != compare_val:
        return f":red[{formatted}]"
    return formatted

st.set_page_config(
    page_title="동적 청구서 정합성 검증",
    page_icon="📇",
    layout="wide",
)

"# 📇 동적 청구서 정합성 검증"

"""
Dynamic Invoice Reconciliation Agent
"""

if "page" not in st.session_state:
    st.session_state.page = "list"
if "selected_row" not in st.session_state:
    st.session_state.selected_row = None

def show_invoice_detail():
    row = st.session_state.selected_row

    if st.button("⬅️ 목록으로 돌아가기"):
        st.session_state.page = "list"
        st.session_state.selected_row = None
        st.rerun()

    st.subheader("📋 청구서 상세 정보")
    st.markdown("---")

    if row.get("match_status") not in ["MATCHED"]:
        notes = row.get("notes", "")
        st.error(f"⚠️ 불일치 발주 내역\n\n\t{notes}")
    else:
        st.success("✅ 불일치 발주 내역 없음")

    st.dataframe(pd.DataFrame([row]), use_container_width=True)

    st.markdown("---")

    po_number = row.get("po_number")

    # 데이터 조회
    po_header_df = get_table_data(f"SELECT * FROM po_header WHERE po_number = '{po_number}'")
    invoice_df = get_table_data(f"SELECT * FROM invoice WHERE po_number = '{po_number}'")
    po_lines_df = get_table_data(f"SELECT * FROM po_line WHERE po_number = '{po_number}' ORDER BY line_number")
    invoice_number = row.get("invoice_number")
    invoice_lines_df = get_table_data(
        f"SELECT * FROM invoice_line WHERE invoice_number = '{invoice_number}' ORDER BY line_number")

    po_row = po_header_df.iloc[0] if not po_header_df.empty else {}
    inv_row = invoice_df.iloc[0] if not invoice_df.empty else {}

    def render_row(label, po_val, inv_val):
        col_label, col_po, col_inv = st.columns([2, 3, 3])
        po_str = str(po_val) if not pd.isna(po_val) else "-"
        inv_str = str(inv_val) if not pd.isna(inv_val) else "-"
        is_diff = po_str != inv_str

        if label in ["Invoice Number", "날짜"]:
            with col_label:
                st.markdown(f"**{label}**")
            with col_po:
                st.markdown(f"{po_str}")
            with col_inv:
                st.markdown(f"{inv_str}")
        else:
            with col_label:
                st.markdown(f"**{label}**")
            with col_po:
                st.markdown(f":red[{po_str}]" if is_diff else po_str)
            with col_inv:
                st.markdown(f":red[{inv_str}]" if is_diff else inv_str)

    # 헤더
    col_label, col_po, col_inv = st.columns([2, 3, 3])
    with col_label:
        st.markdown("**항목**")
    with col_po:
        st.markdown("**📄 발주서**")
    with col_inv:
        st.markdown("**🧾 청구서**")
    st.markdown("---")

    # 헤더 공통 항목
    render_row("PO Number", po_row.get("po_number", "-"), inv_row.get("po_number", "-"))
    render_row("Invoice Number", po_row.get("invoice_number", "-"), inv_row.get("invoice_number", "-"))
    render_row("날짜", po_row.get("po_date", "-"), inv_row.get("invoice_date", "-"))
    render_row("통화", po_row.get("currency", "-"), inv_row.get("currency", "-"))
    render_row("소계", po_row.get("subtotal", "-"), inv_row.get("subtotal", "-"))
    render_row("세금", po_row.get("tax_amount", "-"), inv_row.get("tax_amount", "-"))
    render_row("배송비", po_row.get("shipping_fee", "-"), inv_row.get("shipping_fee", "-"))
    render_row("합계", po_row.get("total_amount", "-"), inv_row.get("total_amount", "-"))

    st.markdown("---")

    # 라인 항목
    for i in range(max(len(po_lines_df), len(invoice_lines_df))):
        po_line = po_lines_df.iloc[i] if i < len(po_lines_df) else {}
        inv_line = invoice_lines_df.iloc[i] if i < len(invoice_lines_df) else {}

        line_num = po_line.get("line_number", i + 1) if len(po_line) > 0 else i + 1
        st.markdown(f"**품목 {line_num}**")

        render_row("품목명", po_line.get("item_name", "-"), inv_line.get("item_name", "-"))
        render_row("수량", po_line.get("quantity", "-"), inv_line.get("quantity", "-"))
        render_row("단가", po_line.get("unit_price", "-"), inv_line.get("unit_price", "-"))
        render_row("금액", po_line.get("line_amount", "-"), inv_line.get("line_amount", "-"))
        st.markdown("---")


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

    if st.session_state.page == "detail":
        show_invoice_detail()

    else:
        col1, col2, col3 = st.columns([3, 4, 2])
        with col1:
            st.subheader("청구서 검증 요청 현황")
        with col2:
            exclude_matched = st.checkbox("발주서와 동일한 항목 제외")
        with col3:
            if st.button("📄 청구서 업로드", use_container_width=True):
                st.session_state.show_upload = True

        if st.session_state.get("show_upload", False):
            uploaded_file = st.file_uploader("PDF 파일을 선택하세요", type=["pdf"])
            if uploaded_file:
                with st.spinner("청구서 분석 중..."):
                    try:
                        import json
                        import requests

                        # 1. Azure Blob Storage 업로드
                        file_path = upload_pdf_to_blob(uploaded_file)
                        st.subheader(file_path)

                        # # 2. API 호출 (file_path 파라미터 포함)
                        # response = requests.post(
                        #     "https://backend.alli.ai/webapi/apps/TExNQXBwOjY5OTU1Yjk4ZDY1ODkzOGM1YmVkYzliMQ==/run",
                        #     headers={
                        #         "API-KEY": "SUKYXKTTRPYVAHHOFTSWQYWS3QFSONQJYA",
                        #         "Content-Type": "application/json"
                        #     },
                        #     data=json.dumps({
                        #         "chat": {
                        #             "message": uploaded_file.name,
                        #             "source": {
                        #                 "knowledgeBaseIds": [],
                        #                 "folderIds": [],
                        #                 "webSites": []
                        #             }
                        #         },
                        #         "inputs": {"file_path": file_path},
                        #         "mode": "sync",
                        #         "isStateful": False,
                        #         "conversationId": "",
                        #         "llmModel": "",
                        #         "llmPromptId": "",
                        #         "gaPromptGroupId": "",
                        #         "temperature": 0,
                        #         "requiredVariables": []
                        #     })
                        # )
                        #
                        # if response.status_code == 200:
                        #     st.success("✅ 업로드 및 분석 완료!")
                        #     st.json(response.json())
                        # else:
                        #     st.error(f"❌ 오류 발생: {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ API 호출 실패: {e}")
                st.session_state.show_upload = False

        df = get_table_data("SELECT * FROM invoice")

        if exclude_matched:
            df = df[df["match_status"] != "MATCHED"]

        selected = st.dataframe(
            df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if selected.selection.rows:
            row_idx = selected.selection.rows[0]
            st.session_state.selected_row = df.iloc[row_idx].to_dict()
            st.session_state.page = "detail"
            st.rerun()