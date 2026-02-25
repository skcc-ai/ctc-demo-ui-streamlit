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
    app_id = "TExNQXBwOjY5OTQyM2M0ZjgyNTQ2MTVkM2RhYzMxYg=="
    api_key = "SUKYXKTTRPYVAHHOFTSWQYWS3QFSONQJYA"
    base_url = "https://backend.alli.ai"
    
    seen_chat_ids = set()
    
    def get_headers():
        return {"API-KEY": api_key}
        
    def poll_until_done(conversation_id, label=""):
        url_run = f"{base_url}/webapi/v2/conversations/{conversation_id}/running"
        url_chats = f"{base_url}/webapi/v2/conversations/{conversation_id}/chats"
        headers = get_headers()
        start = time.time()
        while True:
            res = requests.get(url_run, headers=headers, timeout=30)
            res.raise_for_status()
            is_running = res.json().get("isRunning", False)
            
            # Fetch intermediate chats to display AI progress
            try:
                c = requests.get(url_chats, headers=headers, timeout=30)
                chats = c.json().get("chats", [])
                for chat in chats:
                    cid = chat.get("id")
                    if cid and cid not in seen_chat_ids:
                        seen_chat_ids.add(cid)
                        ctype = chat.get("type", "")
                        msg = chat.get("message", "")
                        
                        if ctype == "llm" and "Company_Name" in msg:
                            add_log("📄 [진행상황] AI 문서 데이터 추출 완료")
                        elif ctype == "llm":
                            add_log("🧠 [진행상황] AI 거래 상황 및 컨텍스트 분석 완료")
                        elif ctype == "tn":
                            add_log("🌐 [진행상황] 외부 신용 데이터 연동 및 조회 완료")
            except Exception:
                pass
                
            if not is_running:
                return time.time() - start
            time.sleep(5)

    try:
        if file_name and file_bytes:
            add_log("ファイルアップロードの準備中...")
            upload_file_to_blob(file_name, file_bytes)
            add_log(f"ファイルが正常に処理されました。（ファイル名：{file_name}）")
            
        # Step 1: Start conversation
        add_log("APIサーバーと接続中（ステップ1/2）...")
        url_start = f"{base_url}/webapi/apps/{app_id}/run"
        payload_start = {"isStateful": True, "mode": "background"}
        
        # requests.post with json=... automatically sets Content-Type: application/json
        res_start = requests.post(url_start, headers=get_headers(), json=payload_start, timeout=60)
        res_start.raise_for_status()
        conversation_id = res_start.json()["result"]["conversation"]["id"]
        
        # Step 2: Poll till initialized
        poll_until_done(conversation_id, label="初期化")

        # Step 3: Send user message and files
        add_log("APIサーバーに状況説明を送信中（ステップ2/2）...")
        
        data = {
            "json": json.dumps({
                "mode": "background",
                "isStateful": True,
                "conversationId": conversation_id,
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

        res_msg = requests.post(url_start, headers=get_headers(), data=data, files=files, timeout=60)
        res_msg.raise_for_status()
        
        # Step 4: Poll till processed
        poll_until_done(conversation_id, label="処理")

        # Step 5: Fetch chats for result
        add_log("分析完了。結果を取得しています...")
        url_chats = f"{base_url}/webapi/v2/conversations/{conversation_id}/chats"
        res_chats = requests.get(url_chats, headers=get_headers(), timeout=60)
        res_chats.raise_for_status()
        
        chats_data = res_chats.json()
        chats = chats_data.get("chats", [])
        
        bot_message = ""
        html_content = ""
        result_data = chats_data
        
        add_log("受信した結果データのパースを開始（HTMLキャンバスおよび要約情報の抽出）...")
        # Since chats come as a list, find the last BOT message
        for chat in reversed(chats):
            if chat.get("sender") == "BOT":
                bot_message = chat.get("message", "")
                
                # Check for metadata/canvas
                try:
                    metadata_str = chat.get("metadata", "{}")
                    if isinstance(metadata_str, str):
                        metadata = json.loads(metadata_str)
                    else:
                        metadata = metadata_str
                    
                    if isinstance(metadata, dict) and "last_canvas_content" in metadata:
                        html_content = metadata.get("last_canvas_content", "")
                except Exception:
                    pass
                break
                
        if not bot_message:
            bot_message = "BOTから有効なメッセージを受け取れませんでした。"
            
        add_log("パース成功！分析結果を生成します。")
                
        st.session_state.eval_results = {
            "html_content": html_content,
            "bot_message": bot_message,
            "result_data": result_data
        }
        st.session_state.eval_status = "done"

    except requests.exceptions.Timeout:
        add_log("❌ 応答制限時間を超過しました。サーバー側の処理が遅延しています。")
        st.session_state.eval_results = {"bot_message": "❌ API呼び出し中にエラーが発生しました: リクエストがタイムアウトしました。", "html_content": "", "result_data": {}}
        st.session_state.eval_status = "done"
    except Exception as e:
        add_log(f"❌ エラー発生: {str(e)}")
        st.session_state.eval_results = {"bot_message": f"❌ API呼び出し中にエラーが発生しました: {str(e)}", "html_content": "", "result_data": {}}
        st.session_state.eval_status = "done"


st.set_page_config(
    page_title="新規取引先リスク評価エージェント",
    page_icon="🏢",
    layout="wide",
)

st.title("新規取引先リスク評価エージェント")

st.markdown("""
このエージェントは新規取引先の登録前に、名刺や事業体登録証などから**基本情報を抽出**し、
入力された**状況説明**を総合して、当社との取引における**潜在的なリスクを評価**します。
""")

st.subheader("1. 証明書類のアップロード")
uploaded_file = st.file_uploader("名刺または事業体登録証の画像ファイルをアップロード", type=["png", "jpg", "jpeg", "pdf"])

st.subheader("2. 状況説明の入力")
situation_options = [
    "新規契約締結のための事前検討",
    "投資および持分取得のための企業価値評価",
    "定期的な取引先の信用度およびリスクの再評価",
    "特定のプロジェクト協業のためのパートナーシップ協議",
    "直接入力"
]
selected_situation = st.radio("取引が進行している状況を選択してください:", situation_options)

if selected_situation == "直接入力":
    situation_description = st.text_area("取引を進行することになった背景、取引先の主な特徴、懸念点などの状況説明を自由に入力してください。", height=150)
else:
    situation_description = selected_situation

if st.button("リスク評価分析を開始", type="primary"):
    st.session_state.eval_status = "running"
    st.session_state.eval_logs = []
    st.session_state.eval_results = {}
    st.session_state.eval_start_time = time.time()
    
    if not uploaded_file and not situation_description:
        st.session_state.eval_logs.append(f"⚠️ {time.strftime('%H:%M:%S')} - 証明書類の未アップロードおよび状況説明の未入力（デフォルト値で進行します）")
        
    file_name = uploaded_file.name if uploaded_file else None
    file_bytes = uploaded_file.getvalue() if uploaded_file else None
    file_type = uploaded_file.type if uploaded_file else None
    
    t = threading.Thread(target=background_task, args=(file_name, file_bytes, file_type, situation_description))
    add_script_run_ctx(t)
    t.start()
    st.rerun()

if st.session_state.get("eval_status") == "running":
    elapsed = int(time.time() - st.session_state.get("eval_start_time", time.time()))
    
    st.info(f"🚀 リスク評価分析中です...（{elapsed}秒経過）- AIが証明書類と状況説明を分析中です（最大10分所要）")
    
    # 가짜 프로그레스 바 (4배 느리게: 240초 동안 95%까지 차오르다가 대기)
    progress_val = min(elapsed / 240.0, 0.95)
    st.progress(progress_val)
    
    log_container = st.empty()
    log_container.code("\n".join(st.session_state.eval_logs) if st.session_state.eval_logs else "待機中...", language="plaintext")

    time.sleep(1)
    st.rerun()

elif st.session_state.get("eval_status") == "done":
    results = st.session_state.eval_results
    bot_message = results.get("bot_message", "")
    html_content = results.get("html_content", "")
    result_data = results.get("result_data", {})
    
    if "❌" in bot_message:
        st.info("⚠️ リスク評価分析の中断（ログを確認してください）")
        st.code("\n".join(st.session_state.eval_logs), language="plaintext")
    else:
        st.info("🚀 リスク評価分析が完了しました！")
        st.code("\n".join(st.session_state.eval_logs), language="plaintext")
        
        st.success("リスク評価分析が正常に完了しました。")
        st.subheader("分析結果レポート")
        
        if html_content:
            st.markdown("### 🤖 AIキャンバス分析結果")
            components.html(f'<div style="background-color: white; color: black; padding: 20px; border-radius: 10px;">{html_content}</div>', height=800, scrolling=True)
        elif bot_message.strip():
            st.markdown("### 🤖 AI分析結果の要約")
            st.markdown(bot_message)
        else:
            st.markdown("### 🤖 APIの生データ(Raw Response)")
            with st.expander("結果データの確認"):
                st.json(result_data)
