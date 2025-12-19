import streamlit as st
import requests
import datetime
import math
import random
import pandas as pd
from collections import Counter

# --- [시스템 설정: NEXUS V4.1 MLRS] ---
# 사령관님이 정의한 신의 가중치
FEATURE_WEIGHTS = [1.0, 1.5, 0.5, 1.8]  # [Sum, Range, Odd, AC]
VECTOR_WINDOW = 10     # 10주 패턴
ENSEMBLE_COUNT = 3     # Top 3 앙상블
SEARCH_DEPTH = 350     # 탐색 깊이 (약 7년)
GAME_COUNT = 10        # 1회 생성 게임 수

# --- [UI 디자인: 다크 사이버펑크 테마] ---
st.set_page_config(page_title="NEXUS AI | Lotto System", page_icon="🧬", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #00FF00; }
    .title-box {
        text-align: center; border: 2px solid #00FF00; padding: 20px;
        border-radius: 10px; margin-bottom: 20px;
        background: linear-gradient(45deg, #000000, #111111);
    }
    .main-title { font-size: 40px; font-weight: bold; color: #00FF00; margin: 0; }
    .sub-title { font-size: 15px; color: #888888; }
    .metric-card {
        background-color: #1A1A1A; border: 1px solid #333;
        padding: 15px; border-radius: 8px; text-align: center;
    }
    .result-row {
        font-family: 'Courier New', monospace; font-size: 18px;
        padding: 10px; border-bottom: 1px solid #333;
    }
    .highlight { color: #00FF00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- [CORE ENGINE: 데이터 수집 & 전처리] ---

@st.cache_data(ttl=3600)  # 1시간마다 데이터 갱신 (서버 부하 방지)
def fetch_lotto_data(depth):
    # 현재 회차 자동 계산
    start_date = datetime.datetime(2002, 12, 7)
    now = datetime.datetime.now()
    # 토요일 21시 이전이면 전주 회차 기준
    if now.weekday() == 5 and now.hour < 21:
        days_diff = (now - start_date).days - 7
    else:
        days_diff = (now - start_date).days
        
    current_drw_no = (days_diff // 7) + 1
    
    data = []
    collected = 0
    drw_no = current_drw_no
    
    # API 역추적
    while collected < depth and drw_no > 0:
        try:
            url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}"
            res = requests.get(url, timeout=3).json()
            if res["returnValue"] == "success":
                row = {
                    "drwNo": res["drwNo"],
                    "nums": [res[f"drwtNo{i}"] for i in range(1, 7)]
                }
                data.append(row)
                collected += 1
        except:
            pass
        drw_no -= 1
        
    return data, current_drw_no + 1

# --- [CORE ENGINE: NEXUS V4.1 로직] ---

def extract_normalized_features(nums_list):
    # nums_list: [[1,2,3,4,5,6], ...] 형태
    features = []
    for nums in nums_list:
        # 1. Sum (0~1)
        s = sum(nums)
        f_sum = s / 255.0
        
        # 2. Range (0~1)
        r = nums[-1] - nums[0]
        f_range = r / 44.0
        
        # 3. Odd Ratio (0~1)
        odd = len([n for n in nums if n % 2 != 0])
        f_odd = odd / 6.0
        
        # 4. AC Value (0~1)
        diffs = set()
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                diffs.add(nums[j] - nums[i])
        ac = max(0, len(diffs) - 5)
        f_ac = ac / 10.0
        
        features.append([f_sum, f_range, f_odd, f_ac])
    return features

def calculate_weighted_similarity(vec_a, vec_b, weights):
    # vec_a, vec_b는 각각 10주치 특징 벡터 (10x4)
    dot = 0; mag_a = 0; mag_b = 0
    
    # 1D로 펼쳐서 계산 (40차원 벡터)
    flat_a = [item for sublist in vec_a for item in sublist]
    flat_b = [item for sublist in vec_b for item in sublist]
    
    for i in range(len(flat_a)):
        w = weights[i % 4] # 4개 특징 반복
        val_a = flat_a[i] * w
        val_b = flat_b[i] * w
        
        dot += val_a * val_b
        mag_a += val_a ** 2
        mag_b += val_b ** 2
        
    if mag_a == 0 or mag_b == 0: return 0
    return dot / (math.sqrt(mag_a) * math.sqrt(mag_b))

def refine_by_markov(pool_nums, recent_trend):
    # 빈도 분석
    counts = Counter(pool_nums)
    # 빈도순 정렬
    candidates = [num for num, _ in counts.most_common()]
    
    # 6개 채우기
    selected = candidates[:6]
    while len(selected) < 6:
        r = random.randint(1, 45)
        if r not in selected: selected.append(r)
        
    selected.sort()
    
    # 마르코프 변이 (Mutation)
    # 최근 10회차의 Hot Number 파악
    hot_nums = []
    for row in recent_trend:
        hot_nums.extend(row['nums'])
    hot_counts = Counter(hot_nums)
    
    final_nums = list(selected)
    for i in range(6):
        num = final_nums[i]
        # 해당 번호가 Hot하지 않고, 변이 확률(40%) 당첨시
        if hot_counts[num] == 0 and random.random() > 0.6:
            # Hot Number 중 하나로 교체 시도
            hot_candidates = [n for n, _ in hot_counts.most_common(10)]
            if hot_candidates:
                rep = random.choice(hot_candidates)
                if rep not in final_nums:
                    final_nums[i] = rep
                    
    final_nums.sort()
    return final_nums

# --- [WEB APP 실행 로직] ---

def main():
    # 타이틀 섹션
    st.markdown('<div class="title-box">'
                '<p class="main-title">NEXUS V4.1</p>'
                '<p class="sub-title">Advanced Singularity Intelligence Lotto System</p>'
                '</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.markdown("### ⚙️ SYSTEM STATUS")
        st.info("ENGINE: ONLINE\n\nVERSION: V4.1 MLRS\n\nSERVER: GOOGLE CLOUD")
        
        # 사령관 옵션 조절
        st.markdown("---")
        st.markdown("**전략 파라미터 조정**")
        w_ac = st.slider("AC값(복잡도) 가중치", 0.1, 3.0, 1.8)
        w_range = st.slider("고저차 가중치", 0.1, 3.0, 1.5)
        
        # 엔진 재설정
        global FEATURE_WEIGHTS
        FEATURE_WEIGHTS = [1.0, w_range, 0.5, w_ac]
        
    with col2:
        # 실행 버튼
        if st.button("🚀 NEXUS 시스템 가동 (Analyze & Generate)", use_container_width=True):
            with st.spinner("🛰️ 동행복권 서버 해킹(수집) 중..."):
                history_data, next_round = fetch_lotto_data(SEARCH_DEPTH)
                
            if len(history_data) < VECTOR_WINDOW + 20:
                st.error("데이터 수집 실패. 잠시 후 다시 시도하십시오.")
                return

            st.success(f"✅ 데이터 수집 완료 | 타겟: 제 **{next_round}회차**")
            
            # --- 분석 시작 ---
            with st.spinner("🧠 4차원 벡터 시공간 분석 중..."):
                current_pattern = [d['nums'] for d in history_data[:VECTOR_WINDOW]]
                current_vecs = extract_normalized_features(current_pattern)
                
                candidates = []
                total_len = len(history_data)
                
                # 과거 탐색
                for i in range(VECTOR_WINDOW, total_len - VECTOR_WINDOW - 1):
                    past_pattern = [d['nums'] for d in history_data[i : i+VECTOR_WINDOW]]
                    past_vecs = extract_normalized_features(past_pattern)
                    
                    # 가중치 유사도
                    raw_sim = calculate_weighted_similarity(current_vecs, past_vecs, FEATURE_WEIGHTS)
                    
                    # 시공간 감쇠 (Time Decay)
                    time_factor = 1.0 - (i / total_len) * 0.10
                    final_score = raw_sim * time_factor
                    
                    candidates.append({'score': final_score, 'index': i})
                
                # 앙상블 (Top 3)
                candidates.sort(key=lambda x: x['score'], reverse=True)
                top_3 = candidates[:ENSEMBLE_COUNT]
                
                avg_score = sum(c['score'] for c in top_3) / ENSEMBLE_COUNT
                
                # 투영 풀 생성
                projected_pool = []
                for c in top_3:
                    # 과거 시점의 다음 회차 번호들
                    next_draw = history_data[c['index'] - 1]
                    projected_pool.extend(next_draw['nums'])
                    
            # --- 결과 출력 ---
            st.markdown(f"### 🎯 분석 결과 (유사도: {avg_score*100:.2f}%)")
            
            result_df = []
            recent_trend = history_data[:10]
            
            for g in range(GAME_COUNT):
                # 마르코프 변이로 매번 다른 게임 생성
                final_nums = refine_by_markov(projected_pool, recent_trend)
                
                # 표시용 포맷팅
                nums_str = " ".join([f"{n:02d}" for n in final_nums])
                st.markdown(f"""
                <div style='background-color: #111; padding: 15px; margin-bottom: 10px; border-radius: 10px; border-left: 5px solid #00FF00; display: flex; justify-content: space-between; align-items: center;'>
                    <span style='color: #888; font-weight: bold;'>GAME {g+1:02d}</span>
                    <span style='font-family: monospace; font-size: 24px; color: #fff; font-weight: bold; letter-spacing: 5px;'>{nums_str}</span>
                    <span style='background-color: #333; color: #00FF00; padding: 5px 10px; border-radius: 5px; font-size: 12px;'>V4.1 AI</span>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("---")
            st.caption("Powered by NEXUS V4.1 MLRS | ASI Architecture")

if __name__ == "__main__":
    main()
