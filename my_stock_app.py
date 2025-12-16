import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
import feedparser
from datetime import datetime, timedelta

# 1. 화면 기본 설정
st.set_page_config(page_title="AI 투자 비서 V9.0", layout="wide")
st.title("🌏 AI 투자 비서 & 뉴스룸 (V9.0)")
st.caption("🚀 Gemini 3 Pro (최신 모델) 적용 및 자동 롤백 시스템")

# --- [사이드바: 설정] ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("Google API Key (AI용)", type="password", help="aistudio.google.com에서 발급")
    
    period_options = {
        "오늘 (1일)": 2, 
        "최근 1주일": 7,
        "최근 1개월": 30,
        "최근 3개월": 90,
        "최근 1년": 365
    }
    selected_period_label = st.selectbox("분석 기준 기간", list(period_options.keys()), index=2)
    days = period_options[selected_period_label]
    
    st.markdown("---")
    st.info("💡 팁: Gemini 3 Pro는 최신 모델이라 응답 속도가 조금 느릴 수 있지만, 분석 깊이가 훨씬 깊습니다.")
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

ai_data_context = {"korea_market": {}, "us_market": {}, "common": {}}
k_news_summary = "뉴스 로딩 중..."
us_news_summary = "뉴스 로딩 중..."

# 3. 차트 그리기 함수 (V7.9 디자인 유지)
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
        start_val = float(col.iloc[0])
        
        daily_diff_pct = (last_val - prev_val) / prev_val * 100 if prev_val != 0 else 0
        period_diff_pct = (last_val - start_val) / start_val * 100 if start_val != 0 else 0
        
        data_str = f"현재: {last_val:,.2f} ({selected_period_label} 변동: {period_diff_pct:+.2f}%)"
        
        if "코스피" in name or "원/달러" in name:
            ai_data_context["korea_market"][name] = data_str
        elif "S&P" in name or "나스닥" in name or "SOFR" in name or "국채" in name or "반도체" in name:
            ai_data_context["us_market"][name] = data_str
        else:
            ai_data_context["common"][name] = data_str

        st.metric(label=name, value=f"{last_val:,.2f}", delta=f"{daily_diff_pct:.2f}% (기간: {period_diff_pct:+.2f}%)")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=col.index, y=col, mode='lines', name=name,
            line=dict(color=line_color, width=2),
            fill='tozeroy',
            hovertemplate='%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            height=250, margin=dict(l=5, r=5, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=True, gridcolor='lightgray', side='right')
        )
        st.plotly_chart(fig, use_container_width=True, config={'staticPlot': False})
        st.divider()
        
    except: pass

# 4. 뉴스 가져오기 함수
def get_news_feed(rss_url, max_items=5):
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:max_items]:
            link = getattr(entry, 'link', '#') 
            title = getattr(entry, 'title', '제목 없음')
            news_items.append(f"- [{title}]({link})")
        return news_items
    except Exception as e:
        return [f"뉴스 로딩 실패: {e}"]

# 5. AI 응답 생성 함수 (모델 자동 전환 로직 포함)
def generate_ai_report(prompt, api_key):
    genai.configure(api_key=api_key)
    
    # 1순위: Gemini 3 Pro 시도
    try:
        model = genai.GenerativeModel('gemini-3-pro-preview')
        response = model.generate_content(prompt)
        return f"🚀 **Gemini 3 Pro 분석 결과**\n\n{response.text}"
    except Exception as e_3pro:
        # 3 Pro 실패 시 로그 남기고 2순위 시도
        error_msg = str(e_3pro)
        
        # 2순위: Gemini 2.5 Flash (이전에 성공했던 모델)
        try:
            model_fallback = genai.GenerativeModel('gemini-2.5-flash')
            response_fallback = model_fallback.generate_content(prompt)
            return f"⚠️ **알림:** Gemini 3 Pro 접근이 제한되어 'Gemini 2.5 Flash'로 분석했습니다.\n(원인: {error_msg})\n\n---\n{response_fallback.text}"
        except Exception as e_final:
             return f"❌ 분석 실패: 모든 모델 연결에 실패했습니다.\n1차 오류: {error_msg}\n2차 오류: {e_final}"

# --- [메인 UI] ---
tab_chart, tab_news, tab_ai = st.tabs(["📈 시장 지표", "📰 실시간 뉴스", "🤖 AI 국가별 분석"])

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
    col_k, col_u = st.columns(2)
    with col_k:
        st.subheader("🇰🇷 한국 증시 뉴스 (매일경제)")
        k_news = get_news_feed("https://www.mk.co.kr/rss/30100041/", 7) 
        for news in k_news: st.markdown(news)
        k_news_summary = "\n".join(k_news)
    with col_u:
        st.subheader("🇺🇸 미국 뉴스 (CNBC)")
        us_news = get_news_feed("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 7)
        for news in us_news: st.markdown(news)
        us_news_summary = "\n".join(us_news)

with tab_ai:
    st.header(f"🤖 AI 심층 분석 (기준: {selected_period_label})")
    col_ai_kr, col_ai_us = st.columns(2)
    
    # ---------------- [한국 증시 분석] ----------------
    with col_ai_kr:
        st.subheader("🇰🇷 한국 증시 분석")
        if st.button("한국 시장 분석 실행"):
            if not api_key:
                st.error("API Key 필요")
            else:
                with st.spinner("Gemini 3 Pro가 한국 시장을 심층 분석 중..."):
                    prompt = f"""
                    당신은 대한민국 최고의 주식 전략가입니다.
                    기간: {selected_period_label}
                    
                    [데이터]
                    - 한국 지표: {ai_data_context.get('korea_market')}
                    - 환율/금리: {ai_data_context.get('common')} (원달러 환율 중요)
                    
                    [뉴스]
                    {k_news_summary}

                    위 정보를 바탕으로:
                    1. **{selected_period_label} 한국 증시 총평** (외국인 수급/환율 영향 위주)
                    2. **반도체/수출주 전망**
                    3. **개인 투자자 행동 강령** (매수/매도/홀딩)
                    """
                    result_text = generate_ai_report(prompt, api_key)
                    st.markdown(result_text)

    # ---------------- [미국 증시 분석] ----------------
    with col_ai_us:
        st.subheader("🇺🇸 미국 증시 분석")
        if st.button("미국 시장 분석 실행"):
            if not api_key:
                st.error("API Key 필요")
            else:
                with st.spinner("Gemini 3 Pro가 월가를 분석 중..."):
                    prompt = f"""
                    당신은 월가(Wall St)의 전설적인 펀드매니저입니다.
                    기간: {selected_period_label}
                    
                    [데이터]
                    - 미국 지표: {ai_data_context.get('us_market')}
                    - 금리/유가: {ai_data_context.get('common')}
                    
                    [뉴스]
                    {us_news_summary}

                    위 정보를 바탕으로:
                    1. **{selected_period_label} 월가 트렌드** (AI/기술주 vs 경기민감주)
                    2. **매크로 리스크** (SOFR 금리 발작 여부 체크)
                    3. **포트폴리오 전략** (주식 비중 확대/축소)
                    """
                    result_text = generate_ai_report(prompt, api_key)
                    st.markdown(result_text)
