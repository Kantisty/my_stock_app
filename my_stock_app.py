import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
import feedparser  # 뉴스 크롤링용 라이브러리
from datetime import datetime, timedelta

# 1. 화면 기본 설정
st.set_page_config(page_title="AI 투자 비서 V7", layout="wide")
st.title("🌏 AI 투자 비서 & 뉴스룸 (V7)")
st.caption("실시간 지표 + 뉴스 속보 + AI 종합 분석")

# --- [사이드바: 설정] ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("Google API Key (AI용)", type="password", help="aistudio.google.com에서 발급")
    
    period_dict = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    selected_period_name = st.selectbox("차트 조회 기간", list(period_dict.keys()), index=1)
    days = period_dict[selected_period_name]
    
    st.markdown("---")
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

# AI 분석용 데이터 저장소
daily_data_summary = {}
news_summary = ""

# 3. 함수 정의: 차트 그리기
def draw_chart(name, info):
    symbol = info["symbol"]
    line_color = info["color"]
    try:
        if info["type"] == "fdr":
            df = fdr.DataReader(symbol, start_date, end_date)
        else:
            df = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if len(df) == 0: return

        # 컬럼 처리
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
        
        # AI에게 넘겨줄 데이터 저장
        daily_data_summary[name] = f"{last_val:,.2f} ({diff_pct:+.2f}%)"

        c1, c2 = st.columns([1, 2])
        with c1: st.metric(label=name, value=f"{last_val:,.2f}", delta=f"{diff_pct:.2f}%")
        with c2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=col.index, y=col, mode='lines', line=dict(color=line_color, width=1.5), fill='tozeroy'))
            fig.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(visible=False), yaxis=dict(visible=False))
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
        st.divider()
    except: pass

# 4. 함수 정의: 뉴스 가져오기 (RSS)
def get_news_feed(rss_url, max_items=5):
    feed = feedparser.parse(rss_url)
    news_items = []
    for entry in feed.entries[:max_items]:
        news_items.append(f"- [{entry.title}]({entry.link})")
    return news_items

# --- [메인 UI] ---
# 탭 구성: 지표 / 뉴스
tab_chart, tab_news, tab_ai = st.tabs(["📈 시장 지표", "📰 실시간 뉴스", "🤖 AI 심층분석"])

with tab_chart:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("주식")
        for k, v in indicators_group["📊 주가 지수"].items(): draw_chart(k, v)
    with c2:
        st.subheader("금리/환율")
        for k, v in indicators_group["💰 환율 & 금리"].items(): draw_chart(k, v)
    with c3:
        st.subheader("원자재/코인")
        for k, v in indicators_group["🪙 원자재/코인"].items(): draw_chart(k, v)

with tab_news:
    col_korea, col_us = st.columns(2)
    
    with col_korea:
        st.subheader("🇰🇷 한국 주요 경제 뉴스 (한경)")
        k_news = get_news_feed("https://rss.hankyung.com/feed/market", 7)
        for news in k_news:
            st.markdown(news)
        news_summary += "한국 뉴스 헤드라인:\n" + "\n".join(k_news) + "\n\n"
            
    with col_us:
        st.subheader("🇺🇸 미국 주요 경제 뉴스 (CNBC)")
        # CNBC Finance RSS
        us_news = get_news_feed("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 7)
        for news in us_news:
            st.markdown(news)
        news_summary += "미국 뉴스 헤드라인:\n" + "\n".join(us_news)

with tab_ai:
    st.markdown("### 🧠 뉴스 + 데이터 기반 AI 투자 리포트")
    st.info("AI가 위에서 수집된 '시장 지표'와 '실시간 뉴스'를 함께 읽고 분석합니다.")
    
    if st.button("📊 AI 심층 분석 시작 (클릭)"):
        if not api_key:
            st.error("설정 탭에서 API Key를 먼저 입력해주세요.")
        else:
            with st.spinner("AI가 뉴스와 차트를 분석 중입니다..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""
                    당신은 월가 최고의 헤지펀드 매니저입니다.
                    아래 제공된 [시장 데이터]와 [최신 뉴스]를 종합하여 인사이트 있는 일일 보고서를 작성해주세요.

                    [시장 데이터]
                    {daily_data_summary}

                    [최신 뉴스 헤드라인]
                    {news_summary}

                    [작성 요청 사항]
                    1. **시장 3줄 요약**: 데이터와 뉴스를 종합해 오늘의 핵심 흐름을 요약.
                    2. **상승/하락 원인 분석**: 지표의 변동이 뉴스에 나온 어떤 이슈(금리, 전쟁, 실적 등) 때문인지 연결해서 설명.
                    3. **SOFR 및 금리 점검**: SOFR 금리와 국채 금리를 보고 유동성 위험이 있는지 체크.
                    4. **투자자 행동 강령**: 주식, 코인 투자자가 내일 당장 취해야 할 포지션(매수/매도/관망)을 명확히 제시.
                    
                    투자자에게 말하듯 쉽고 명확하게 작성해줘.
                    """
                    
                    response = model.generate_content(prompt)
                    st.success("분석 완료!")
                    st.markdown(response.text)
                except Exception as e:

                    st.error(f"오류 발생: {e}")
