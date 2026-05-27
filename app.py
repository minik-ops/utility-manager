import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="수도/전기 요금 통합 검증 시스템", layout="wide", page_icon="⚡")

# 2. Supabase 연결 초기화
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

def safe_int(val):
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError):
        return 0

def get_previous_readings(target_month):
    response = supabase.table("utility_records").select("f_read, g_read, water_f_read").lt("month", target_month).order("month", desc=True).limit(1).execute()
    if response.data:
        d = response.data[0]
        return safe_int(d.get('f_read', 0)), safe_int(d.get('g_read', 0)), safe_int(d.get('water_f_read', 0))
    return 0, 0, 0

# --- 헤더 영역 ---
st.title("🏢 건물 요금 통합 관리 대시보드")
st.markdown("실측 지침과 청구 요금을 비교하여 정확한 사용량을 검증하고 통계를 확인합니다.")
st.divider()

# --- 년/월 선택 영역 ---
with st.container(border=True):
    col_icon, col_y, col_m, col_info = st.columns([0.5, 2, 2, 3])
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    with col_icon:
        st.markdown("### 🗓️")
    with col_y:
        sel_year = st.selectbox("조회/입력 년도", range(2020, 2036), index=(current_year - 2020), label_visibility="collapsed")
    with col_m:
        sel_month = st.selectbox("조회/입력 월", range(1, 13), index=(current_month - 1), label_visibility="collapsed")
    
    target_month = f"{sel_year}-{sel_month:02d}"
    
    with col_info:
        st.markdown(f"**현재 선택된 관리 월: <span style='color:#1f77b4; font-size:1.2em;'>{target_month}</span>**", unsafe_allow_html=True)

response = supabase.table("utility_records").select("*").eq("month", target_month).execute()
existing_data = response.data[0] if response.data else {}
prev_f, prev_g, prev_w_f = get_previous_readings(target_month)

st.write("")

# --- 핵심: 배너 스위치 (통계 분석 추가) ---
utility_type = st.radio(
    "관리 항목 선택", 
    ["⚡ 전기 요금 관리", "💧 수도 요금 관리", "📈 종합 통계 분석"], 
    horizontal=True, 
    label_visibility="collapsed"
)
st.write("") 

