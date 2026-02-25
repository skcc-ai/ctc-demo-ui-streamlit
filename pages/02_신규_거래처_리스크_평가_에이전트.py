import streamlit as st
import time
import requests
import json
import os
import streamlit.components.v1 as components
from azure.storage.blob import BlobServiceClient
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx

conn_str = os.environ.get("AZURE_CONNECTION_STRING")

def upload_file_to_blob(file_name, file_bytes):
    if not conn_str:
        return file_name # Fallback
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    # Using 'invoice-docs' container as referenced in other pages
    blob_client = blob_service_client.get_blob_client(container="invoice-docs", blob=file_name)
    blob_client.upload_blob(file_bytes, overwrite=True)
    return file_name

if "eval_status" not in st.session_state:
    st.session_state.eval_status = "idle"
if "eval_logs" not in st.session_state:
    st.session_state.eval_logs = []
if "eval_results" not in st.session_state:
    st.session_state.eval_results = {}

def add_log(msg):
    if msg.startswith("❌") or msg.startswith("⚠️"):
        # The message already has an emoji, so just insert the time after it
        emoji_char = msg[0]
        text_part = msg[1:].strip()
        timestamp = time.strftime('%H:%M:%S')
        st.session_state.eval_logs.append(f"{emoji_char} {timestamp} - {text_part}")
    else:
        # Prepend the default success/info emoji
        st.session_state.eval_logs.append(f"✅ {time.strftime('%H:%M:%S')} - {msg}")

def background_task(file_name, file_bytes, file_type, situation_desc):
    try:
        if file_name and file_bytes:
            add_log("파일 업로드 준비 중...")
            upload_file_to_blob(file_name, file_bytes)
            add_log(f"파일이 성공적으로 처리되었습니다. (파일명: {file_name})")
            
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
                    "DEAL_CONTEXT_TEXT": situation_desc
                }
            })
        }

        files = {}
        if file_name and file_bytes:
            files["COMPANY_ID_IMAGE"] = (file_name, file_bytes, file_type)

        headers = {
            "API-KEY": api_key
        }

        add_log("Allganize API 서버로 분석 요청 전송... (AI 분석이 완료될 때까지 대기합니다. 최대 10분 소요 가능)")
        response = requests.post(api_url, data=data, files=files, headers=headers, timeout=600)
        add_log(f"서버 응답 수신 완료 (Status Code: {response.status_code})")
        
        bot_message = ""
        html_content = ""
        result_data = {}
        
        try:
            raw_text = response.text
            add_log(f"[서버 응답] {raw_text}")
        except Exception:
            raw_text = "Raw Response 확인 불가"
            
        if response.status_code != 200:
            add_log(f"❌ 실패! Allganize 서버에서 에러 코드({response.status_code})를 반환했습니다. 위 RAW 데이터를 확인해주세요.")
            bot_message = f"❌ API 서버 연동 에러 ({response.status_code}): {raw_text}"
        else:
            try:
                result_data = response.json()
            except json.JSONDecodeError:
                result_data = {}
                add_log("JSON 형식이 아닙니다.")
                
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
                
        st.session_state.eval_results = {
            "html_content": html_content,
            "bot_message": bot_message,
            "result_data": result_data
        }
        st.session_state.eval_status = "done"

    except requests.exceptions.Timeout:
        add_log("❌ 응답 제한 시간(10분)을 초과했습니다. 서버 쪽 처리가 지연되고 있습니다.")
        st.session_state.eval_results = {"bot_message": "❌ API 호출 중 오류가 발생했습니다: 요청 시간이 초과되었습니다.", "html_content": "", "result_data": {}}
        st.session_state.eval_status = "done"
    except Exception as e:
        add_log(f"❌ 오류 발생: {str(e)}")
        st.session_state.eval_results = {"bot_message": f"❌ API 호출 중 오류가 발생했습니다: {str(e)}", "html_content": "", "result_data": {}}
        st.session_state.eval_status = "done"


st.set_page_config(
    page_title="신규 거래처 리스크 평가 에이전트",
    page_icon="🏢",
    layout="wide",
)

st.title("신규 거래처 리스크 평가 에이전트")

st.markdown("""
이 에이전트는 신규 거래처 등록 전, 명함이나 사업자등록증 등을 통해 **기본 정보를 추출**하고, 
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
    st.session_state.eval_status = "running"
    st.session_state.eval_logs = []
    st.session_state.eval_results = {}
    st.session_state.eval_start_time = time.time()
    
    if not uploaded_file and not situation_description:
        st.session_state.eval_logs.append(f"⚠️ {time.strftime('%H:%M:%S')} - 증빙 서류 미업로드 및 상황 설명 미입력 (기본값으로 진행됩니다)")
        
    file_name = uploaded_file.name if uploaded_file else None
    file_bytes = uploaded_file.getvalue() if uploaded_file else None
    file_type = uploaded_file.type if uploaded_file else None
    
    t = threading.Thread(target=background_task, args=(file_name, file_bytes, file_type, situation_description))
    add_script_run_ctx(t)
    t.start()
    st.rerun()

if st.session_state.get("eval_status") == "running":
    elapsed = int(time.time() - st.session_state.get("eval_start_time", time.time()))
    
    st.info(f"🚀 리스크 평가 분석 중입니다... ({elapsed}초 경과) - AI가 증빙 서류와 상황 설명을 분석 중입니다 (최대 10분 소요)")
    
    # 가짜 프로그레스 바 (4배 느리게: 240초 동안 95%까지 차오르다가 대기)
    progress_val = min(elapsed / 240.0, 0.95)
    st.progress(progress_val)
    
    log_container = st.empty()
    log_container.code("\n".join(st.session_state.eval_logs) if st.session_state.eval_logs else "대기 중...", language="plaintext")

    time.sleep(1)
    st.rerun()

elif st.session_state.get("eval_status") == "done":
    results = st.session_state.eval_results
    bot_message = results.get("bot_message", "")
    html_content = results.get("html_content", "")
    result_data = results.get("result_data", {})
    
    if "❌" in bot_message:
        st.info("⚠️ 리스크 평가 분석 중단 (로그를 확인해주세요)")
        st.code("\n".join(st.session_state.eval_logs), language="plaintext")
    else:
        st.info("🚀 리스크 평가 분석 완료!")
        st.code("\n".join(st.session_state.eval_logs), language="plaintext")
        
        st.success("리스크 평가 분석이 성공적으로 완료되었습니다.")
        st.subheader("분석 결과 보고서")
        
        if html_content:
            st.markdown("### 🤖 AI 캔버스 분석 결과")
            components.html(f'<div style="background-color: white; color: black; padding: 20px; border-radius: 10px;">{html_content}</div>', height=800, scrolling=True)
        elif bot_message.strip():
            st.markdown("### 🤖 AI 분석 결과 요약")
            st.markdown(bot_message)
        else:
            st.markdown("### 🤖 API Raw Response")
            with st.expander("결과 데이터 확인"):
                st.json(result_data)
