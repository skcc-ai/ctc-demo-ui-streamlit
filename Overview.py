import streamlit as st


st.set_page_config(
    page_title="Agent Demo",
    page_icon="🤖",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Space+Grotesk:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

.main {
    background-color: #0a0f1e;
}

.block-container {
    padding: 3rem 4rem;
    max-width: 1200px;
}

/* 헤더 */
.hero {
    text-align: center;
    padding: 3rem 0 2rem 0;
    margin-bottom: 1rem;
}

.hero-badge {
    display: inline-block;
    background: linear-gradient(135deg, #1a2a4a, #0d1b35);
    border: 1px solid #2a4a7f;
    color: #6eb3ff;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 0.4rem 1.2rem;
    border-radius: 100px;
    margin-bottom: 1.5rem;
}

.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.8rem;
    font-weight: 700;
    color: #6eb3ff;
    line-height: 1.2;
    margin-bottom: 1rem;
}

.hero-title span {
    background: linear-gradient(135deg, #6eb3ff, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-sub {
    color: #8899bb;
    font-size: 1rem;
    font-weight: 300;
    max-width: 540px;
    margin: 0 auto;
    line-height: 1.7;
}

/* 섹션 타이틀 */
.section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.4rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #4a6fa0;
    margin-bottom: 1.2rem;
    padding-left: 0.2rem;
}

/* 워크플로우 카드 */
.workflow-card {
    background: #ffffff;
    border: 2px solid #2e4e7f;
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s ease;
    cursor: pointer;
}

.workflow-card:hover {
    border-color: #5a8acf;
}

.workflow-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #3a6aaf, transparent);
}

.card-number {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #4a6fa0;
    margin-bottom: 0.6rem;
}

.card-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    font-weight: 600;
    color: #1a1a1a;
    margin-bottom: 0.8rem;
    line-height: 1.3;
}

.card-context-label {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6eb3ff;
    margin-bottom: 0.4rem;
}

.card-context {
    font-size: 0.85rem;
    color: #444444;
    line-height: 1.7;
    font-weight: 300;
}

.card-icon {
    float: right;
    font-size: 1.8rem;
    opacity: 0.5;
    margin-top: -0.3rem;
}

/* 채팅 카드 */
.chat-card {
    background: #ffffff;
    border: 2px solid #2a4a38; 
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.7rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    transition: border-color 0.2s ease;
    cursor: pointer;
}

.chat-card:hover {
    border-color: #4a8a6a;
}

.chat-index {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: #1a4a3a;
    min-width: 2rem;
    text-align: center;
}

.chat-content {}

.chat-title {
    font-size: 1.1rem;
    font-weight: 500;
    color: #1a1a1a;
    margin-bottom: 0.15rem;
}

.chat-title-en {
    font-size: 0.75rem;
    color: #3a7a5a;
    font-weight: 400;
}

.chat-tag {
    display: inline-block;
    background: #0a2a1a;
    border: 1px solid #1a4a2a;
    color: #4aaa7a;
    font-size: 0.65rem;
    padding: 0.15rem 0.6rem;
    border-radius: 100px;
    font-weight: 500;
}

/* 구분선 */
.divider {
    border: none;
    border-top: 1px solid #1a2a3a;
    margin: 2.5rem 0;
}

/* 하단 */
.footer-note {
    text-align: center;
    color: #2a3a5a;
    font-size: 0.75rem;
    margin-top: 2rem;
    letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)


# ── 히어로 ──────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-badge">🤖 AI Agent Demo</div>
    <div class="hero-title">ようこそ、<br><span>エージェントデモ</span>のUIです</div>
    <div class="hero-sub">複雑な業務を自動化するAIエージェントのシナリオを<br>直接体験してみてください。</div></div>
""", unsafe_allow_html=True)


# ── 워크플로우 시나리오 ──────────────────────────────
st.markdown('<div class="section-title">⚡ Workflow Agent Scenarios</div>', unsafe_allow_html=True)

scenarios = [
    {
        "num": "SCENARIO 01",
        "icon": "🧾",
        "title": "請求書検証ワークベンチ (Smart Invoice Validator)",
        "context": "財務チームの担当者がメールで受信したサプライヤー（東京電子）の請求書（PDF）を処理する必要があります。発注（PO）システムに登録された金額と請求書の金額が異なるため、手作業で照合し原因を把握しなければならない状況です。"
    },
    {
        "num": "SCENARIO 02",
        "icon": "🏢",
        "title": "新規取引先リスク評価エージェント (Supplier Onboarding Wizard)",
        "context": "購買チームが緊急の資材調達のために初めて見る企業「フューチャーテック」と取引を開始する必要があります。急いでいますが、倒産リスクのある企業や詐欺企業の危険を避けるため、AIを通じて迅速かつ深く検証しようとしています。"
    },
    {
        "num": "SCENARIO 03",
        "icon": "🔍",
        "title": "AI内部統制・監査マネージャー (AI Compliance & Audit Manager)",
        "context": "監査チームの担当者が出勤し、前日に発生した法人カード使用履歴の中から「不正使用」疑いの案件を確認します。数千件の中からAIが事前にフィルタリングした「高リスク群」のみに集中して確認します。"
    },
]

for s in scenarios:
    st.markdown(f"""
    <div class="workflow-card">
        <span class="card-icon">{s['icon']}</span>
        <div class="card-number">{s['num']}</div>
        <div class="card-title">{s['title']}</div>
        <div class="card-context-label">Context</div>
        <div class="card-context">{s['context']}</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown('<hr class="divider">', unsafe_allow_html=True)


# ── 채팅 시나리오 ────────────────────────────────────
st.markdown('<div class="section-title">💬 Chat Agent Scenarios</div>', unsafe_allow_html=True)

st.markdown("""
<div style="font-size:0.82rem; color:#4a6a8a; margin-bottom:1.2rem; line-height:1.6; font-weight:300;">
    非定形の質問 · 迅速な情報検索 · モバイル環境対応 — ワークフローの基本UIを活用するか、最小限のカスタムのみ適用します。</div>
""", unsafe_allow_html=True)

chat_scenarios = [
    ("社内規定・購買ガイドチャットボット", "Policy & Compliance Bot"),
    ("契約書の毒素条項自動レビュー", "Contract AI Reviewer"),
    ("自然言語ベースの注文状況照会", "Sales Field Assistant"),
]

for i, (ko, en) in enumerate(chat_scenarios, 1):
    st.markdown(f"""
    <div class="chat-card">
        <div class="chat-index">0{i}</div>
        <div class="chat-content">
            <div class="chat-title">{ko}</div>
            <div class="chat-title-en">{en}</div>
        </div>
        <div style="margin-left:auto;"><span class="chat-tag">Chat</span></div>
    </div>
    """, unsafe_allow_html=True)


st.markdown('<div class="footer-note">Powered by Claude · Internal Demo Only</div>', unsafe_allow_html=True)