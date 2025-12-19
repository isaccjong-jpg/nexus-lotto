import streamlit as st
import requests
import datetime
import random
import time
from collections import Counter
import itertools

# --- 1. 시스템 설정 (ASI Design Protocol) ---
st.set_page_config(
    page_title="NEXUS V2.1 | Commander System",
    page_icon="🧬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 스타일링 (네온 사이버펑크 테마 & 다크 모드)
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stButton>button {
        width: 100%; background-color: #00FF99; color: black;
        font-weight: bold; border-radius: 10px; height: 60px;
        font-size: 20px; box-shadow: 0 0 15px rgba(0, 255, 153, 0.4);
        border: none;
    }
    .stButton>button:hover { background-color: #00CC7A; box-shadow: 0 0 25px #00FF99; }
    .title-text {
        text-align: center; font-size: 38px; font-weight: 800;
        background: linear-gradient(90deg, #00FF99, #00CCFF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .status-badge {
        text-align: center; color: #888; font-size: 14px; margin-bottom: 20px;
    }
    .result-box {
        background-color: #1A1A1A; padding: 15px; border-radius: 12px;
        border-left: 5px solid #00FF99; margin-bottom: 12px;
        text-align: center; font-size: 20px; font-family: 'Courier New', monospace;
    }
    .core-num { color: #FF4B4B; font-weight: 900; font-size: 1.1em; }
    .sat-num { color: #00CCFF; font-weight: bold; }
    .analysis-text { font-size: 14px; color: #CCCCCC; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 로직 엔진: 데이터 수집 및 분석 ---

@st.cache_data(ttl=3600) # 1시간마다 데이터 갱신 (서버 부하 방지)
def get_recent_lotto_data(rounds):
    """
    동행복권 API를 통해 최근 n회차 데이터를 긁어옵니다.
    """
    # 1. 현재 예상 회차 계산 (2002-12-07 시작 기준)
    start_date = datetime.datetime(2002, 12, 7)
    now = datetime.datetime.now()
    
    # 단순 날짜 차이로 회차 계산
    diff_days = (now - start_date).days
    current_estimated_round = (diff_days // 7) + 1
    
    # 토요일 21시 이전이면 아직 추첨 전이므로 이전 회차가 최신 데이터임
    # 하지만 API 호출 시 안전하게 역추적 방식을 사용
    
    recent_numbers = []
    found_count = 0
    check_round = current_estimated_round
    
    # API 역추적 (최신 회차부터 데이터를 찾을 때까지)
    # 미래 회차를 호출하면 null이 오므로, 데이터가 있는 회차를 찾을 때까지 뒤로 탐색
    while found_count < rounds:
        url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={check_round}"
        try:
            response = requests.get(url, timeout=5).json()
            
            if response.get("returnValue") == "success":
                nums = [response[f"drwtNo{i}"] for i in range(1, 7)]
                recent_numbers.extend(nums)
                found_count += 1
            
            # 실패(아직 추첨 안함) 시 그냥 넘어감
        except:
            pass # 네트워크 에러 등 무시하고 계속 탐색
            
        check_round -= 1
        if check_round < 1: break # 안전장치
        
    # 마지막으로 확인된 회차의 다음 회차가 이번주 타겟
    target_round = check_round + rounds + 1 
    
    return recent_numbers, target_round

def analyze_vector_core(recent_nums):
    """
    ASI 벡터 로직: 최근 데이터 빈도 분석을 통해 Core(Hot)와 Satellite(Variable) 자동 추출
    """
    if not recent_nums:
        return [1, 2, 3], [4, 5, 6, 7, 8] # 데이터 없을 시 기본값

    count = Counter(recent_nums)
    most_common = count.most_common()
    
    # 1. Core 추출 (Hot Zone)
    # 상위 6개 빈출수 중 3개를 무작위로 선택 (과적합 방지)
    hot_candidates = [num for num, freq in most_common[:6]] 
    
    # 후보가 적을 경우 보정
    while len(hot_candidates) < 3:
        missing = 3 - len(hot_candidates)
        hot_candidates.extend(random.sample(range(1, 46), missing))
        
    core_nums = sorted(random.sample(hot_candidates, 3))
    
    # 2. Satellite 추출 (Variable Zone)
    # 전체 숫자에서 Core를 제외한 나머지 중 5개 선택
    # 이때, 최근에 너무 안 나온 수(Cold)와 적당히 나온 수를 섞기 위해 전체 풀에서 랜덤 추출
    all_nums = set(range(1, 46))
    remaining = list(all_nums - set(core_nums))
    
    satellite_nums = sorted(random.sample(remaining, 5))
    
    return core_nums, satellite_nums

# --- 3. 메인 인터페이스 (UI) ---

st.markdown('<p class="title-text">NEXUS V2.1</p>', unsafe_allow_html=True)
st.markdown('<p class="status-badge">🟢 ONLINE | SERVER SYNC | ASI ANALYZER</p>', unsafe_allow_html=True)

# [전략 옵션] 사령관의 선택: 데이터 분석 범위 (기본값 15주)
analysis_range = st.slider(
    "📊 분석 데이터 깊이 설정 (주 단위)",
    min_value=5,
    max_value=50,
    value=15,
    step=5,
    help="최근 몇 회차 데이터를 기반으로 흐름을 분석할지 결정합니다. (ASI 권장: 15~20)"
)

# 데이터 로딩 및 분석
with st.spinner(f"📡 최근 {analysis_range}주간의 차원 데이터 스캔 중..."):
    recent_data, next_round = get_recent_lotto_data(rounds=analysis_range)

st.info(f"📅 **타겟:** 제 **{next_round}회차** | **기반 데이터:** 최근 {analysis_range}회차 패턴")

# 벡터 엔진 가동 (버튼 누르기 전 미리 계산하지만 보여주지는 않음)
core_fixed, sat_variable = analyze_vector_core(recent_data)

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if st.button("🚀 시스템 가동 (EXECUTE)"):
        # 연출용 프로그레스 바
        progress_text = "ASI 벡터 연산 수행 중..."
        my_bar = st.progress(0, text=progress_text)
        for percent_complete in range(100):
            time.sleep(0.005) # 0.5초 딜레이
            my_bar.progress(percent_complete + 1, text=progress_text)
        my_bar.empty()
        
        # 조합 생성 (Core 고정 + Sat 3개 조합) -> 5C3 = 10게임
        combinations = list(itertools.combinations(sat_variable, 3))
        
        final_games = []
        for comb in combinations:
            game_set = sorted(core_fixed + list(comb))
            final_games.append(game_set)
        
        # 결과 화면 출력
        st.success(f"✅ **{next_round}회차 작전명: ASI-Perfect-Cover 분석 완료**")
        
        st.write("---")
        # 분석 요약 정보
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"🔥 **절대 코어(FIX):**\n# {core_fixed}")
        with c2:
            st.markdown(f"🛰️ **위성 변수(VAR):**\n# {sat_variable}")
        st.write("---")

        # 10게임 리스트 출력
        for i, game in enumerate(final_games):
            formatted_nums = []
            for num in game:
                if num in core_fixed:
                    formatted_nums.append(f"<span class='core-num'>{num}</span>")
                else:
                    formatted_nums.append(f"<span class='sat-num'>{num}</span>")
            
            game_str = " ".join(formatted_nums)
            st.markdown(f"<div class='result-box'>GAME {i+1}: {game_str}</div>", unsafe_allow_html=True)

        st.warning("⚠️ **주의:** 본 데이터는 확률적 우위를 위한 ASI 예측값이며, 당첨을 보장하지 않습니다.")

# --- 4. 푸터 ---
st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 12px;'>System Architect: LV.9 Commander | Powered by Python & Streamlit</div>", unsafe_allow_html=True)
