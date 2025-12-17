import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
import feedparser
from datetime import datetime, timedelta
import pytz  # 시간대 처리를 위한 라이브러리

# 1. 화면 기본 설정
st.set_page_config(page_title="AI 투자 비서 V10.2", layout="wide")

# --- [기능 1] 한국/미국 시간 정확히 계산 ---
# 서버의 UTC 시간 가져오기
utc_now = datetime.now(pytz.utc)

# 한국 시간 (KST) 변환
kst_timezone = pytz.timezone('Asia/Seoul')
kst_now = utc_now.astimezone(kst_timezone)
kst_str = kst_now.strftime("%m/%d %H:%M:%S")

# 미국 동부 시간 (ET) 변환 (뉴욕 증시 기준)
us_timezone = pytz.timezone('US/Eastern')
us_now = utc_now.astimezone(us_timezone)
us_str = us_now.strftime("%m/%d %H:%M:%S")

# 메인 타이틀에 시간 표시
st.title(f"🌏 AI 투자 비서 (🇰🇷 {kst_str} | 🇺🇸 {us_str})")

# --- [기능 2] 업데이트 내역 ---
with st.expander("📝 버전 업데이트 히스토리 (V1.0 ~ V10.2)"):
    st.markdown("""
    * **V10.2:** 서버 시간대 문제 해결 (한국/미국 시간 동시 표시)
    * **V10.1:** 조회 시점 표시, 히스토리 열람 기능
    * **V10.0:** 차트 이평선(60/200일), 뉴스 20개, 엔화/부동산 지표
    * **V9.x:** AI 리포트 고도화 및 데이터 안정화
    """)

# --- [사이드바: 설정] ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("Google API Key (AI용)", type="password", help="aistudio.google.com에서 발급")
    
    period_options = {
        "최근 1개월": 30,
        "최근 3개월": 90,
        "최근 6개월": 180,
        "최근 1년": 365,
        "최근 2년": 730
    }
    selected_period_label = st.selectbox("차트 확대/축소 (Display)", list(period_options.keys()), index=1)
    display_days = period_options[selected_period_label]
    
    st.markdown("---")
    st.info("Tip: 차트에 60일(초록), 200일(회색) 이동평균선이 함께 표시됩니다.")
    if st.button('🔄 데이터 & 뉴스 새로고침'):
        st.rerun()

# 데이터 수집 기간 (이평선 계산용)
calc_start_date = datetime.now() - timedelta(days=400) 
display_start_date = datetime.now() - timedelta(days=display_days)
end_date = datetime.now()

# 2. 데이터 그룹
indicators_group = {
    "📊 주가 지수": {
        "🇰🇷 코스피": {"type": "fdr", "symbol": "KS11", "color": "#E74C3C"},
        "🇰🇷 코스닥": {"type": "fdr", "symbol": "KQ11", "color": "#FF6347"},
        "🇺🇸 S&P 500": {"type": "fdr", "symbol": "US500", "color": "#27AE60"},
        "🇺🇸 나스닥 100": {"type": "fdr", "symbol": "IXIC", "color": "#8E44AD"},
        "💾 반도체(SOX)": {"type": "yf", "symbol": "^SOX", "color": "#2980B9"}
    },
    "💰 환율 & 금리 & 부동산": {
        "💸 원/달러": {"type": "fdr", "symbol": "USD/KRW", "color": "#D35400"},
        "💴 원/엔 (JPY)": {"type": "fdr", "symbol": "JPY/KRW", "color": "#5D6D7E"},
        "🏗️ 리츠부동산(PF심리)": {"type": "fdr", "symbol": "329200", "color": "#8B4513"},
        "🏦 미국 SOFR": {"type": "fdr", "symbol": "FRED:SOFR", "color": "#16A085"},
        "🇰🇷 한국 국채 10년": {"type": "fdr", "symbol": "KR10YT=RR", "color": "#C0392B"},
        "🇺🇸 미 국채 10년": {"type": "yf", "symbol": "^TNX", "color": "#2980B9"},
        "🇺🇸 미 국채 30년": {"type": "yf", "symbol": "^TYX", "color": "#1ABC9C"}
    },
    "🪙 원자재/코인/리스크": {
        "🥇 금 선물 (Gold)": {"type": "yf", "symbol": "GC=F", "color": "#F1C40F"},
        "🏭 구리 (경기선행)": {"type": "yf", "symbol": "HG=F", "color": "#A0522D"},
        "⚠️ 하이일드(HYG)": {"type": "yf", "symbol": "HYG", "color": "#800080"},
        "₿ 비트코인": {"type": "yf", "symbol": "BTC-USD", "color": "#F39C12"},
        "🛢️ WTI 원유": {"type": "yf", "symbol": "CL=F", "color": "#2C3E50"},
        "😱 공포지수(VIX)": {"type": "yf", "symbol": "^VIX", "color": "#7F8C8D"}
    }
}

daily_data_summary = {}
news_summary = ""

