import streamlit as st
import time
import requests
import json
import os
import streamlit.components.v1 as components
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
situation_options = [
    "신규 계약 체결을 위한 사전 검토",
    "투자 및 지분 인수를 위한 기업 가치 평가",
    "정기적인 거래처 신용도 및 리스크 재평가",
    "특정 프로젝트 협업을 위한 파트너십 논의",
    "직접 입력"
]
selected_situation = st.radio("거래가 진행되는 상황을 선택해주세요:", situation_options)

if selected_situation == "직접 입력":
    situation_description = st.text_area("거래를 진행하게 된 배경, 거래처의 주요 특징, 우려되는 점 등 상황 설명을 자유롭게 입력해주세요.", height=150)
else:
    situation_description = selected_situation

if st.button("리스크 평가 분석 시작", type="primary"):
    if not uploaded_file and not situation_description:
        st.warning("증빙 서류를 업로드하거나 상황 설명을 입력해주세요.")
    else:
        # 진행 상태를 보여줄 컨테이너 생성
        status_placeholder = st.empty()
        log_container = st.empty()
        
        with status_placeholder.container():
            st.info("🚀 리스크 평가 분석 프로세스를 시작합니다...")
            
        logs = []
        def add_log(msg):
            logs.append(f"✅ {time.strftime('%H:%M:%S')} - {msg}")
            log_container.code("\n".join(logs), language="plaintext")

        with st.spinner("AI가 증빙 서류와 상황 설명을 분석 중입니다..."):
            bot_message = ""
            html_content = ""
            result_data = {}
            try:
                # 1. 파일 업로드 단계
                add_log("파일 업로드 준비 중...")
                file_path = upload_file_to_blob(uploaded_file)
                add_log(f"파일이 성공적으로 처리되었습니다. (파일명: {uploaded_file.name if uploaded_file else '없음'})")
                
                # 2. API 데이터 준비 단계
                add_log("API 전송 데이터(JSON 및 파일 객체) 규격 생성 중...")
                app_id = "TExNQXBwOjY5OTQyM2M0ZjgyNTQ2MTVkM2RhYzMxYg=="
                api_key = "SUKYXKTTRPYVAHHOFTSWQYWS3QFSONQJYA"
                api_url = f"https://backend.alli.ai/webapi/apps/{app_id}/run"
                
                data = {
                    "json": json.dumps({
                        "mode": "sync",
                        "chat": {
                            "message": "Start Evaluation"
                        },
                        "inputs": {
                            "DEAL_CONTEXT_TEXT": situation_description
                        }
                    })
                }

                files = {}
                if uploaded_file:
                    files["COMPANY_ID_IMAGE"] = (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)

                headers = {
                    "API-KEY": api_key
                }

                # 3. API 호출 및 대기 단계
                add_log("Allganize API 서버로 분석 요청 전송... (AI 분석이 완료될 때까지 대기합니다. 최대 10분 소요 가능)")
                response = requests.post(api_url, data=data, files=files, headers=headers, timeout=600)
                add_log(f"서버 응답 수신 완료 (Status Code: {response.status_code})")
                
                bot_message = ""
                html_content = ""
                
                # Raw 디버깅 로그를 무조건 가장 먼저 출력 (200, 400, 500 상관없이)
                try:
                    raw_text = response.text
                    add_log(f"[RAW 데이터 전체] {raw_text}")
                except Exception:
                    raw_text = "Raw Response 확인 불가"
                    pass
                
                if response.status_code != 200:
                    add_log(f"❌ 실패! Allganize 서버에서 에러 코드({response.status_code})를 반환했습니다. 위 RAW 데이터를 확인해주세요.")
                    bot_message = f"❌ API 서버 연동 에러 ({response.status_code}): {raw_text}"
                else:
                    try:
                        result_data = response.json()
                    except json.JSONDecodeError:
                        result_data = {}
                        add_log("JSON 형식이 아닙니다.")
                        
                    # 4. 응답 데이터 파싱 단계
                    add_log("수신된 결과 데이터 파싱 시작 (HTML 캔버스 및 요약 정보 추출)...")
                    try:
                        data_block = result_data.get("data", {})
                        result_block = data_block.get("result", {}) if data_block else result_data.get("result", {})
                        
                        if isinstance(result_block, dict):
                            metadata = result_block.get("metadata", {})
                            if isinstance(metadata, dict):
                                html_content = metadata.get("last_canvas_content", "")
                            
                            if result_block.get("response"):
                                bot_message = result_block.get("response")
                        
                        if not html_content and not bot_message:
                            variables = result_block.get("variables", {})
                            if "RESPONSE" in variables:
                                bot_message = variables["RESPONSE"]
                            else:
                                responses = result_block.get("responses", [])
                                if isinstance(responses, list):
                                    for resp in responses:
                                        if resp.get("sender") == "BOT":
                                            bot_message = resp.get("message", "")
                        add_log("파싱 성공! 분석 결과를 생성합니다.")
                    except Exception as parse_e:
                        bot_message = f"응답 파싱 실패: {parse_e}"
                        add_log("파싱 도중 오류가 발생했습니다. Raw Data를 확인해주세요.")
                        
            except requests.exceptions.Timeout:
                add_log("❌ 응답 제한 시간(10분)을 초과했습니다. 서버 쪽 처리가 지연되고 있습니다.")
                bot_message = "❌ API 호출 중 오류가 발생했습니다: 요청 시간이 초과되었습니다."
            except Exception as e:
                add_log(f"❌ 오류 발생: {str(e)}")
                bot_message = f"❌ API 호출 중 오류가 발생했습니다: {str(e)}"

        # 에러가 발생하지 않고 응답이 정상적일 때만 success 표시
        status_placeholder.empty() # 진행 상태 info 메시지 지우기
        
        if "❌" not in bot_message:
            st.success("리스크 평가 분석이 성공적으로 완료되었습니다.")
        else:
            st.error("분석 중 오류가 발생했습니다. 위의 로그를 확인해주세요.")
        
        # 분석 결과 표시
        st.subheader("분석 결과 보고서")
        
        if html_content:
            st.markdown("### 🤖 AI 캔버스 분석 결과")
            components.html(html_content, height=800, scrolling=True)
        elif bot_message.strip():
            st.markdown("### 🤖 AI 분석 결과 요약")
            st.markdown(bot_message)
        else:
            st.markdown("### 🤖 API Raw Response")
            with st.expander("결과 데이터 확인"):
                st.json(result_data)
