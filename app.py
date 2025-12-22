import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime

# ==========================================
# [설정] 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="NEXUS COMMAND CENTER", page_icon="🏆", layout="wide")

# 스타일 커스텀 (다크 모드 & 네온)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button {
        width: 100%; border-radius: 20px; background: linear-gradient(45deg, #4f46e5, #9333ea);
        color: white; font-weight: bold; border: none; padding: 10px;
    }
    .nexus-card {
        background-color: #1a1c24; padding: 20px; border-radius: 15px;
        border: 1px solid #333; margin-bottom: 20px; text-align: center;
    }
    .ball {
        display: inline-block; width: 35px; height: 35px; line-height: 35px;
        border-radius: 50%; font-weight: bold; color: black; margin: 3px;
    }
    .ball-y { background: #fbc400; } .ball-b { background: #69c8f2; }
    .ball-r { background: #ff7272; color: white; } .ball-g { background: #aaaaaa; } .ball-gn { background: #b0d840; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# [기능 1] 스마트 DB 캐싱 (데이터 수집)
# ==========================================
# ==========================================
# [기능 1] 스마트 DB 관리 (CSV 파일 저장 방식)
# ==========================================
import os

def fetch_lotto_data():
    # 1. 파일이 있으면 읽어오고, 없으면 빈 껍데기 생성
    csv_file = 'lotto_db.csv'
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
    else:
        df = pd.DataFrame(columns=['drwNo', 'nums'])

    # 2. 현재 최신 회차 계산
    base_date = datetime.datetime(2002, 12, 7)
    today = datetime.datetime.now()
    diff_days = (today - base_date).days
    curr_drw_no = (diff_days // 7) + 1
    if today.weekday() == 5 and today.hour < 21: curr_drw_no -= 1

    # 3. 내 창고(CSV)에 마지막으로 저장된 회차 확인
    if not df.empty:
        last_saved_no = int(df['drwNo'].max())
    else:
        last_saved_no = curr_drw_no - 300 # 파일 없으면 최근 300개부터 시작

    # 4. [핵심] 없는 데이터만 다운로드 (Incremental Update)
    if last_saved_no < curr_drw_no:
        new_data = []
        # 저장된 것 다음 회차부터 ~ 최신 회차까지 반복
        for drw_no in range(last_saved_no + 1, curr_drw_no + 1):
            url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}"
            try:
                res = requests.get(url, timeout=1).json()
                if res["returnValue"] == "success":
                    # 번호 6개 묶어서 저장 (문자열 형태 "[1, 2, 3...]"로 저장됨을 주의)
                    nums = [res[f"drwtNo{j}"] for j in range(1, 7)]
                    new_data.append({
                        "drwNo": res["drwNo"],
                        "nums": str(nums) # CSV 저장을 위해 문자열로 변환
                    })
            except:
                pass
        
        # 5. 새 데이터가 있으면 기존 DB에 합치고 파일 저장
        if new_data:
            new_df = pd.DataFrame(new_data)
            df = pd.concat([df, new_df], ignore_index=True)
            df.to_csv(csv_file, index=False) # ★ 파일에 영구 저장

    # 6. 데이터 전처리 (문자열로 저장된 "[1, 2, 3]"을 다시 진짜 리스트 [1, 2, 3]으로 복구)
    #    (CSV에서 읽어오면 리스트가 아니라 글자로 읽히기 때문)
    if not df.empty:
        # 안전하게 리스트로 변환 (eval 사용)
        df['nums'] = df['nums'].apply(lambda x: eval(x) if isinstance(x, str) else x)
        
        # 최신순 정렬 (분석하기 좋게)
        df = df.sort_values(by='drwNo', ascending=False).reset_index(drop=True)

        # 300개만 잘라서 리턴 (너무 옛날 데이터는 분석에서 제외)
        return df.head(300)
    
    return df
# ==========================================
# [기능 2] NEXUS 3.0 엔진 (형태/패턴)
# ==========================================
def engine_nexus_30(df):
    vector_window = 10
    if len(df) < vector_window + 10: return [1,2,3,4,5,6], "데이터 부족"
    
    # 1. 현재 패턴 추출
    current_draws = df.iloc[0:vector_window] # 최신 10개
    
    # 2. 특징 벡터화 함수
    def get_features(draws_subset):
        features = []
        for nums in draws_subset["nums"]:
            s = sum(nums)
            r = nums[-1] - nums[0]
            odd = sum(1 for n in nums if n % 2 != 0)
            features.extend([s/255.0, r/44.0, odd/6.0])
        return np.array(features)
    
    curr_vec = get_features(current_draws)
    
    # 3. 과거 탐색 (Cosine Similarity)
    best_score = -1
    best_idx = -1
    
    # 전체 탐색
    for i in range(vector_window, len(df) - vector_window):
        past_draws = df.iloc[i : i+vector_window]
        past_vec = get_features(past_draws)
        
        # 코사인 유사도
        dot = np.dot(curr_vec, past_vec)
        norm_a = np.linalg.norm(curr_vec)
        norm_b = np.linalg.norm(past_vec)
        sim = dot / (norm_a * norm_b) if norm_a * norm_b > 0 else 0
        
        if sim > best_score:
            best_score = sim
            best_idx = i
            
    # 4. 결과 도출 (그 당시의 다음 회차 번호)
    target_idx = best_idx - 1
    if target_idx < 0: target_idx = best_idx + 1 # 예외처리
    
    pred_nums = df.iloc[target_idx]["nums"]
    target_drw = df.iloc[best_idx]["drwNo"]
    
    # 마르코프 변주 (약간 섞기)
    final_nums = sorted(list(set(pred_nums))) # 일단 그대로
    
    info = f"타겟: {target_drw}회 (유사도 {best_score*100:.1f}%)"
    return final_nums, info

# ==========================================
# [기능 3] NEXUS 4.1 엔진 (벡터/물리)
# ==========================================
def engine_nexus_41(df):
    momentum_window = 10
    scores = {n: 0 for n in range(1, 46)}
    
    # 1. 최근 5주 에너지 가중치
    for i in range(momentum_window):
        if i >= len(df): break
        nums = df.iloc[i]["nums"]
        weight = (momentum_window - i) * 1.5
        for n in nums:
            scores[n] += weight
            
    # 2. 탄성 계수 (최근 50회 미출현 가중치)
    last_appear = {n: -1 for n in range(1, 46)}
    for i in range(min(50, len(df))):
        nums = df.iloc[i]["nums"]
        for n in nums:
            if last_appear[n] == -1: last_appear[n] = i
            
    for n in range(1, 46):
        if last_appear[n] > 10: # 10주 이상 안나오면
            scores[n] += (last_appear[n] * 0.5)
            
    # 3. Top 6 추출
    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    # 랜덤성 추가 (상위 15개 중 6개)
    pool = sorted_nums[:15]
    final_nums = sorted(np.random.choice(pool, 6, replace=False))
    
    return final_nums, "⚡ 벡터/에너지 가중치 상위"

# ==========================================
# [UI] 공 색깔 렌더링
# ==========================================
def draw_balls(nums):
    html = ""
    for n in nums:
        color = "ball-gn"
        if n <= 10: color = "ball-y"
        elif n <= 20: color = "ball-b"
        elif n <= 30: color = "ball-r"
        elif n <= 40: color = "ball-g"
        html += f'<span class="ball {color}">{n}</span>'
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# [MAIN] 메인 화면
# ==========================================
st.title("🏆 NEXUS COMMAND CENTER")
st.caption(f"LV.9 Strategy Integration Dashboard | 접속: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

if st.button("🚀 전략 엔진 가동 (Start Analysis)"):
    with st.spinner("데이터 수집 및 300회차 패턴 정밀 분석 중..."):
        df = fetch_lotto_data()
        
    if df.empty:
        st.error("데이터 수집 실패. 잠시 후 다시 시도해주세요.")
    else:
        st.success(f"데이터 로드 완료! (최신: {df.iloc[0]['drwNo']}회 ~ 과거 150회차 분석)")
        
        col1, col2 = st.columns(2)
        
        # 3.0 결과 출력
        with col1:
            st.markdown("### 🟦 NEXUS 3.0 (패턴)")
            for i in range(5): # 5게임
                with st.container():
                    st.markdown(f"**GAME {i+1}**")
                    nums, info = engine_nexus_30(df) # 엔진 호출
                    draw_balls(nums)
                    st.caption(f"└ {info}")
                    st.divider()

        # 4.1 결과 출력
        with col2:
            st.markdown("### 🟩 NEXUS 4.1 (물리)")
            for i in range(5): # 5게임
                with st.container():
                    st.markdown(f"**GAME {i+1}**")
                    nums, info = engine_nexus_41(df) # 엔진 호출
                    draw_balls(nums)
                    st.caption(f"└ {info}")
                    st.divider()

        # 통합 추천
        st.markdown("### 🟨 전략적 혼합 (Top Picks)")
        with st.container():
            st.markdown("#### ⭐ 사령관 추천 1")
            nums, _ = engine_nexus_30(df)
            draw_balls(nums)
            
            st.markdown("#### ⭐ 사령관 추천 2")
            nums, _ = engine_nexus_41(df)
            draw_balls(nums)
