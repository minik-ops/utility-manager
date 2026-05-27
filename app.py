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

# 이전 달 지침 불러오기
def get_previous_readings(target_month):
    response = supabase.table("utility_records").select("f_read, g_read, water_f_read, water_g_read").lt("month", target_month).order("month", desc=True).limit(1).execute()
    if response.data:
        d = response.data[0]
        return safe_int(d.get('f_read', 0)), safe_int(d.get('g_read', 0)), safe_int(d.get('water_f_read', 0)), safe_int(d.get('water_g_read', 0))
    return 0, 0, 0, 0

st.subheader("📝 검침 데이터 입력 및 수정")

# 1. 년도와 월 분리 입력 (드롭다운)
col_y, col_m = st.columns(2)
current_year = datetime.now().year
current_month = datetime.now().month

with col_y:
    # 2020년부터 2035년까지 선택 가능, 기본값은 현재 년도
    sel_year = st.selectbox("📅 년도 선택", range(2020, 2036), index=(current_year - 2020))
with col_m:
    # 1월부터 12월까지 선택 가능, 기본값은 현재 월
    sel_month = st.selectbox("📅 월 선택", range(1, 13), index=(current_month - 1))

# 선택한 년/월을 합쳐서 YYYY-MM 형태로 변환 (DB 저장용)
target_month = f"{sel_year}-{sel_month:02d}"
st.caption(f"👉 현재 선택된 검침월: **{target_month}**")

# 해당 월의 기존 데이터 조회
response = supabase.table("utility_records").select("*").eq("month", target_month).execute()
existing_data = response.data[0] if response.data else {}

# 이전 달 지침 가져오기
prev_f, prev_g, prev_w_f, prev_w_g = get_previous_readings(target_month)

# 탭 분리
tab1, tab2 = st.tabs(["📋 1단계: 자체 실검침 (10일 쯤)", "🧾 2단계: 집주인 청구서 (말일 쯤)"])

# --- 1단계: 자체 실검침 탭 ---
with tab1:
    st.markdown("### 🔍 우리 교회 실측 지침 입력")
    st.caption(f"💡 직전 달 지침 참고 — 전기 메인: {prev_f} / 전기 5층: {prev_g} | 수도 메인: {prev_w_f} / 수도 5층: {prev_w_g}")
    
    with st.form("self_scan_form"):
        st.write("🔌 **전기 검침**")
        c1, c2 = st.columns(2)
        with c1:
            f_curr = st.number_input("메인 계량기 (전체)", min_value=0, step=1, value=safe_int(existing_data.get('f_read', 0)))
        with c2:
            g_curr = st.number_input("5층 계량기", min_value=0, step=1, value=safe_int(existing_data.get('g_read', 0)))
            
        st.write("💧 **수도 검침**")
        c3, c4 = st.columns(2)
        with c3:
            w_f_curr = st.number_input("수도 메인 계량기 (전체)", min_value=0, step=1, value=safe_int(existing_data.get('water_f_read', 0)))
        with c4:
            w_g_curr = st.number_input("수도 5층 계량기", min_value=0, step=1, value=safe_int(existing_data.get('water_g_read', 0)))
        
        submit_self = st.form_submit_button("실검침 데이터 저장하기 ↵", use_container_width=True)

    if submit_self:
        h_use = max(0, g_curr - prev_g)
        my_church_use = max(0, (f_curr - prev_f) - h_use)
        w_h_use = max(0, w_g_curr - prev_w_g)
        w_church_use = max(0, (w_f_curr - prev_w_f) - w_h_use)

        upsert_data = existing_data.copy()
        upsert_data.update({
            "month": target_month,
            "f_read": f_curr,
            "g_read": g_curr,
            "h_use": h_use,
            "my_church_use": my_church_use,
            "water_f_read": w_f_curr,
            "water_g_read": w_g_curr,
            "water_h_use": w_h_use,
            "water_church_use": w_church_use
        })
        supabase.table("utility_records").upsert(upsert_data).execute()
        st.success(f"{target_month} 실검침 데이터가 저장됐어!")
        st.rerun()

    # 1단계 전용 데이터 표 출력
    st.markdown("---")
    st.subheader("📊 누적 실검침 데이터")
    res_tab1 = supabase.table("utility_records").select("month, f_read, g_read, h_use, my_church_use, water_f_read, water_g_read, water_h_use, water_church_use").order("month", desc=True).execute()
    
    if res_tab1.data:
        df1 = pd.DataFrame(res_tab1.data)
        # 혹시 모를 누락 컬럼 방지
        for c in ['water_h_use', 'water_church_use']:
            if c not in df1.columns: df1[c] = 0
            
        df1.columns = [
            "검침월", "전기 메인(전체)", "전기 5층", "전기 5층(사용량)", "전기 교회(실사용량)", 
            "수도 메인(전체)", "수도 5층", "수도 5층(사용량)", "수도 교회(실사용량)"
        ]
        
        # 포맷에서 소수점(precision=0) 제거
        st.dataframe(df1.style.format(precision=0), use_container_width=True, hide_index=True)
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

    # 2단계 전용 데이터 표 출력
    st.markdown("---")
    st.subheader("📊 누적 청구 요금 데이터")
    res_tab2 = supabase.table("utility_records").select("month, ll_prev, ll_curr, ll_5f_use, ll_church_use, total_bill, ll_water_bill").order("month", desc=True).execute()
    
    if res_tab2.data:
        df2 = pd.DataFrame(res_tab2.data)
        df2.columns = [
            "검침월", "청구서 이전지침", "청구서 이번지침", "청구서 5층사용량", 
            "교회 청구사용량", "최종 전기요금(원)", "최종 수도요금(원)"
        ]
        
        # 요금 부분 배경색 강조
        def highlight_cols(s):
            if s.name == '최종 전기요금(원)':
                return ['background-color: #e6f2ff; font-weight: bold' for v in s]
            elif s.name == '최종 수도요금(원)':
                return ['background-color: #eafaf1; font-weight: bold' for v in s]
            return ['' for v in s]

        # 콤마 처리 및 소수점 제거
        styled_df2 = df2.style.format({
            "최종 전기요금(원)": "{:,.0f}", 
            "최종 수도요금(원)": "{:,.0f}"
        }).format(precision=0).apply(highlight_cols, axis=0)

        st.dataframe(styled_df2, use_container_width=True, hide_index=True)
    else:
        st.info("입력된 청구 데이터가 없어.")
