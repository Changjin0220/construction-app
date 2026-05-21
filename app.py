# 실행: streamlit run app.py --server.port 8501
# DB 파일(construction.db)은 최초 실행 시 자동 생성됨

"""
app.py - 공정률 관리 Streamlit 메인 앱
"""

import streamlit as st
import plotly.express as px
import pandas as pd

from database import (
    init_db,
    get_all_constructions,
    add_construction,
    update_construction_info,
    update_progress,
    add_daily_work,
    get_progress_history,
    delete_construction,
)

# ── 페이지 설정 ───────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="공정률 관리")

# ── DB 초기화 ─────────────────────────────────────────────────
init_db()

# ── 공통 CSS 주입 ─────────────────────────────────────────────
st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    #MainMenu { display: none !important; }

    .block-container { padding: 0.5rem 1rem !important; }

    table.progress-table {
        width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
        font-size: 11px;
        line-height: 1.4;
    }
    table.progress-table th {
        background: #1e2a3a;
        color: #c8d8ea;
        text-align: center;
        padding: 5px 4px;
        border: 1px solid #2e3d50;
        font-weight: 600;
        white-space: normal;
        word-break: keep-all;
    }
    table.progress-table td {
        padding: 5px 4px;
        border: 1px solid #e0e8f0;
        text-align: center;
        vertical-align: middle;
        white-space: normal;
        word-break: break-word;
    }
    table.progress-table tr:nth-child(even) td { background: #f7fafd; }
    table.progress-table tr:hover td { background: #eaf2fb; }

    .badge {
        display: inline-block;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
        margin: 1px 0;
        white-space: nowrap;
    }
    .badge-low   { background: #FEF4E1; color: #633806; }
    .badge-mid   { background: #E1F5EE; color: #085041; }
    .badge-high  { background: #E6F1FB; color: #0C447C; }

    .summary-card {
        background: #1e2a3a;
        border-radius: 8px;
        padding: 10px 14px;
        text-align: center;
        color: white;
        margin-bottom: 8px;
    }
    .summary-card .val { font-size: 24px; font-weight: 700; }
    .summary-card .lbl { font-size: 11px; color: #8ab4d4; }

    .edit-form-wrap {
        background: #f0f6ff;
        border-left: 3px solid #378ADD;
        border-radius: 6px;
        padding: 8px 14px;
        margin-top: 4px;
        margin-bottom: 6px;
    }
    .daily-form-wrap {
        background: #f0fff8;
        border-left: 3px solid #1D9E75;
        border-radius: 6px;
        padding: 8px 14px;
        margin-top: 4px;
        margin-bottom: 6px;
    }

    section[data-testid="stSidebar"] .block-container { padding: 0.5rem !important; }

    div[data-testid="column"] .stButton button {
        font-size: 11px;
        padding: 2px 6px;
        height: auto;
    }
</style>
""", unsafe_allow_html=True)


def get_badge_class(rate: float) -> str:
    if rate <= 30:   return "badge-low"
    elif rate <= 70: return "badge-mid"
    else:            return "badge-high"


def get_bar_color(rate: float) -> str:
    if rate <= 30:   return "#EF9F27"
    elif rate <= 70: return "#1D9E75"
    else:            return "#378ADD"


# ── 데이터 로드 ───────────────────────────────────────────────
df = get_all_constructions()

# ── 레이아웃 ──────────────────────────────────────────────────
col_left, col_right = st.columns([1, 3.5])


# ════════════════════════════════════════════════════════════
# 왼쪽 패널
# ════════════════════════════════════════════════════════════
with col_left:
    st.markdown("### 📊 현황 요약")

    c1, c2 = st.columns(2)
    avg_rate    = round(df["total_rate"].mean(), 1) if len(df) > 0 else 0.0
    total_count = len(df)

    with c1:
        st.markdown(f"""
        <div class="summary-card">
            <div class="val">{avg_rate}%</div>
            <div class="lbl">평균 누적 공정률</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="summary-card">
            <div class="val">{total_count}</div>
            <div class="lbl">총 공사 수</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:11px; margin:4px 0 2px 0; color:#555;">
        <span style="color:#EF9F27; font-size:14px;">●</span> ~30%&nbsp;&nbsp;
        <span style="color:#1D9E75; font-size:14px;">●</span> 30~70%&nbsp;&nbsp;
        <span style="color:#378ADD; font-size:14px;">●</span> 70%~
    </div>
    """, unsafe_allow_html=True)

    if len(df) > 0:
        df_chart = df.copy()
        df_chart["color"] = df_chart["total_rate"].apply(get_bar_color)
        fig = px.bar(df_chart, x="total_rate", y="name", orientation="h",
                     color="color", color_discrete_map="identity", text="total_rate")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            xaxis=dict(range=[0, 110], title="", showgrid=True, gridcolor="#e8ecf0"),
            yaxis=dict(title="", autorange="reversed"),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=30, t=4, b=4), height=250, font=dict(size=11),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("공사 데이터가 없습니다.")


# ════════════════════════════════════════════════════════════
# 오른쪽 패널
# ════════════════════════════════════════════════════════════
with col_right:
    st.markdown("### 📋 공사별 공정 현황")

    if len(df) == 0:
        st.info("등록된 공사가 없습니다.")
    else:
        # ── 테이블 전체를 하나로 구성, 삭제버튼은 테이블 밖 오른쪽 컬럼 ──
        # 전체를 tbl_col(테이블) + del_col(삭제버튼) 2단으로 나눔
        tbl_col, del_col = st.columns([11.5, 1])

        with tbl_col:
            # 헤더 + 전체 행을 하나의 테이블로 생성
            table_html = """
            <table class="progress-table">
              <thead>
                <tr>
                  <th style="width:11%;">공사명</th>
                  <th style="width:11%;">전체공정<br><small style="font-weight:400;color:#a0b8cc;">km / 개소</small><br><small style="font-weight:400;color:#a0b8cc;">공사기간</small></th>
                  <th style="width:10%;">올해계획공정<br><small style="font-weight:400;color:#a0b8cc;">km / 개소</small></th>
                  <th style="width:10%;">이달시공<br><small style="font-weight:400;color:#a0b8cc;">km / 개소</small></th>
                  <th style="width:10%;">누적시공<br><small style="font-weight:400;color:#a0b8cc;">km / 개소</small></th>
                  <th style="width:13%;">누적공정률<br><small style="font-weight:400;color:#a0b8cc;">전체↑ 올해↓</small></th>
                  <th style="width:21%;">당일 작업계획</th>
                  <th style="width:10%;">담당자</th>
                </tr>
              </thead>
              <tbody>
            """
            for _, row in df.iterrows():
                badge_total_cls = get_badge_class(row["total_rate"])
                badge_plan_cls  = get_badge_class(row["plan_rate"])
                name_disp   = row["name"].replace(" ", "<br>") if len(row["name"]) > 5 else row["name"]
                daily_plan  = row["daily_plan"] if row["daily_plan"] else "<span style='color:#bbb;'>-</span>"
                period_disp = f"<br><small style='color:#888;font-size:10px;'>{row['period']}</small>" if row["period"] else ""

                table_html += f"""
                <tr>
                  <td>{name_disp}</td>
                  <td>{row['total_km']:.1f} km<br>{row['total_spot']} 개소{period_disp}</td>
                  <td>{row['plan_km']:.1f} km<br>{row['plan_spot']} 개소</td>
                  <td><strong>{row['month_km']:.1f}</strong> km<br>{row['month_spot']} 개소</td>
                  <td><strong>{row['done_km']:.1f}</strong> km<br>{row['done_spot']} 개소</td>
                  <td>
                    <span class="badge {badge_total_cls}">{row['total_rate']:.1f}%</span><br>
                    <span class="badge {badge_plan_cls}">올해 {row['plan_rate']:.1f}%</span>
                  </td>
                  <td style="text-align:left;">{daily_plan}</td>
                  <td>{row['manager']}</td>
                </tr>
                """
            table_html += "</tbody></table>"
            st.html(table_html)

        with del_col:
            # 헤더 높이만큼 여백 후 각 행마다 버튼 배치
            st.markdown("<div style='margin-top:52px;'></div>", unsafe_allow_html=True)
            for _, row in df.iterrows():
                cid         = row["id"]
                confirm_key = f"confirm_del_{cid}"
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = False

                if st.button("🗑", key=f"delbtn_{cid}", use_container_width=True, help=f"{row['name']} 삭제"):
                    for _, r2 in df.iterrows():
                        st.session_state[f"confirm_del_{r2['id']}"] = False
                        st.session_state[f"daily_{r2['id']}"]       = False
                        st.session_state[f"edit_{r2['id']}"]        = False
                    st.session_state[confirm_key] = True
                    st.rerun()

        # 삭제 확인창 (테이블 아래, 해당 공사 이름 표시)
        for _, row in df.iterrows():
            cid         = row["id"]
            confirm_key = f"confirm_del_{cid}"
            if st.session_state.get(confirm_key, False):
                st.markdown(f"""
                <div style="background:#fff0f0;border-left:3px solid #e74c3c;border-radius:6px;
                            padding:8px 14px;margin:4px 0;">
                    <strong>⚠️ '{row['name']}' 을(를) 정말 삭제할까요?</strong><br>
                    <small style="color:#888;">삭제하면 공정률 이력까지 모두 사라지며 복구할 수 없습니다.</small>
                </div>
                """, unsafe_allow_html=True)
                yes_col, no_col, _ = st.columns([2, 2, 8])
                with yes_col:
                    if st.button("✅ 삭제", key=f"yes_del_{cid}", use_container_width=True):
                        delete_construction(int(cid))
                        st.session_state[confirm_key] = False
                        st.rerun()
                with no_col:
                    if st.button("✖ 취소", key=f"no_del_{cid}", use_container_width=True):
                        st.session_state[confirm_key] = False
                        st.rerun()

        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

        # ════════════════════════════════════════════════════
        # 금일 작업량 입력 섹션
        # ════════════════════════════════════════════════════
        st.markdown("#### 📥 금일 작업량 입력")

        daily_btn_cols = st.columns(min(len(df), 5))
        for i, (_, row) in enumerate(df.iterrows()):
            cid = row["id"]
            daily_key = f"daily_{cid}"
            if daily_key not in st.session_state:
                st.session_state[daily_key] = False

            with daily_btn_cols[i % 5]:
                if st.button(f"📥 {row['name']}", key=f"dbtn_{cid}", use_container_width=True):
                    for _, r2 in df.iterrows():
                        st.session_state[f"daily_{r2['id']}"] = False
                        st.session_state[f"edit_{r2['id']}"]  = False
                        st.session_state[f"confirm_del_{r2['id']}"] = False
                    st.session_state[daily_key] = True
                    st.rerun()

        for _, row in df.iterrows():
            cid = row["id"]
            daily_key = f"daily_{cid}"

            if st.session_state.get(daily_key, False):
                st.markdown(f"""
                <div class="daily-form-wrap">
                    <strong>📥 {row['name']} — 금일 작업량 입력</strong>
                    &nbsp;<small style="color:#555;">※ 입력한 양이 누적시공 및 공정률에 자동 반영됩니다</small>
                </div>
                """, unsafe_allow_html=True)

                with st.form(key=f"daily_form_{cid}"):
                    fd1, fd2, fd3 = st.columns(3)
                    with fd1:
                        d_km   = st.number_input("금일 시공 (km)",  value=0.0, step=0.1, min_value=0.0, format="%.2f")
                        d_spot = st.number_input("금일 시공 (개소)", value=0,   step=1,   min_value=0)
                    with fd2:
                        d_plan = st.text_input("당일 작업계획", value="")
                        d_by   = st.text_input("입력자 이름",  value="")
                    with fd3:
                        st.markdown(f"""
                        <div style="font-size:11px;color:#555;padding-top:4px;">
                            <b>현재 누적</b><br>
                            {float(row['done_km']):.1f} km / {int(row['done_spot'])} 개소<br><br>
                            <b>입력 후 예상 누적</b><br>
                            {float(row['done_km']):.1f} + 금일km<br>
                            {int(row['done_spot'])} + 금일개소
                        </div>
                        """, unsafe_allow_html=True)

                    ds_col, dc_col = st.columns(2)
                    with ds_col:
                        d_submitted = st.form_submit_button("💾 저장", use_container_width=True)
                    with dc_col:
                        d_cancelled = st.form_submit_button("✖ 취소", use_container_width=True)

                    if d_submitted:
                        if not d_by.strip():
                            st.warning("입력자 이름을 입력해주세요.")
                        elif d_km == 0 and d_spot == 0:
                            st.warning("금일 시공량(km 또는 개소)을 입력해주세요.")
                        else:
                            add_daily_work(int(cid), float(d_km), int(d_spot), d_plan.strip(), d_by.strip())
                            st.session_state[daily_key] = False
                            st.rerun()
                    if d_cancelled:
                        st.session_state[daily_key] = False
                        st.rerun()

        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

        # ════════════════════════════════════════════════════
        # 공사 정보 수정 섹션
        # (공사명·전체물량·올해계획·담당자·공사기간 + 누적 공정률 직접 수정)
        # ════════════════════════════════════════════════════
        st.markdown("#### ✏️ 공사 정보 / 공정률 수정")

        btn_cols = st.columns(min(len(df), 5))
        for i, (_, row) in enumerate(df.iterrows()):
            cid = row["id"]
            edit_key = f"edit_{cid}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            with btn_cols[i % 5]:
                if st.button(f"✏️ {row['name']}", key=f"btn_{cid}", use_container_width=True):
                    for _, r2 in df.iterrows():
                        st.session_state[f"edit_{r2['id']}"]        = False
                        st.session_state[f"daily_{r2['id']}"]       = False
                        st.session_state[f"confirm_del_{r2['id']}"] = False
                    st.session_state[edit_key] = True
                    st.rerun()

        for _, row in df.iterrows():
            cid = row["id"]
            edit_key = f"edit_{cid}"

            if st.session_state.get(edit_key, False):
                st.markdown(f"""
                <div class="edit-form-wrap">
                    <strong>✏️ {row['name']} — 공사 정보 및 공정률 수정</strong>
                </div>
                """, unsafe_allow_html=True)

                with st.form(key=f"form_{cid}"):
                    st.markdown("**📌 공사 기본 정보**")
                    fi1, fi2, fi3 = st.columns(3)
                    with fi1:
                        new_name    = st.text_input("공사명", value=row["name"])
                        new_manager = st.text_input("담당자", value=row["manager"])
                    with fi2:
                        new_total_km   = st.number_input("전체물량 (km)",   value=float(row["total_km"]),  step=0.1, min_value=0.0, format="%.1f")
                        new_total_spot = st.number_input("전체물량 (개소)", value=int(row["total_spot"]),   step=1,   min_value=0)
                    with fi3:
                        new_plan_km    = st.number_input("올해계획 (km)",   value=float(row["plan_km"]),   step=0.1, min_value=0.0, format="%.1f")
                        new_plan_spot  = st.number_input("올해계획 (개소)", value=int(row["plan_spot"]),    step=1,   min_value=0)

                    new_period = st.text_input(
                        "공사기간 (예: 26.5.16~27.12.31)",
                        value=row["period"] if row["period"] else "",
                        placeholder="26.5.16~27.12.31",
                    )

                    st.markdown("**📊 누적 공정률 직접 수정**")
                    fp1, fp2, fp3 = st.columns(3)
                    with fp1:
                        new_km   = st.number_input("누적 완료 (km)",   value=float(row["done_km"]),  step=0.1, min_value=0.0, format="%.1f")
                        new_spot = st.number_input("누적 완료 (개소)", value=int(row["done_spot"]),   step=1,   min_value=0)
                    with fp2:
                        new_by = st.text_input("수정자 이름", value=row["updated_by"])
                    with fp3:
                        st.markdown(f"""
                        <div style="font-size:11px;color:#555;padding-top:4px;">
                            <b>현재 누적</b><br>
                            {float(row['done_km']):.1f} km / {int(row['done_spot'])} 개소<br>
                            전체 공정률: {row['total_rate']:.1f}%<br>
                            올해 공정률: {row['plan_rate']:.1f}%
                        </div>
                        """, unsafe_allow_html=True)

                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        submitted = st.form_submit_button("💾 저장", use_container_width=True)
                    with cancel_col:
                        cancelled = st.form_submit_button("✖ 취소", use_container_width=True)

                    if submitted:
                        if not new_name.strip():
                            st.warning("공사명을 입력해주세요.")
                        elif not new_manager.strip():
                            st.warning("담당자를 입력해주세요.")
                        elif not new_by.strip():
                            st.warning("수정자 이름을 입력해주세요.")
                        else:
                            # 공사 기본 정보 수정
                            update_construction_info(
                                construction_id=int(cid),
                                name=new_name.strip(),
                                total_km=float(new_total_km),
                                total_spot=int(new_total_spot),
                                plan_km=float(new_plan_km),
                                plan_spot=int(new_plan_spot),
                                manager=new_manager.strip(),
                                period=new_period.strip(),
                            )
                            # 누적 공정률 수정 (값이 변경된 경우만)
                            if float(new_km) != float(row["done_km"]) or int(new_spot) != int(row["done_spot"]):
                                update_progress(
                                    construction_id=int(cid),
                                    done_km=float(new_km),
                                    done_spot=int(new_spot),
                                    updated_by=new_by.strip(),
                                )
                            st.session_state[edit_key] = False
                            st.rerun()

                    if cancelled:
                        st.session_state[edit_key] = False
                        st.rerun()


# ════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════
with st.sidebar:

    st.markdown("## ➕ 공사 추가")

    with st.form("add_construction_form"):
        add_name = st.text_input("공사명")
        a1, a2 = st.columns(2)
        with a1:
            add_total_km   = st.number_input("전체물량 (km)",   min_value=0.0, step=0.1, format="%.1f")
            add_plan_km    = st.number_input("올해계획 (km)",   min_value=0.0, step=0.1, format="%.1f")
        with a2:
            add_total_spot = st.number_input("전체물량 (개소)", min_value=0, step=1)
            add_plan_spot  = st.number_input("올해계획 (개소)", min_value=0, step=1)
        add_manager = st.text_input("담당자")
        add_period  = st.text_input("공사기간 (예: 26.5.16~27.12.31)", placeholder="26.5.16~27.12.31")

        add_submitted = st.form_submit_button("✅ 공사 추가", use_container_width=True)

        if add_submitted:
            if not add_name.strip():
                st.warning("공사명을 입력해주세요.")
            elif not add_manager.strip():
                st.warning("담당자를 입력해주세요.")
            elif add_total_km <= 0:
                st.warning("전체물량(km)을 입력해주세요.")
            elif add_plan_km <= 0:
                st.warning("올해계획(km)을 입력해주세요.")
            else:
                add_construction(
                    name=add_name.strip(),
                    total_km=float(add_total_km),
                    total_spot=int(add_total_spot),
                    plan_km=float(add_plan_km),
                    plan_spot=int(add_plan_spot),
                    manager=add_manager.strip(),
                    period=add_period.strip(),
                )
                st.success(f"'{add_name}' 공사가 추가되었습니다.")
                st.rerun()

    st.divider()

    st.markdown("## 🕓 수정 이력 조회")

    if len(df) > 0:
        construction_options = {row["name"]: row["id"] for _, row in df.iterrows()}
        selected_name = st.selectbox("공사 선택", options=list(construction_options.keys()), key="history_select")

        if selected_name:
            selected_id = construction_options[selected_name]
            history_df  = get_progress_history(selected_id)

            if len(history_df) == 0:
                st.info("수정 이력이 없습니다.")
            else:
                st.markdown(f"**{selected_name}** 이력 ({len(history_df)}건)")
                hist_html = """
                <table style="width:100%;border-collapse:collapse;font-size:10px;">
                <thead><tr>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">누적km</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">누적개소</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">금일km</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">금일개소</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">당일계획</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">수정자</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">수정일시</th>
                </tr></thead><tbody>
                """
                for _, hrow in history_df.iterrows():
                    hist_html += f"""
                    <tr>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['누적km']:.1f}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['누적개소']}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['금일km']:.1f}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['금일개소']}</td>
                      <td style="padding:4px;border:1px solid #ddd;">{hrow['당일계획'] or '-'}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['수정자'] or '-'}</td>
                      <td style="padding:4px;border:1px solid #ddd;font-size:10px;">{hrow['수정일시']}</td>
                    </tr>
                    """
                hist_html += "</tbody></table>"
                st.html(hist_html)
    else:
        st.info("등록된 공사가 없습니다.")
