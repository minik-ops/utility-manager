import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="수도/전기 요금 검증", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

st.title("⚡ 수도/전기 요금 검증 시스템")
st.markdown("---")

# 안전하게 정수(int)로 변환하는 함수 (소수점 제거용)
def safe_int(val):
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError):
        return 0

# 이전 달 지침 불러오기 (수도 5층 제외)
def get_previous_readings(target_month):
    response = supabase.table("utility_records").select("f_read, g_read, water_f_read").lt("month", target_month).order("month", desc=True).limit(1).execute()
    if response.data:
        d = response.data[0]
        return safe_int(d.get('f_read', 0)), safe_int(d.get('g_read', 0)), safe_int(d.get('water_f_read', 0))
    return 0, 0, 0

st.subheader("📝 검침 데이터 입력 및 수정")

# 1. 년도와 월 분리 입력 (드롭다운)
col_y, col_m = st.columns(2)
current_year = datetime.now().year
current_month = datetime.now().month

with col_y:
    sel_year = st.selectbox("📅 년도 선택", range(2020, 2036), index=(current_year - 2020))
with col_m:
    sel_month = st.selectbox("📅 월 선택", range(1, 13), index=(current_month - 1))

# 선택한 년/월을 합쳐서 YYYY-MM 형태로 변환 (DB 저장용)
target_month = f"{sel_year}-{sel_month:02d}"
st.caption(f"👉 현재 선택된 검침월: **{target_month}**")

# 해당 월의 기존 데이터 조회
response = supabase.table("utility_records").select("*").eq("month", target_month).execute()
existing_data = response.data[0] if response.data else {}

# 이전 달 지침 가져오기
prev_f, prev_g, prev_w_f = get_previous_readings(target_month)

# 탭 분리
tab1, tab2 = st.tabs(["📋 1단계: 자체 실검침 (10일 쯤)", "🧾 2단계: 집주인 청구서 (말일 쯤)"])

# --- 1단계: 자체 실검침 탭 ---
with tab1:
    st.markdown("### 🔍 우리 교회 실측 지침 입력")
    st.caption(f"💡 직전 달 지침 참고 — [전기] 메인: {prev_f} / 5층: {prev_g} | [수도] 메인: {prev_w_f}")
    
    with st.form("self_scan_form"):
        st.write("🔌 **전기 검침**")
        c1, c2 = st.columns(2)
        with c1:
            f_curr = st.number_input("메인계량기(전체)", min_value=0, step=1, value=safe_int(existing_data.get('f_read', 0)))
        with c2:
            g_curr = st.number_input("5층 계량기", min_value=0, step=1, value=safe_int(existing_data.get('g_read', 0)))
            
        st.write("💧 **수도 검침 (교회 단독)**")
        w_f_curr = st.number_input("수도계량기 (전체)", min_value=0, step=1, value=safe_int(existing_data.get('water_f_read', 0)))
        
        submit_self = st.form_submit_button("실검침 데이터 저장하기 ↵", use_container_width=True)

    if submit_self:
        h_use = max(0, g_curr - prev_g)
        my_church_use = max(0, (f_curr - prev_f) - h_use)
        
        # 수도는 5층이 없으므로, (이번달 수도계량기 - 저번달 수도계량기)가 바로 교회 실사용량
        w_church_use = max(0, w_f_curr - prev_w_f)

        upsert_data = existing_data.copy()
        upsert_data.update({
            "month": target_month,
            "f_read": f_curr,
            "g_read": g_curr,
            "h_use": h_use,
            "my_church_use": my_church_use,
            "water_f_read": w_f_curr,
            "water_church_use": w_church_use,
            "water_g_read": 0, # 더이상 쓰지 않음
            "water_h_use": 0   # 더이상 쓰지 않음
        })
        supabase.table("utility_records").upsert(upsert_data).execute()
        st.success(f"{target_month} 실검침 데이터가 저장됐어!")
        st.rerun()

    # 1단계 전용 데이터 표 출력 (전기 / 수도 완전 분리)
    st.markdown("---")
    st.subheader("📊 누적 실검침 데이터")
    res_tab1 = supabase.table("utility_records").select("month, f_read, g_read, h_use, my_church_use, water_f_read, water_church_use").order("month", desc=True).execute()
    
    if res_tab1.data:
        df1 = pd.DataFrame(res_tab1.data)
        
        # 누락 방지 처리
        if 'water_f_read' not in df1.columns: df1['water_f_read'] = 0
        if 'water_church_use' not in df1.columns: df1['water_church_use'] = 0

        # 전기 표 구성
        st.write("🔌 **전기 실검침 기록**")
        df1_elec = df1[['month', 'f_read', 'g_read', 'h_use', 'my_church_use']].copy()
        df1_elec.columns = ["검침년월", "메인계량기(전체)", "5층 계량기", "5층 사용량", "교회 실사용량"]
        st.dataframe(df1_elec.style.format(precision=0), use_container_width=True, hide_index=True)
        
        # 수도 표 구성
        st.write("💧 **수도 실검침 기록**")
        df1_water = df1[['month', 'water_f_read', 'water_church_use']].copy()
        df1_water.columns = ["검침년월", "수도계량기", "수도사용량"]
        st.dataframe(df1_water.style.format(precision=0), use_container_width=True, hide_index=True)
    else:
        st.info("입력된 실검침 데이터가 없어.")


