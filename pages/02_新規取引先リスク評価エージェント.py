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
            add_log("ファイルアップロードの準備中...")
            upload_file_to_blob(file_name, file_bytes)
            add_log(f"ファイルが正常に処理されました。（ファイル名：{file_name}）")
            
        add_log("API送信データ（JSONおよびファイルオブジェクト）の規格を作成中...")
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

        add_log("Allganize APIサーバーに分析リクエストを送信...（AI分析が完了するまで待機します。最大10分かかる場合があります）")
        response = requests.post(api_url, data=data, files=files, headers=headers, timeout=600)
        add_log(f"サーバー応答の受信完了 (ステータスコード: {response.status_code})")
        
        bot_message = ""
        html_content = ""
        result_data = {}
        
        try:
            raw_text = response.text
            add_log(f"[サーバー応答] {raw_text}")
        except Exception:
            raw_text = "Raw Response の確認不可"
            
        if response.status_code != 200:
            add_log(f"❌ 失敗！Allganizeサーバーからエラーコード({response.status_code})が返されました。上記のRAWデータを確認してください。")
            bot_message = f"❌ APIサーバー連携エラー ({response.status_code}): {raw_text}"
        else:
            try:
                result_data = response.json()
            except json.JSONDecodeError:
                result_data = {}
                add_log("JSON形式ではありません。")
                
            add_log("受信した結果データのパースを開始（HTMLキャンバスおよび要約情報の抽出）...")
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
                add_log("パース成功！分析結果を生成します。")
            except Exception as parse_e:
                bot_message = f"応答のパースに失敗: {parse_e}"
                add_log("パース中にエラーが発生しました。Raw Dataを確認してください。")
                
        st.session_state.eval_results = {
            "html_content": html_content,
            "bot_message": bot_message,
            "result_data": result_data
        }
        st.session_state.eval_status = "done"

    except requests.exceptions.Timeout:
        add_log("❌ 応答制限時間（10分）を超過しました。サーバー側の処理が遅延しています。")
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
