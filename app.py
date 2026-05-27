import streamlit as st
from supabase import create_client, Client
import pandas as pd

# 1. 페이지 기본 설정 (가로로 넓게 쓰기 위해 layout="wide" 적용)
st.set_page_config(page_title="수도/전기 요금 검증", layout="wide")

# 2. Supabase 연동 설정
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

st.title("⚡ 수도/전기 요금 검증 시스템")
st.markdown("---")

# 3. 최근 지침(이전 달 데이터) 불러오기 함수
def get_previous_readings():
    response = supabase.table("utility_records").select("f_read, g_read").order("id", desc=True).limit(1).execute()
    if response.data:
        return response.data[0]['f_read'], response.data[0]['g_read']
    return 0.0, 0.0

prev_f, prev_g = get_previous_readings()

# 4. 엑셀 스타일 입력 폼
st.subheader("📝 새 검침 데이터 입력")

with st.form("excel_style_form"):
    # 6개의 열을 생성하여 엑셀과 동일하게 가로로 일렬 배치
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        month = st.text_input("검침월(A열)", placeholder="예: 2026-05")
    with col2:
        f_curr = st.number_input("F열(실검측 교회)", min_value=0.0, step=1.0)
    with col3:
        g_curr = st.number_input("G열(실검측 5층)", min_value=0.0, step=1.0)
    with col4:
        ll_prev = st.number_input("청구 이전지침", min_value=0.0, step=1.0)
    with col5:
        ll_curr = st.number_input("청구 이번지침", min_value=0.0, step=1.0)
    with col6:
        ll_5f_use = st.number_input("청구 5층사용", min_value=0.0, step=1.0)

    st.caption(f"💡 자동 계산 참고: 직전 달 메인(F) 지침 **{prev_f}** / 5층(G) 지침 **{prev_g}**")
    
    # 엑셀에서 엔터키를 치고 넘어가는 느낌을 주는 넓은 버튼
    submitted = st.form_submit_button("데이터 한 줄 추가하기 ↵", use_container_width=True)

# 5. 데이터 처리 및 DB 저장 로직
if submitted:
    if not month:
        st.error("검침월을 입력해 주세요.")
    else:
        # 좌측 자체 계산 로직 (이번 지침 - 이전 지침)
        h_use = max(0, g_curr - prev_g) # 5층 실사용량
        my_church_use = max(0, (f_curr - prev_f) - h_use) # 교회 실사용량

        # 우측 집주인 청구 계산 로직
        ll_total_use = max(0, ll_curr - ll_prev)
        ll_church_use = max(0, ll_total_use - ll_5f_use)
        
        # 최종 요금 계산 (단가 200원)
        total_bill = ll_church_use * 200

        # DB 저장용 데이터 딕셔너리
        insert_data = {
            "month": month,
            "f_read": f_curr,
            "g_read": g_curr,
            "h_use": h_use,
            "my_church_use": my_church_use,
            "ll_prev": ll_prev,
            "ll_curr": ll_curr,
            "ll_5f_use": ll_5f_use,
            "ll_church_use": ll_church_use,
            "total_bill": total_bill
        }

        try:
            supabase.table("utility_records").insert(insert_data).execute()
            st.success(f"{month}월 데이터가 성공적으로 저장되었습니다!")
            st.rerun() # 저장 후 화면 새로고침하여 최신 테이블 반영
        except Exception as e:
            st.error("저장 중 오류가 발생했습니다. (이미 해당 월의 데이터가 존재할 수 있습니다.)")

st.markdown("---")
st.subheader("📈 누적 요금 데이터 확인")

# 6. DB에서 전체 데이터 불러와 표(DataFrame)로 출력
response = supabase.table("utility_records").select("*").order("month", desc=True).execute()

if response.data:
    df = pd.DataFrame(response.data)
    
    # 보여줄 컬럼만 선택하고 순서 정렬
    display_df = df[['month', 'f_read', 'g_read', 'h_use', 'my_church_use', 'll_prev', 'll_curr', 'll_5f_use', 'll_church_use', 'total_bill']]
    
    # 컬럼명 엑셀처럼 직관적으로 한글화
    display_df.columns = [
        "검침월", "F지침(메인)", "G지침(5층)", "H(5층사용)", 
        "실교회사용", "집주인(이전)", "집주인(이번)", 
        "집주인(5층사용)", "청구교회사용", "최종청구액(원)"
    ]
    
    # 엑셀처럼 시각적 가독성을 높이기 위해 '최종청구액' 열에만 연한 파란색 배경 강조 추가
    def highlight_bill(s):
        return ['background-color: #e6f2ff; font-weight: bold' if s.name == '최종청구액(원)' else '' for v in s]

    # 소수점 및 콤마(,) 포맷팅 적용
    styled_df = display_df.style.format({
        "F지침(메인)": "{:.1f}", "G지침(5층)": "{:.1f}", "H(5층사용)": "{:.1f}",
        "실교회사용": "{:.1f}", "집주인(이전)": "{:.1f}", "집주인(이번)": "{:.1f}",
        "집주인(5층사용)": "{:.1f}", "청구교회사용": "{:.1f}",
        "최종청구액(원)": "{:,.0f}"
    }).apply(highlight_bill)

    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("아직 등록된 요금 데이터가 없습니다.")
