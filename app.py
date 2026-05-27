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

# 특정 월 기준 이전 달 데이터 불러오기 (전기 및 수도 포함)
def get_previous_readings(target_month):
    response = supabase.table("utility_records").select("f_read, g_read, water_f_read, water_g_read").lt("month", target_month).order("month", desc=True).limit(1).execute()
    if response.data:
        d = response.data[0]
        return d.get('f_read', 0.0), d.get('g_read', 0.0), d.get('water_f_read', 0.0), d.get('water_g_read', 0.0)
    return 0.0, 0.0, 0.0, 0.0

st.subheader("📝 검침 데이터 입력 및 수정")
target_month = st.text_input("📅 검침월 선택 (예: 2026-05) ↵", placeholder="YYYY-MM 입력 후 엔터")

if target_month:
    # 해당 월의 기존 데이터 조회
    response = supabase.table("utility_records").select("*").eq("month", target_month).execute()
    existing_data = response.data[0] if response.data else {}

    # 이전 달 지침 가져오기
    prev_f, prev_g, prev_w_f, prev_w_g = get_previous_readings(target_month)

    # 탭을 사용하여 입력 창을 완전히 분리
    tab1, tab2 = st.tabs(["📋 1단계: 자체 실검침 입력 (10일 전후)", "🧾 2단계: 집주인 청구서 입력 (말일 쯤)"])

    # --- 1단계: 자체 실검침 탭 ---
    with tab1:
        st.markdown("### 🔍 우리 교회 실측 지침 입력")
        st.caption(f"💡 직전 달 지침 참고 — 전기 메인: {prev_f} / 전기 5층: {prev_g} | 수도 메인: {prev_w_f} / 수도 5층: {prev_w_g}")
        
        with st.form("self_scan_form"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                f_curr = st.number_input("전기 F열 (메인 교회)", min_value=0.0, step=1.0, value=float(existing_data.get('f_read', 0.0)))
            with col2:
                g_curr = st.number_input("전기 G열 (5층 지침)", min_value=0.0, step=1.0, value=float(existing_data.get('g_read', 0.0)))
            with col3:
                w_f_curr = st.number_input("수도 메인 지침 (교회)", min_value=0.0, step=1.0, value=float(existing_data.get('water_f_read', 0.0)))
            with col4:
                w_g_curr = st.number_input("수도 5층 지침", min_value=0.0, step=1.0, value=float(existing_data.get('water_g_read', 0.0)))
            
            submit_self = st.form_submit_button("실검침 데이터 저장하기 ↵", use_container_width=True)

        if submit_self:
            # 전기 계산
            h_use = max(0, g_curr - prev_g)
            my_church_use = max(0, (f_curr - prev_f) - h_use)
            # 수도 계산
            w_h_use = max(0, w_g_curr - prev_w_g)
            w_church_use = max(0, (w_f_curr - prev_w_f) - w_h_use)

            # 기존 데이터가 있으면 보존하면서 덮어씀
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
            st.success("실검침 데이터가 안전하게 저장되었습니다!")
            st.rerun()

    # --- 2단계: 집주인 청구서 탭 ---
    with tab2:
        st.markdown("### 🧾 집주인 통보 및 영수증 금액 입력")
        
        with st.form("landlord_bill_form"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                ll_prev = st.number_input("집주인 전기 이전지침", min_value=0.0, step=1.0, value=float(existing_data.get('ll_prev', 0.0)))
            with col2:
                ll_curr = st.number_input("집주인 전기 이번지침", min_value=0.0, step=1.0, value=float(existing_data.get('ll_curr', 0.0)))
            with col3:
                ll_5f_use = st.number_input("집주인 통보 5층사용량", min_value=0.0, step=1.0, value=float(existing_data.get('ll_5f_use', 0.0)))
            with col4:
                ll_water_bill = st.number_input("청구된 수도 요금 (전체)", min_value=0.0, step=1.0, value=float(existing_data.get('ll_water_bill', 0.0)))
            
            submit_bill = st.form_submit_button("청구서 내역 업데이트하기 ↵", use_container_width=True)

        if submit_bill:
            # 집주인 전기 사용량 및 요금 계산 (단가 200원)
            ll_total_use = max(0, ll_curr - ll_prev)
            ll_church_use = max(0, ll_total_use - ll_5f_use)
            total_bill = ll_church_use * 200

            # 기존 데이터(1단계에서 입력한 실검침)를 유지하며 청구 내역만 추가
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
                st.warning("⚠️ 1단계 실검침 데이터가 아직 입력되지 않았습니다. 청구 내역만 먼저 저장됩니다.")

            supabase.table("utility_records").upsert(upsert_data).execute()
            st.success("집주인 청구 내역 및 요금 계산이 저장되었습니다!")
            st.rerun()

st.markdown("---")
st.subheader("📈 누적 요금 데이터 확인 (전기 & 수도)")

# 하단 표 출력 데이터 정렬
response = supabase.table("utility_records").select("*").order("month", desc=True).execute()

if response.data:
    df = pd.DataFrame(response.data)
    
    # 데이터 구조 정의 및 컬럼 배치
    cols = [
        'month', 'f_read', 'g_read', 'h_use', 'my_church_use', 
        'water_f_read', 'water_g_read', 'water_church_use',
        'll_prev', 'll_curr', 'll_5f_use', 'll_church_use', 'total_bill', 'll_water_bill'
    ]
    # 존재하지 않는 컬럼 예외 방지
    for c in cols:
        if c not in df.columns:
            df[c] = 0.0

    display_df = df[cols]
    display_df.columns = [
        "검침월", "전기F(메인)", "전기G(5층)", "전기H(5층사용)", "전기실교회", 
        "수도메인", "수도5층", "수도실교회",
        "주인이전", "주인이번", "주인5층사용", "청구교회전기", "최종전기료(원)", "청구수도료(원)"
    ]
    
    def highlight_cols(s):
        if s.name == '최종전기료(원)':
            return ['background-color: #e6f2ff; font-weight: bold' for v in s]
        elif s.name == '청구수도료(원)':
            return ['background-color: #eafaf1; font-weight: bold' for v in s]
        return ['' for v in s]

    styled_df = display_df.style.format({
        "전기F(메인)": "{:.1f}", "전기G(5층)": "{:.1f}", "전기H(5층사용)": "{:.1f}", "전기실교회": "{:.1f}",
        "수도메인": "{:.1f}", "수도5층": "{:.1f}", "수도실교회": "{:.1f}",
        "주인이전": "{:.1f}", "주인이번": "{:.1f}", "주인5층사용": "{:.1f}", "청구교회전기": "{:.1f}",
        "최종전기료(원)": "{:,.0f}", "청구수도료(원)": "{:,.0f}"
    }).apply(highlight_cols, axis=0)

    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("아직 등록된 요금 데이터가 없습니다.")
