import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
import feedparser
from datetime import datetime, timedelta

# 1. 화면 기본 설정
st.set_page_config(page_title="AI 투자 비서 V7.9", layout="wide")
st.title("🌏 AI 투자 비서 & 뉴스룸 (V7.9)")
st.caption("AI 모델 복구 (Gemini 2.5 Flash) 및 차트 디자인 최적화")

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

daily_data_summary = {}
news_summary = ""

# 3. 차트 그리기 함수 (보기 편한 V7.7 디자인 유지)
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
            name=name,
            line=dict(color=line_color, width=2),
            fill='tozeroy',
            hovertemplate='%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            height=250, # 차트 크기 확대 유지
            margin=dict(l=5, r=5, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=True, gridcolor='lightgray', side='right')
        )
        st.plotly_chart(fig, use_container_width=True, config={'staticPlot': False})
        
        st.divider()
        
    except: pass

# 4. 뉴스 가져오기 함수 (V7.5 유지)
def get_news_feed(rss_url, max_items=7):
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:max_items]:
            link = getattr(entry, 'link', '#') 
            title = getattr(entry, 'title', '제목 없음')
            news_items.append(f"- [{title}]({link})")
        return news_items
    except Exception as e:
        return [f"뉴스 피드 로딩 실패: {e}"]

# --- [메인 UI] ---
tab_chart, tab_news, tab_ai = st.tabs(["📈 시장 지표", "📰 실시간 뉴스", "🤖 AI 심층분석"])

with tab_chart:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("📊 주식")
        for k, v in indicators_group["📊 주가 지수"].items(): draw_chart(k, v)
    with c2:
        st.subheader("💰 금리/환율")
        for k, v in indicators_group["💰 환율 & 금리"].items(): draw_chart(k, v)
    with c3:
        st.subheader("🪙 원자재/코인")
        for k, v in indicators_group["🪙 원자재/코인"].items(): draw_chart(k, v)

with tab_news:
    col_korea, col_us = st.columns(2)
    with col_korea:
        st.subheader("🇰🇷 한국 증시 뉴스 (매일경제)")
        k_news = get_news_feed("https://www.mk.co.kr/rss/30100041/", 7) 
        for news in k_news: st.markdown(news)
        news_summary += "한국 뉴스:\n" + "\n".join(k_news) + "\n\n"
    with col_us:
        st.subheader("🇺🇸 미국 뉴스 (CNBC)")
        us_news = get_news_feed("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 7)
        for news in us_news: st.markdown(news)
        news_summary += "미국 뉴스:\n" + "\n".join(us_news)

with tab_ai:
    st.markdown("### 🧠 뉴스 + 데이터 기반 AI 투자 리포트")
    st.info("AI 모델: Gemini 2.5 Flash (복구 완료)")
    
    if st.button("📊 AI 심층 분석 시작"):
        if not api_key:
            st.error("설정 탭에서 API Key를 입력해주세요.")
        else:
            with st.spinner("Gemini 2.5 Flash가 시장을 분석 중입니다..."):
                try:
                    # ✅ 문제가 된 client_options 삭제
                    genai.configure(api_key=api_key)
                    # ✅ 아까 잘 작동했던 모델명으로 복구
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    prompt = f"""
                    당신은 월가 최고의 헤지펀드 매니저입니다.
                    [시장 데이터]
                    {daily_data_summary}
                    [뉴스 헤드라인]
                    {news_summary}

                    위 정보를 바탕으로 다음 보고서를 작성해 주세요:
                    1. **시장 핵심 요약 (3줄)**
                    2. **상승/하락 원인 분석**: 뉴스와 지표를 연결해서 설명.
                    3. **위험 신호 점검**: 특히 SOFR, 국채금리, 환율 위주로.
                    4. **실전 투자 전략**: 주식 비중을 늘릴지, 현금을 확보할지 구체적으로 조언.
                    
                    중요한 부분은 굵은 글씨로 강조해 주세요.
                    """
                    
                    response = model.generate_content(prompt)
                    st.success("분석 완료!")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"오류 발생: {e}")