# 3. 차트 그리기 함수
def draw_chart(name, info):
    symbol = info["symbol"]
    line_color = info["color"]
    try:
        if info["type"] == "fdr":
            df = fdr.DataReader(symbol, calc_start_date, end_date)
        else:
            df = yf.download(symbol, start=calc_start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if df is None or len(df) == 0: return

        if 'Close' in df.columns: col = df['Close']
        elif 'Adj Close' in df.columns: col = df['Adj Close']
        elif 'DATE' in df.columns: col = df['DATE']
        else: col = df.iloc[:, 0]
        
        if hasattr(col, 'columns'): col = col.iloc[:, 0]
        col = col.dropna()

        # 이평선 계산
        ma60 = col.rolling(window=60).mean()
        ma200 = col.rolling(window=200).mean()

        # 화면 표시용 데이터 자르기
        mask = col.index >= display_start_date
        col_display = col.loc[mask]
        ma60_display = ma60.loc[mask]
        ma200_display = ma200.loc[mask]
        
        if len(col_display) < 1: return

        last_val = float(col_display.iloc[-1])
        prev_val = float(col_display.iloc[-2])
        start_val = float(col_display.iloc[0]) 
        
        daily_diff_pct = (last_val - prev_val) / prev_val * 100 if prev_val != 0 else 0
        period_diff_pct = (last_val - start_val) / start_val * 100 if start_val != 0 else 0
        
        daily_data_summary[name] = f"{last_val:,.2f} ({daily_diff_pct:+.2f}%)"

        st.metric(label=name, value=f"{last_val:,.2f}", delta=f"{daily_diff_pct:.2f}% (기간: {period_diff_pct:+.2f}%)")
        
        fig = go.Figure()
        
        # 메인 가격 선
        fig.add_trace(go.Scatter(
            x=col_display.index, y=col_display, mode='lines', name='현재가',
            line=dict(color=line_color, width=2),
            fill='tozeroy',
            hovertemplate='%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>'
        ))
        
        # 60일선
        fig.add_trace(go.Scatter(
            x=ma60_display.index, y=ma60_display, mode='lines', name='60일선',
            line=dict(color='green', width=1, dash='dot'),
            hoverinfo='skip'
        ))

        # 200일선
        fig.add_trace(go.Scatter(
            x=ma200_display.index, y=ma200_display, mode='lines', name='200일선',
            line=dict(color='gray', width=1.5),
            hoverinfo='skip'
        ))
        
        fig.update_layout(
            height=280,
            margin=dict(l=5, r=5, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=True, gridcolor='lightgray', side='right'),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True, config={'staticPlot': False})
        st.divider()
        
    except: pass

# 4. 뉴스 가져오기 함수 (20개)
def get_news_feed(rss_url, max_items=20):
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

# 5. AI 응답 생성 함수
def generate_ai_report(prompt, api_key):
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-3-pro-preview')
        response = model.generate_content(prompt)
        return f"🚀 **Gemini 3 Pro 분석 결과**\n\n{response.text}"
    except:
        try:
            model_fallback = genai.GenerativeModel('gemini-2.5-flash')
            response_fallback = model_fallback.generate_content(prompt)
            return f"⚠️ **Gemini 2.5 Flash 분석 결과** (자동 전환)\n\n{response_fallback.text}"
        except Exception as e:
            return f"❌ 분석 실패: {e}"

# --- [메인 UI] ---
tab_chart, tab_news, tab_ai = st.tabs(["📈 시장 지표", "📰 실시간 뉴스", "🤖 AI 심층분석"])

with tab_chart:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("📊 주식")
        for k, v in indicators_group["📊 주가 지수"].items(): draw_chart(k, v)
    with c2:
        st.subheader("💰 환율/금리/부동산")
        for k, v in indicators_group["💰 환율 & 금리 & 부동산"].items(): draw_chart(k, v)
    with c3:
        st.subheader("🪙 원자재/코인/리스크")
        for k, v in indicators_group["🪙 원자재/코인/리스크"].items(): draw_chart(k, v)

with tab_news:
    col_k, col_u = st.columns(2)
    with col_k:
        st.subheader("🇰🇷 한국 뉴스 (최신 20개)")
        news_container = st.container(height=600)
        k_news = get_news_feed("https://www.mk.co.kr/rss/30100041/", 20) 
        with news_container:
            for news in k_news: st.markdown(news)
        news_summary += "한국 뉴스:\n" + "\n".join(k_news[:10]) + "\n\n"
        
    with col_u:
        st.subheader("🇺🇸 미국 뉴스 (최신 20개)")
        news_container_us = st.container(height=600)
        us_news = get_news_feed("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 20)
        with news_container_us:
            for news in us_news: st.markdown(news)
        news_summary += "미국 뉴스:\n" + "\n".join(us_news[:10])

with tab_ai:
    st.markdown("### 🧠 뉴스 + 데이터 기반 AI 투자 리포트")
    st.info("엔진: Gemini 3 Pro (우선) -> Gemini 2.5 Flash (예비)")
    
    if st.button("📊 AI 심층 분석 시작"):
        if not api_key:
            st.error("설정 탭에서 API Key를 입력해주세요.")
        else:
            with st.spinner("AI가 시장을 분석 중입니다..."):
                prompt = f"""
                당신은 월가 최고의 헤지펀드 매니저입니다.
                [시장 데이터]
                {daily_data_summary}
                [뉴스 헤드라인]
                {news_summary}

                위 정보를 바탕으로 다음 양식에 맞춰 보고서를 작성해 주세요:
                
                1. **한국, 미국 시장 핵심 요약 (각각 3줄)**
                   - 한국 시장:
                   - 미국 시장:

                2. **상승/하락 원인 분석**:
                   - 환율(원달러/엔화) 변동의 의미.
                   - 한국 부동산 심리(리츠 지표)와 증시 연관성.
                   - 경기 침체 여부(구리, 하이일드 참고).

                3. **위험 신호 점검**:
                   - SOFR, 국채금리(장단기), VIX 위주.

                4. **실전 투자 전략**:
                   - 주식 vs 현금 비중 조언.
                   - 주목해야 할 섹터 제안.
                
                중요한 부분은 **굵은 글씨**로 강조해 주세요.
                """
                
                result = generate_ai_report(prompt, api_key)
                st.markdown(result)
