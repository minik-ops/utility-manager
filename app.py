import streamlit as st
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="수도/전기 요금 검증", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

st.title("⚡ 수도/전기 요금 검증 시스템")
st.markdown("---")

# 1. 특정 월 기준 이전 달 데이터 불러오기 함수 (수정됨)
def get_previous_readings(target_month):
    # 타겟 월보다 '이전' 달의 데이터 중 가장 최근 것을 가져옴
    response = supabase.table("utility_records").select("f_read, g_read").lt("month", target_month).order("month", desc=True).limit(1).execute()
    if response.data:
        return response.data[0]['f_read'], response.data[0]['g_read']
    return 0.0, 0.0

st.subheader("📝 검침 데이터 입력 및 수정")
st.caption("먼저 검침월을 입력하고 엔터를 치세요. 기존 데이터가 있으면 자동으로 불러옵니다.")

# 2. 폼 바깥에서 검침월 먼저 입력받기
target_month = st.text_input("검침월 (예: 2026-05) ↵", placeholder="YYYY-MM 형식으로 입력 후 엔터")

# 검침월이 입력되었을 때만 폼이 나타나도록 설정
if target_month:
    # 3. DB에서 입력한 월의 데이터가 이미 있는지 조회
    response = supabase.table("utility_records").select("*").eq("month", target_month).execute()
    existing_data = response.data[0] if response.data else None

    # 이전 달 지침 불러오기
    prev_f, prev_g = get_previous_readings(target_month)

    # 4. 입력창 초기값 설정 (기존 데이터가 있으면 불러오고, 없으면 0.0)
    def_f = float(existing_data['f_read']) if existing_data else 0.0
    def_g = float(existing_data['g_read']) if existing_data else 0.0
    def_ll_prev = float(existing_data['ll_prev']) if existing_data else 0.0
    def_ll_curr = float(existing_data['ll_curr']) if existing_data else 0.0
    def_ll_5f_use = float(existing_data['ll_5f_use']) if existing_data else 0.0

    with st.form("excel_style_form"):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            f_curr = st.number_input("F열(실검측 교회)", min_value=0.0, step=1.0, value=def_f)
        with col2:
            g_curr = st.number_input("G열(실검측 5층)", min_value=0.0, step=1.0, value=def_g)
        with col3:
            ll_prev = st.number_input("청구 이전지침", min_value=0.0, step=1.0, value=def_ll_prev)
        with col4:
            ll_curr = st.number_input("청구 이번지침", min_value=0.0, step=1.0, value=def_ll_curr)
        with col5:
            ll_5f_use = st.number_input("청구 5층사용", min_value=0.0, step=1.0, value=def_ll_5f_use)

        st.caption(f"💡 자동 계산 참고: 직전 달({target_month} 기준 이전) 메인(F) 지침 **{prev_f}** / 5층(G) 지침 **{prev_g}**")
        
        # 데이터 존재 여부에 따라 버튼 이름 변경
        submit_label = "기존 데이터 업데이트 ↵" if existing_data else "새 데이터 추가하기 ↵"
        submitted = st.form_submit_button(submit_label, use_container_width=True)

    # 5. 저장 로직 (추가 및 덮어쓰기 기능 결합)
    if submitted:
        h_use = max(0, g_curr - prev_g) 
        my_church_use = max(0, (f_curr - prev_f) - h_use) 
        ll_total_use = max(0, ll_curr - ll_prev)
        ll_church_use = max(0, ll_total_use - ll_5f_use)
        total_bill = ll_church_use * 200

        # DB에 전달할 데이터 세트
        upsert_data = {
            "month": target_month,
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

        # 기존 데이터가 있으면 id를 포함시켜 '수정(Update)'으로 동작하게 함
        if existing_data:
            upsert_data['id'] = existing_data['id']

        try:
            # insert 대신 upsert(있으면 덮어쓰기, 없으면 생성) 사용
            supabase.table("utility_records").upsert(upsert_data).execute()
            st.success(f"{target_month}월 데이터가 성공적으로 저장되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류가 발생했습니다: {e}")

st.markdown("---")
st.subheader("📈 누적 요금 데이터 확인")

# 6. 하단 표 출력
response = supabase.table("utility_records").select("*").order("month", desc=True).execute()

if response.data:
    df = pd.DataFrame(response.data)
    display_df = df[['month', 'f_read', 'g_read', 'h_use', 'my_church_use', 'll_prev', 'll_curr', 'll_5f_use', 'll_church_use', 'total_bill']]
    display_df.columns = [
        "검침월", "F지침(메인)", "G지침(5층)", "H(5층사용)", 
        "실교회사용", "집주인(이전)", "집주인(이번)", 
        "집주인(5층사용)", "청구교회사용", "최종청구액(원)"
    ]
    
    def highlight_bill(s):
        return ['background-color: #e6f2ff; font-weight: bold' if s.name == '최종청구액(원)' else '' for v in s]

    styled_df = display_df.style.format({
        "F지침(메인)": "{:.1f}", "G지침(5층)": "{:.1f}", "H(5층사용)": "{:.1f}",
        "실교회사용": "{:.1f}", "집주인(이전)": "{:.1f}", "집주인(이번)": "{:.1f}",
        "집주인(5층사용)": "{:.1f}", "청구교회사용": "{:.1f}",
        "최종청구액(원)": "{:,.0f}"
    }).apply(highlight_bill)

    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("아직 등록된 요금 데이터가 없습니다.")
