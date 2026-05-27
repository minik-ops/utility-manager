import streamlit as st
from supabase import create_client, Client
import pandas as pd

# 페이지 기본 설정
st.set_page_config(page_title="수도/전기 요금 검증", layout="wide")

# Supabase 클라이언트 초기화
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

st.title("⚡ 수도/전기 요금 검증 시스템")
st.markdown("---")

# 최근 지침(이전 달 데이터) 불러오기 함수
def get_previous_readings():
    response = supabase.table("utility_records").select("f_read, g_read").order("id", desc=True).limit(1).execute()
    if response.data:
        return response.data[0]['f_read'], response.data[0]['g_read']
    return 0.0, 0.0

prev_f, prev_g = get_previous_readings()

# 입력 폼 구성 (엑셀과 동일한 좌/우 레이아웃)
with st.form("utility_form"):
    month = st.text_input("📅 검침월 (예: 2026-05)", placeholder="YYYY-MM 형식으로 입력")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 [좌측] 자체 실 검측 데이터")
        f_curr = st.number_input("F열 (메인/교회 지침)", min_value=0.0, step=1.0, format="%.1f")
        g_curr = st.number_input("G열 (5층 지침)", min_value=0.0, step=1.0, format="%.1f")
        st.caption(f"💡 참고: DB에 저장된 이전 달 메인 지침은 **{prev_f}**, 5층 지침은 **{prev_g}** 입니다.")
        
    with col2:
        st.subheader("🧾 [우측] 집주인 청구 데이터")
        ll_prev = st.number_input("집주인 이전 지침", min_value=0.0, step=1.0, format="%.1f")
        ll_curr = st.number_input("집주인 이번 지침", min_value=0.0, step=1.0, format="%.1f")
        ll_5f_use = st.number_input("5층 통보 사용량", min_value=0.0, step=1.0, format="%.1f")

    submitted = st.form_submit_button("계산 및 DB 저장", type="primary")

# 데이터 처리 및 저장 로직
if submitted:
    if not month:
        st.error("검침월을 입력해 주세요.")
    else:
        # 1. 좌측 자체 계산 로직 (이번 지침 - 이전 지침)
        h_use = max(0, g_curr - prev_g) # 5층 실사용량
        my_church_use = max(0, (f_curr - prev_f) - h_use) # 교회 실사용량

        # 2. 우측 집주인 청구 계산 로직
        ll_total_use = max(0, ll_curr - ll_prev)
        ll_church_use = max(0, ll_total_use - ll_5f_use)
        
        # 3. 최종 요금 계산 (단가 200원)
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

# DB에서 전체 데이터 불러와 표(DataFrame)로 출력
response = supabase.table("utility_records").select("*").order("month", desc=True).execute()

if response.data:
    df = pd.DataFrame(response.data)
    
    # 불필요한 id, created_at 컬럼 숨김 및 컬럼명 한글화
    display_df = df.drop(columns=['id', 'created_at'])
    display_df.columns = [
        "검침월", "F지침(메인)", "G지침(5층)", "H(5층사용)", 
        "실교회사용", "집주인(이전)", "집주인(이번)", 
        "집주인(5층사용)", "청구교회사용", "최종청구액(원)"
    ]
    
    # 요금 콤마 포맷팅 적용 등 스타일링
    st.dataframe(
        display_df.style.format({"최종청구액(원)": "{:,.0f}"}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("아직 등록된 요금 데이터가 없습니다.")