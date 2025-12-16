import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai
import feedparser
from datetime import datetime, timedelta

# 1. 화면 기본 설정
st.set_page_config(page_title="AI 투자 비서 V8.0", layout="wide")
st.title("🌏 AI 투자 비서 & 뉴스룸 (V8.0)")
st.caption("국가별(한국/미국) 심층 분석 및 기간별 수익률 추적 기능 탑재")

# --- [사이드바: 설정] ---
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("Google API Key (AI용)", type="password", help="aistudio.google.com에서 발급")
    
    # 기간 선택 기능 강화 (오늘, 1주, 1달, 1년)
    period_options = {
        "오늘 (1일)": 2, # 전일 대비를 위해 최소 2일치 필요
        "최근 1주일": 7,
        "최근 1개월": 30,
        "최근 3개월": 90,
        "최근 1년": 365
    }
    selected_period_label = st.selectbox("분석 기준 기간 (데이터 & AI)", list(period_options.keys()), index=2)
    days = period_options[selected_period_label]
    
    st.markdown("---")
    st.info(f"선택된 기간: {selected_period_label}\n\nAI가 이 기간 동안의 추세를 분석합니다.")
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

# AI에게 전달할 데이터 저장소 (구조 업그레이드)
ai_data_context = {
    "korea_market": {}, # 한국 관련 지표
    "us_market": {},    # 미국 관련 지표
    "common": {}        # 공통 지표 (원자재 등)
}

k_news_summary = ""
us_news_summary = ""

# 3. 차트 그리기 및 데이터 가공 함수
def draw_chart(name, info):
    symbol = info["symbol"]
    line_color = info["color"]
    try:
        # 데이터 수집
        if info["type"] == "fdr":
            df = fdr.DataReader(symbol, start_date, end_date)
        else:
            df = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if len(df) == 0: return

        # 컬럼 정리
        if 'Close' in df.columns: col = df['Close']
        elif 'Adj Close' in df.columns: col = df['Adj Close']
        elif 'DATE' in df.columns: col = df['DATE']
        else: col = df.iloc[:, 0]
        if hasattr(col, 'columns'): col = col.iloc[:, 0]
        col = col.dropna()
            
        # --- [수익률 계산 로직 강화] ---
        last_val = float(col.iloc[-1]) # 현재가
        prev_val = float(col.iloc[-2]) # 전일 종가
        start_val = float(col.iloc[0]) # 기간 시작일 종가
        
        daily_diff_pct = (last_val - prev_val) / prev_val * 100 if prev_val != 0 else 0
        period_diff_pct = (last_val - start_val) / start_val * 100 if start_val != 0 else 0
        
        # AI용 데이터 포맷팅
        data_str = f"현재: {last_val:,.2f} (전일대비: {daily_diff_pct:+.2f}%, {selected_period_label} 변동: {period_diff_pct:+.2f}%)"
        
        # 시장별 데이터 분류 (AI에게 똑똑하게 전달하기 위함)
        if "코스피" in name or "원/달러" in name:
            ai_data_context["korea_market"][name] = data_str
        elif "S&P" in name or "나스닥" in name or "SOFR" in name or "국채" in name or "반도체" in name:
            ai_data_context["us_market"][name] = data_str
        else:
            ai_data_context["common"][name] = data_str # 비트코인, 유가 등

        # --- [차트 시각화] ---
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
    st.info("왼쪽은 한국 시장, 오른쪽은 미국 시장을 집중 분석합니다.")
    
    # 두 개의 컬럼으로 분리
    col_ai_kr, col_ai_us = st.columns(2)
    
    # ---------------- [한국 증시 분석] ----------------
    with col_ai_kr:
        st.subheader("🇰🇷 한국 증시 분석")
        if st.button("한국 시장 분석 실행"):
            if not api_key:
                st.error("API Key 필요")
            else:
                with st.spinner("한국 시장 분석 중..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        prompt = f"""
                        당신은 한국 주식 시장(KOSPI, KOSDAQ) 전문 애널리스트입니다.
                        설정된 기간({selected_period_label}) 동안의 데이터를 바탕으로 한국 증시를 분석해주세요.

                        [분석 데이터]
                        - 한국 지표: {ai_data_context['korea_market']}
                        - 글로벌 참고 지표: {ai_data_context['common']}
                        - 미국 시장 영향: {ai_data_context['us_market']} (참고용)
                        
                        [관련 뉴스]
                        {k_news_summary}

                        [작성 요청]
                        1. **{selected_period_label} 동안의 한국 증시 총평**: (상승세/하락세/보합세)
                        2. **주요 원인**: 환율 및 반도체(미국장 영향)와 연관지어 설명.
                        3. **투자 전략**: 지금 삼성전자나 코스피 지수를 매수해야 할까? (매수/매도/관망)
                        """
                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                    except Exception as e: st.error(f"오류: {e}")

    # ---------------- [미국 증시 분석] ----------------
    with col_ai_us:
        st.subheader("🇺🇸 미국 증시 분석")
        if st.button("미국 시장 분석 실행"):
            if not api_key:
                st.error("API Key 필요")
            else:
                with st.spinner("미국 시장 분석 중..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        prompt = f"""
                        당신은 월가(Wall St)의 수석 전략가입니다.
                        설정된 기간({selected_period_label}) 동안의 데이터를 바탕으로 미국 증시를 분석해주세요.

                        [분석 데이터]
                        - 미국 지표: {ai_data_context['us_market']}
                        - 글로벌 지표: {ai_data_context['common']}
                        
                        [관련 뉴스]
                        {us_news_summary}

                        [작성 요청]
                        1. **{selected_period_label} 동안의 월가 흐름 요약**: (Bull/Bear Market)
                        2. **리스크 점검**: SOFR 금리와 국채 금리 변화에 따른 유동성 분석.
                        3. **섹터 전략**: 기술주(나스닥) vs 가치주(S&P500), 어디에 비중을 둘까?
                        """
                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                    except Exception as e: st.error(f"오류: {e}")