# --- 2단계: 집주인 청구서 탭 ---
with tab2:
    st.markdown("### 🧾 집주인 통보 및 영수증 금액 입력")
    
    with st.form("landlord_bill_form"):
        st.write("🔌 **전기 청구 내역**")
        c1, c2, c3 = st.columns(3)
        with c1:
            ll_prev = st.number_input("청구서 이전 지침", min_value=0, step=1, value=safe_int(existing_data.get('ll_prev', 0)))
        with c2:
            ll_curr = st.number_input("청구서 이번 지침", min_value=0, step=1, value=safe_int(existing_data.get('ll_curr', 0)))
        with c3:
            ll_5f_use = st.number_input("청구서 5층 사용량", min_value=0, step=1, value=safe_int(existing_data.get('ll_5f_use', 0)))
            
        st.write("💧 **수도 청구 내역**")
        ll_water_bill = st.number_input("최종 청구된 수도 요금", min_value=0, step=1, value=safe_int(existing_data.get('ll_water_bill', 0)))
        
        submit_bill = st.form_submit_button("청구서 내역 업데이트하기 ↵", use_container_width=True)

    if submit_bill:
        ll_total_use = max(0, ll_curr - ll_prev)
        ll_church_use = max(0, ll_total_use - ll_5f_use)
        total_bill = ll_church_use * 200

        upsert_data = existing_data.copy()
        upsert_data.update({
            "month": target_month,
            "ll_prev": ll_prev,
            "ll_curr": ll_curr,
            "ll_5f_use": ll_5f_use,
            "ll_church_use": ll_church_use,
            "total_bill": total_bill,
            "ll_water_bill": ll_water_bill
        })
        
        if not upsert_data.get('f_read'):
            st.warning("⚠️ 1단계 실검침 데이터가 아직 입력되지 않았어. 청구 내역만 먼저 저장할게.")

        supabase.table("utility_records").upsert(upsert_data).execute()
        st.success(f"{target_month} 집주인 청구 내역이 저장됐어!")
        st.rerun()

    # 2단계 전용 데이터 표 출력 (전기 / 수도 완전 분리)
    st.markdown("---")
    st.subheader("📊 누적 청구 요금 데이터")
    res_tab2 = supabase.table("utility_records").select("month, ll_prev, ll_curr, ll_5f_use, ll_church_use, total_bill, ll_water_bill").order("month", desc=True).execute()
    
    if res_tab2.data:
        df2 = pd.DataFrame(res_tab2.data)
        
        if 'll_water_bill' not in df2.columns: df2['ll_water_bill'] = 0

        # 전기 청구 표
        st.write("🔌 **전기 요금 청구 기록**")
        df2_elec = df2[['month', 'll_prev', 'll_curr', 'll_5f_use', 'll_church_use', 'total_bill']].copy()
        df2_elec.columns = ["검침년월", "청구서 이전지침", "청구서 이번지침", "청구서 5층사용량", "교회 청구사용량", "최종 전기요금(원)"]
        
        def highlight_elec(s):
            return ['background-color: #e6f2ff; font-weight: bold' if s.name == '최종 전기요금(원)' else '' for v in s]

        st.dataframe(df2_elec.style.format({"최종 전기요금(원)": "{:,.0f}"}).format(precision=0).apply(highlight_elec, axis=0), use_container_width=True, hide_index=True)

        # 수도 청구 표
        st.write("💧 **수도 요금 청구 기록**")
        df2_water = df2[['month', 'll_water_bill']].copy()
        df2_water.columns = ["검침년월", "최종 수도요금(원)"]

        def highlight_water(s):
            return ['background-color: #eafaf1; font-weight: bold' if s.name == '최종 수도요금(원)' else '' for v in s]

        st.dataframe(df2_water.style.format({"최종 수도요금(원)": "{:,.0f}"}).format(precision=0).apply(highlight_water, axis=0), use_container_width=True, hide_index=True)

    else:
        st.info("입력된 청구 데이터가 없어.")
