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

sub = st.sidebar.radio("", ["발주서 목록", "청구서 검증 요청 현황"])

if sub == "발주서 목록":
    st.markdown("""
    <style>
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Noto Sans KR', sans-serif;
        font-size: 0.85rem;
    }
    .custom-table thead tr {
        background: linear-gradient(135deg, #1a2a4a, #0d1b35);
        color: #6eb3ff;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    .custom-table th {
        padding: 0.9rem 1rem;
        text-align: left;
        border-bottom: 2px solid #2e4e7f;
    }
    .custom-table td {
        padding: 0.85rem 1rem;
        color: #1a1a1a;
        border-bottom: 1px solid #e8eef5;
    }
    .custom-table tbody tr:hover {
        background-color: #f0f5ff;
    }
    .badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 100px;
        font-size: 0.7rem;
        font-weight: 500;
    }
    .badge-완료   { background: #e8fff0; color: #2a6a4a; border: 1px solid #2a6a4a; }
    .badge-진행중 { background: #e8f0ff; color: #2e4e7f; border: 1px solid #2e4e7f; }
    .badge-대기   { background: #fff5e8; color: #8a5a2a; border: 1px solid #8a5a2a; }
    </style>

    <table class="custom-table">
        <thead>
            <tr>
                <th>발주번호</th>
                <th>업체명</th>
                <th>금액</th>
                <th>상태</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>PO-001</td>
                <td>도쿄전자</td>
                <td>1,000,000</td>
                <td><span class="badge badge-완료">완료</span></td>
            </tr>
            <tr>
                <td>PO-002</td>
                <td>퓨처테크</td>
                <td>2,000,000</td>
                <td><span class="badge badge-진행중">진행중</span></td>
            </tr>
            <tr>
                <td>PO-003</td>
                <td>삼성</td>
                <td>3,000,000</td>
                <td><span class="badge badge-대기">대기</span></td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)
elif sub == "청구서 검증 요청 현황":
    st.markdown("""
        <style>
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Noto Sans KR', sans-serif;
            font-size: 0.85rem;
        }
        .custom-table thead tr {
            background: linear-gradient(135deg, #1a2a4a, #0d1b35);
            color: #6eb3ff;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }
        .custom-table th {
            padding: 0.9rem 1rem;
            text-align: left;
            border-bottom: 2px solid #2e4e7f;
        }
        .custom-table td {
            padding: 0.85rem 1rem;
            color: #1a1a1a;
            border-bottom: 1px solid #e8eef5;
        }
        .custom-table tbody tr:hover {
            background-color: #f0f5ff;
        }
        .badge {
            display: inline-block;
            padding: 0.2rem 0.7rem;
            border-radius: 100px;
            font-size: 0.7rem;
            font-weight: 500;
        }
        .badge-검증중 { background: #e8f0ff; color: #2e4e7f; border: 1px solid #2e4e7f; }
        .badge-완료   { background: #e8fff0; color: #2a6a4a; border: 1px solid #2a6a4a; }
        .badge-보류   { background: #fff5e8; color: #8a5a2a; border: 1px solid #8a5a2a; }
        </style>

        <table class="custom-table">
            <thead>
                <tr>
                    <th>요청번호</th>
                    <th>업체명</th>
                    <th>청구금액</th>
                    <th>발주금액</th>
                    <th>차이금액</th>
                    <th>요청일</th>
                    <th>상태</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>REQ-001</td>
                    <td>도쿄전자</td>
                    <td>1,000,000</td>
                    <td>900,000</td>
                    <td style="color:#c0392b;">+100,000</td>
                    <td>2026-02-01</td>
                    <td><span class="badge badge-검증중">검증중</span></td>
                </tr>
                <tr>
                    <td>REQ-002</td>
                    <td>퓨처테크</td>
                    <td>2,000,000</td>
                    <td>2,000,000</td>
                    <td style="color:#2a6a4a;">0</td>
                    <td>2026-02-10</td>
                    <td><span class="badge badge-완료">완료</span></td>
                </tr>
                <tr>
                    <td>REQ-003</td>
                    <td>삼성</td>
                    <td>3,000,000</td>
                    <td>3,100,000</td>
                    <td style="color:#2a6a4a;">-100,000</td>
                    <td>2026-02-15</td>
                    <td><span class="badge badge-보류">보류</span></td>
                </tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)