# ==========================================
# ⚡ 전기 요금 관리 섹션 (기존 기능 100% 유지)
# ==========================================
if utility_type == "⚡ 전기 요금 관리":
    st.markdown("#### 📊 이번 달 전기 요약")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("실제 교회 사용량", f"{safe_int(existing_data.get('my_church_use', 0))} kWh")
    m2.metric("청구서 기준 사용량", f"{safe_int(existing_data.get('ll_church_use', 0))} kWh")
    m3.metric("최종 청구 요금", f"{safe_int(existing_data.get('total_bill', 0)):,} 원")
    
    diff = safe_int(existing_data.get('ll_church_use', 0)) - safe_int(existing_data.get('my_church_use', 0))
    m4.metric("사용량 오차 (청구 - 실측)", f"{diff} kWh", delta=diff, delta_color="inverse")
    
    st.write("")
    tab1, tab2 = st.tabs(["📋 1단계: 자체 실검침 (10일 전후)", "🧾 2단계: 집주인 청구서 (말일)"])

    with tab1:
        with st.container(border=True):
            st.markdown(f"**💡 직전 달 지침 참고 — 메인: <span style='color:blue'>{prev_f}</span> / 5층: <span style='color:blue'>{prev_g}</span>**", unsafe_allow_html=True)
            with st.form("elec_self_scan_form"):
                c1, c2 = st.columns(2)
                with c1:
                    f_curr = st.number_input("메인계량기(전체)", min_value=0, step=1, value=safe_int(existing_data.get('f_read', 0)))
                with c2:
                    g_curr = st.number_input("5층 계량기", min_value=0, step=1, value=safe_int(existing_data.get('g_read', 0)))
                submit_self = st.form_submit_button("전기 실검침 데이터 저장 ↵", type="primary", use_container_width=True)

            if submit_self:
                h_use = max(0, g_curr - prev_g)
                my_church_use = max(0, (f_curr - prev_f) - h_use)
                upsert_data = existing_data.copy()
                upsert_data.update({"month": target_month, "f_read": f_curr, "g_read": g_curr, "h_use": h_use, "my_church_use": my_church_use})
                supabase.table("utility_records").upsert(upsert_data).execute()
                st.success(f"✅ {target_month} 전기 실검침 업데이트 완료!")
                st.rerun()

    with tab2:
        with st.container(border=True):
            with st.form("elec_landlord_bill_form"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    ll_prev = st.number_input("청구서 이전 지침", min_value=0, step=1, value=safe_int(existing_data.get('ll_prev', 0)))
                with c2:
                    ll_curr = st.number_input("청구서 이번 지침", min_value=0, step=1, value=safe_int(existing_data.get('ll_curr', 0)))
                with c3:
                    ll_5f_use = st.number_input("청구서 5층 사용량", min_value=0, step=1, value=safe_int(existing_data.get('ll_5f_use', 0)))
                submit_bill = st.form_submit_button("전기 청구서 내역 업데이트 ↵", type="primary", use_container_width=True)

            if submit_bill:
                ll_total_use = max(0, ll_curr - ll_prev)
                ll_church_use = max(0, ll_total_use - ll_5f_use)
                total_bill = ll_church_use * 200
                upsert_data = existing_data.copy()
                upsert_data.update({"month": target_month, "ll_prev": ll_prev, "ll_curr": ll_curr, "ll_5f_use": ll_5f_use, "ll_church_use": ll_church_use, "total_bill": total_bill})
                supabase.table("utility_records").upsert(upsert_data).execute()
                st.success(f"✅ {target_month} 전기 청구서 내역 업데이트 완료!")
                st.rerun()

    st.divider()
    st.subheader("📚 전기 누적 데이터 확인")
    res_elec = supabase.table("utility_records").select("month, f_read, g_read, h_use, my_church_use, ll_prev, ll_curr, ll_5f_use, ll_church_use, total_bill").order("month", desc=True).execute()
    
    if res_elec.data:
        df_elec = pd.DataFrame(res_elec.data)
        st.caption("🔍 자체 실검침 기록")
        df_elec_self = df_elec[['month', 'f_read', 'g_read', 'h_use', 'my_church_use']].copy()
        df_elec_self.columns = ["검침년월", "메인계량기(전체)", "5층 계량기", "5층 사용량", "교회 실사용량"]
        st.dataframe(df_elec_self.style.format(precision=0), use_container_width=True, hide_index=True)
        
        st.write("")
        st.caption("🧾 집주인 청구 기록")
        df_elec_bill = df_elec[['month', 'll_prev', 'll_curr', 'll_5f_use', 'll_church_use', 'total_bill']].copy()
        df_elec_bill.columns = ["검침년월", "청구서 이전지침", "청구서 이번지침", "청구서 5층사용량", "교회 청구사용량", "최종 전기요금(원)"]
        
        def highlight_elec(s):
            return ['background-color: #e6f2ff; font-weight: bold' if s.name == '최종 전기요금(원)' else '' for v in s]
        st.dataframe(df_elec_bill.style.format({"최종 전기요금(원)": "{:,.0f}"}).format(precision=0).apply(highlight_elec, axis=0), use_container_width=True, hide_index=True)
    else:
        st.info("입력된 전기 데이터가 없습니다.")

# ==========================================
# 💧 수도 요금 관리 섹션 (기존 기능 100% 유지)
# ==========================================
elif utility_type == "💧 수도 요금 관리":
    st.markdown("#### 📊 이번 달 수도 요약")
    m1, m2 = st.columns(2)
    m1.metric("실제 교회 사용량", f"{safe_int(existing_data.get('water_church_use', 0))} 톤(m³)")
    m2.metric("최종 청구 요금", f"{safe_int(existing_data.get('ll_water_bill', 0)):,} 원")
    st.write("")

    tab1, tab2 = st.tabs(["📋 1단계: 자체 실검침 (10일 전후)", "🧾 2단계: 집주인 청구서 (말일)"])

    with tab1:
        with st.container(border=True):
            st.markdown(f"**💡 직전 달 지침 참고 — 메인 수도: <span style='color:#00a3e0'>{prev_w_f}</span>**", unsafe_allow_html=True)
            with st.form("water_self_scan_form"):
                w_f_curr = st.number_input("수도계량기 (전체)", min_value=0, step=1, value=safe_int(existing_data.get('water_f_read', 0)))
                submit_w_self = st.form_submit_button("수도 실검침 데이터 저장 ↵", type="primary", use_container_width=True)

            if submit_w_self:
                w_church_use = max(0, w_f_curr - prev_w_f)
                upsert_data = existing_data.copy()
                upsert_data.update({"month": target_month, "water_f_read": w_f_curr, "water_church_use": w_church_use})
                supabase.table("utility_records").upsert(upsert_data).execute()
                st.success(f"✅ {target_month} 수도 실검침 업데이트 완료!")
                st.rerun()

    with tab2:
        with st.container(border=True):
            with st.form("water_landlord_bill_form"):
                ll_water_bill = st.number_input("최종 청구된 수도 요금 (원)", min_value=0, step=1, value=safe_int(existing_data.get('ll_water_bill', 0)))
                submit_w_bill = st.form_submit_button("수도 청구 요금 업데이트 ↵", type="primary", use_container_width=True)

            if submit_w_bill:
                upsert_data = existing_data.copy()
                upsert_data.update({"month": target_month, "ll_water_bill": ll_water_bill})
                supabase.table("utility_records").upsert(upsert_data).execute()
                st.success(f"✅ {target_month} 수도 청구 내역 업데이트 완료!")
                st.rerun()

    st.divider()
    st.subheader("📚 수도 누적 데이터 확인")
    res_water = supabase.table("utility_records").select("month, water_f_read, water_church_use, ll_water_bill").order("month", desc=True).execute()
    
    if res_water.data:
        df_water = pd.DataFrame(res_water.data)
        for col in ['water_f_read', 'water_church_use', 'll_water_bill']:
            if col not in df_water.columns: df_water[col] = 0

        df_water_display = df_water[['month', 'water_f_read', 'water_church_use', 'll_water_bill']].copy()
        df_water_display.columns = ["검침년월", "수도계량기", "수도사용량", "최종 수도요금(원)"]
        
        def highlight_water(s):
            return ['background-color: #eafaf1; font-weight: bold' if s.name == '최종 수도요금(원)' else '' for v in s]
        st.dataframe(df_water_display.style.format({"최종 수도요금(원)": "{:,.0f}"}).format(precision=0).apply(highlight_water, axis=0), use_container_width=True, hide_index=True)
    else:
        st.info("입력된 수도 데이터가 없습니다.")

# ==========================================
# 📈 종합 통계 분석 섹션 (신규 기능)
# ==========================================
elif utility_type == "📈 종합 통계 분석":
    st.markdown("#### 📈 요금 및 사용량 시계열 분석")
    
    # 통계용 전체 데이터 불러오기 (과거순 정렬)
    res_stats = supabase.table("utility_records").select("*").order("month", ascending=True).execute()
    
    if res_stats.data:
        df_stats = pd.DataFrame(res_stats.data)
        
        # 숫자형 변환 처리 (에러 방지)
        cols_to_numeric = ['my_church_use', 'll_church_use', 'total_bill', 'water_church_use', 'll_water_bill']
        for col in cols_to_numeric:
            if col in df_stats.columns:
                df_stats[col] = pd.to_numeric(df_stats[col], errors='coerce').fillna(0)
            else:
                df_stats[col] = 0
                
        # 인덱스를 검침월로 설정 (그래프 x축 활용)
        df_stats.set_index('month', inplace=True)

        tab_elec, tab_water = st.tabs(["⚡ 전기 통계", "💧 수도 통계"])
        
        # --- 전기 통계 ---
        with tab_elec:
            avg_bill = df_stats['total_bill'].mean()
            max_bill = df_stats['total_bill'].max()
            
            sc1, sc2 = st.columns(2)
            sc1.metric("월 평균 전기 요금", f"{safe_int(avg_bill):,} 원")
            sc2.metric("최고 청구 요금", f"{safe_int(max_bill):,} 원")
            
            st.write("---")
            st.markdown("**📉 월별 전기 청구 요금 추이**")
            st.line_chart(df_stats['total_bill'], color="#ffaa00", height=300)
            
            st.write("---")
            st.markdown("**⚖️ 사용량 교차 검증 (우리가 실측한 양 vs 집주인이 청구한 양)**")
            st.caption("막대그래프 높이가 다르면 청구서에 과다/과소 청구가 발생했다는 의미입니다.")
            
            chart_df = df_stats[['my_church_use', 'll_church_use']].copy()
            chart_df.columns = ["우리 실측 사용량", "집주인 청구 사용량"]
            # 두 막대를 겹치지 않고 나란히 배치하기 위해 st.bar_chart 활용
            st.bar_chart(chart_df, height=350)
            
        # --- 수도 통계 ---
        with tab_water:
            avg_water = df_stats['ll_water_bill'].mean()
            max_water = df_stats['ll_water_bill'].max()
            
            sc3, sc4 = st.columns(2)
            sc3.metric("월 평균 수도 요금", f"{safe_int(avg_water):,} 원")
            sc4.metric("최고 청구 요금", f"{safe_int(max_water):,} 원")
            
            st.write("---")
            st.markdown("**📉 월별 수도 청구 요금 추이**")
            st.line_chart(df_stats['ll_water_bill'], color="#00a3e0", height=300)
            
            st.write("---")
            st.markdown("**📊 월별 수도 사용량 추이**")
            st.bar_chart(df_stats['water_church_use'], color="#00a3e0", height=350)
            
    else:
        st.info("통계를 분석할 데이터가 아직 없습니다. 데이터를 먼저 입력해 주세요.")
