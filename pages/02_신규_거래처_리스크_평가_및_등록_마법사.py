import streamlit as st
import time
import requests
import json
import os
from azure.storage.blob import BlobServiceClient

conn_str = os.environ.get("AZURE_CONNECTION_STRING")

def upload_file_to_blob(uploaded_file):
    if not conn_str:
        return uploaded_file.name # Fallback
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    # Using 'invoice-docs' container as referenced in other pages
    blob_client = blob_service_client.get_blob_client(container="invoice-docs", blob=uploaded_file.name)
    blob_client.upload_blob(uploaded_file.getvalue(), overwrite=True)
    return uploaded_file.name


st.set_page_config(
    page_title="신규 거래처 리스크 평가 및 등록 마법사",
    page_icon="🏢",
    layout="wide",
)

st.title("신규 거래처 리스크 평가 및 등록 마법사")

st.markdown("""
이 마법사는 신규 거래처 등록 전, 명함이나 사업자등록증 등을 통해 **기본 정보를 추출**하고, 
입력해주신 **상황 설명**을 종합하여 당사와의 거래에 있어 **잠재적 리스크를 평가**합니다.
""")

st.subheader("1. 증빙 서류 업로드")
uploaded_file = st.file_uploader("명함 또는 사업자등록증 이미지 파일 업로드", type=["png", "jpg", "jpeg", "pdf"])

st.subheader("2. 상황 설명 입력")
situation_description = st.text_area("거래를 진행하게 된 배경, 거래처의 주요 특징, 우려되는 점 등 상황 설명을 자유롭게 입력해주세요.", height=150)

if st.button("리스크 평가 분석 시작", type="primary"):
    if not uploaded_file and not situation_description:
        st.warning("증빙 서류를 업로드하거나 상황 설명을 입력해주세요.")
    else:
        with st.spinner("AI가 증빙 서류와 상황 설명을 분석 중입니다..."):
            try:
                # 1. 파일 업로드
                file_path = upload_file_to_blob(uploaded_file)
                
                # 2. API 호출
                app_id = "TExNQXBwOjY5OTQyM2M0ZjgyNTQ2MTVkM2RhYzMxYg=="
                api_key = "SUKYXKTTRPYVAHHOFTSWQYWS3QFSONQJYA"
                api_url = f"https://backend.alli.ai/webapi/apps/{app_id}/run"
                
                payload = {
                    "chat": {
                        "message": situation_description
                    },
                    "inputs": {
                        "file_path": file_path,
                        "file_name": uploaded_file.name
                    },
                    "mode": "sync"
                }

                headers = {
                    "Content-Type": "application/json",
                    "API-KEY": api_key
                }

                response = requests.post(api_url, json=payload, headers=headers)
                response.raise_for_status()
                result_data = response.json()
                
                # 봇 응답 메시지 추출
                bot_message = ""
                responses = result_data.get("result", {}).get("responses", [])
                for resp in responses:
                    if resp.get("sender") == "BOT":
                        bot_message += resp.get("message", "") + "\\n\\n"
                        
            except Exception as e:
                bot_message = f"❌ API 호출 중 오류가 발생했습니다: {str(e)}"

        st.success("리스크 평가 분석이 완료되었습니다.")
        
        # 분석 결과 표시
        st.subheader("분석 결과 보고서")
        st.markdown("### 🤖 AI 분석 결과")
        if bot_message.strip():
            st.markdown(bot_message)
        else:
            with st.expander("API Raw Response"):
                st.json(result_data)
