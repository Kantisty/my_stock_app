import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
import feedparser
from datetime import datetime, timedelta

# 1. 화면 기본 설정
st.set_page_config(page_title="AI 투자 비서 V9.1", layout="wide")
st.title("🌏 AI 투자 비서 & 뉴스룸 (V9.1)")
st.caption("베이스: V7.9 / 엔진: Gemini 3 Pro (Auto-Fallback 적용)")

# --- [사이드바: 설정] ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("Google API Key (AI용)", type="password", help="aistudio.google.com에서 발급")
    
    # V7.9의 심플한 기간 설정 유지
    period_dict = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    selected_period_name = st.selectbox("차트 조회 기간", list(period_dict.keys()), index=1)
    days = period_dict[selected_period_name]
    
    st.markdown("---")
    st.info("Tip: 최신 모델(3 Pro)을 우선 시도하고, 안 되면 자동으로 2.5 Flash를 사용합니다.")
    if st.button('🔄 데이터 & 뉴스 새로고침'):
        st.rerun()

end_date = datetime.now()
start_date = end_date - timedelta(days=days)

# 2. 데이터 그룹
indicators_group = {
    "📊 주가 지수": {
        "🇰🇷 코스피": {"type": "fdr", "symbol": "KS11", "color": "#E74C3C"},
        "🇺🇸 S&P 500": {"type": "fdr", "symbol": "US500", "color": "#27AE60"},
        "🇺🇸 나스닥 100": {"type": "fdr", "symbol": "IXIC", "color": "#8E44AD"},
        "💾 반도체(SOX)": {"type": "yf", "symbol": "^SOX", "color": "#2980B9"}
    },
    "💰 환율 & 금리": {
        "💸 원/달러": {"type": "fdr", "symbol": "USD/KRW", "color": "#D35400"},
        "🏦 미국 SOFR": {"type": "fdr", "symbol": "FRED:SOFR", "color": "#16A085"},
        "🇺🇸 미 국채 10년": {"type": "yf", "symbol": "^TNX", "color": "#2980B9"}
    },
    "🪙 원자재/코인": {
        "₿ 비트코인": {"type": "yf", "symbol": "BTC-USD", "color": "#F39C12"},
        "🛢️ WTI 원유": {"type": "yf", "symbol": "CL=F", "color": "#2C3E50"},
        "😱 공포지수(VIX)": {"type": "yf", "symbol": "^VIX", "color": "#7F8C8D"}
    }
}

daily_data_summary = {}
news_summary = ""

# 3. 차트 그리기 함수 (V7.9 디자인: 수치 위, 차트 아래)
def draw_chart(name, info):
    symbol = info["symbol"]
    line_color = info["color"]
    try:
        if info["type"] == "fdr":
            df = fdr.DataReader(symbol, start_date, end_date)
        else:
            df = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if len(df) == 0: return

        if 'Close' in df.columns: col = df['Close']
        elif 'Adj Close' in df.columns: col = df['Adj Close']
        elif 'DATE' in df.columns: col = df['DATE']
        else: col = df.iloc[:, 0]
        if hasattr(col, 'columns'): col = col.iloc[:, 0]
        col = col.dropna()
            
        last_val = float(col.iloc[-1])
        prev_val = float(col.iloc[-2])
        diff = last_val - prev_val
        diff_pct = (diff / prev_val) * 100 if prev_val != 0 else 0
        
        daily_data_summary[name] = f"{last_val:,.2f} ({diff_pct:+.2f}%)"

        # 수치 표시
        st.metric(label=name, value=f"{last_val:,.2f}", delta=f"{diff_pct:.2f}%")
        
        # 차트 그리기
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=col.index, 
            y=col, 
            mode='lines', 
            name=
