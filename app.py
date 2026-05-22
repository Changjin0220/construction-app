# 실행: streamlit run app.py --server.port 8501

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

st.set_page_config(layout="wide", page_title="공정률 관리")
init_db()

st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    #MainMenu { display: none !important; }
    .block-container { padding: 0.5rem 1rem !important; }
    table.progress-table {
        width: 100%; table-layout: fixed; border-collapse: collapse;
        font-size: 11px; line-height: 1.4;
    }
    table.progress-table th {
        background: #1e2a3a; color: #c8d8ea; text-align: center;
        padding: 5px 4px; border: 1px solid #2e3d50; font-weight: 600;
    }
    table.progress-table td {
        padding: 5px 4px; border: 1px solid #e0e8f0; text-align: center;
        vertical-align: middle; word-break: break-word;
    }
    table.progress-table tr:nth-child(even) td { background: #f7fafd; }
    table.progress-table tr:hover td { background: #eaf2fb; }
    .badge { display: inline-block; border-radius: 4px; padding: 2px 6px;
             font-size: 11px; font-weight: 600; margin: 1px 0; white-space: nowrap; }
    .badge-low  { background: #FEF4E1; color: #633806; }
    .badge-mid  { background: #E1F5EE; color: #085041; }
    .badge-high { background: #E6F1FB; color: #0C447C; }
    .summary-card { background: #1e2a3a; border-radius: 8px; padding: 8px 10px;
                    text-align: center; color: white; margin-bottom: 6px; }
    .summary-card .val { font-size: 20px; font-weight: 700; }
    .summary-card .lbl { font-size: 10px; color: #8ab4d4; }
    .edit-form-wrap { background: #f0f6ff; border-left: 3px solid #378ADD;
                      border-radius: 6px; padding: 8px 14px; margin-top: 4px; margin-bottom: 6px; }
    .daily-form-wrap { background: #f0fff8; border-left: 3px solid #1D9E75;
                       border-radius: 6px; padding: 8px 14px; margin-top: 4px; margin-bottom: 6px; }
    div[data-testid="column"] .stButton button { font-size: 11px; padding: 2px 6px; height: auto; }
</style>
""", unsafe_allow_html=True)


def get_badge_class(rate):
    if rate <= 30:   return "badge-low"
    elif rate <= 70: return "badge-mid"
    else:            return "badge-high"

def get_bar_color(rate):
    if rate <= 30:   return "#EF9F27"
    elif rate <= 70: return "#1D9E75"
    else:            return "#378ADD"


df = get_all_constructions()
col_left, col_right = st.columns([0.8, 3.5])


# ── 왼쪽 패널 ─────────────────────────────────────────────────
with col_left:
    st.markdown("### 📊 현황 요약")
    avg_rate    = round(df["total_rate"].mean(), 1) if len(df) > 0 else 0.0
    total_count = len(df)
    st.markdown(f"""
    <div class="summary-card"><div class="val">{total_count}</div><div class="lbl">총 공사 수</div></div>
    <div class="summary-card"><div class="val">{avg_rate}%</div><div class="lbl">평균 누적 공정률</div></div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:10px;margin:4px 0 2px;color:#555;">
        <span style="color:#EF9F27;">●</span> ~30%&nbsp;
        <span style="color:#1D9E75;">●</span> 30~70%&nbsp;
        <span style="color:#378ADD;">●</span> 70%~
    </div>""", unsafe_allow_html=True)

    if len(df) > 0:
        df_chart = df.copy()
        df_chart["color"] = df_chart["total_rate"].apply(get_bar_color)
        df_chart["name_wrap"] = df_chart["name"].apply(lambda n: n.replace(" ", "<br>") if len(n) > 5 else n)
        fig = px.bar(df_chart, x="total_rate", y="name_wrap", orientation="h",
                     color="color", color_discrete_map="identity", text="total_rate")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            xaxis=dict(range=[0, 115], title="", showgrid=True, gridcolor="#e8ecf0"),
            yaxis=dict(title="", autorange="reversed", tickfont=dict(size=10)),
            showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=35, t=4, b=4), height=max(200, len(df)*45), font=dict(size=10),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("공사 데이터가 없습니다.")


# ── 오른쪽 패널 ───────────────────────────────────────────────
with col_right:
    st.markdown("### 📋 공사별 공정 현황")

    if len(df) == 0:
        st.info("등록된 공사가 없습니다.")
    else:
        tbl_col, del_col = st.columns([11.5, 1])
        with tbl_col:
            table_html = """
            <table class="progress-table"><thead><tr>
              <th style="width:11%;">공사명</th>
              <th style="width:11%;">전체공정<br><small style="font-weight:400;color:#a0b8cc;">km/개소·기간</small></th>
              <th style="width:10%;">올해계획공정<br><small style="font-weight:400;color:#a0b8cc;">km/개소</small></th>
              <th style="width:10%;">이달시공<br><small style="font-weight:400;color:#a0b8cc;">km/개소</small></th>
              <th style="width:10%;">누적시공<br><small style="font-weight:400;color:#a0b8cc;">km/개소</small></th>
              <th style="width:13%;">누적공정률<br><small style="font-weight:400;color:#a0b8cc;">전체↑ 올해↓</small></th>
              <th style="width:21%;">당일 작업계획</th>
              <th style="width:10%;">담당자</th>
            </tr></thead><tbody>"""
            for _, row in df.iterrows():
                b1 = get_badge_class(row["total_rate"])
                b2 = get_badge_class(row["plan_rate"])
                nm = row["name"].replace(" ", "<br>") if len(row["name"]) > 5 else row["name"]
                dp = row["daily_plan"] if row["daily_plan"] else "<span style='color:#bbb;'>-</span>"
                pd_disp = f"<br><small style='color:#888;font-size:10px;'>{row['period']}</small>" if row["period"] else ""
                table_html += f"""<tr>
                  <td>{nm}</td>
                  <td>{row['total_km']:.1f} km<br>{row['total_spot']} 개소{pd_disp}</td>
                  <td>{row['plan_km']:.1f} km<br>{row['plan_spot']} 개소</td>
                  <td><strong>{row['month_km']:.1f}</strong> km<br>{row['month_spot']} 개소</td>
                  <td><strong>{row['done_km']:.1f}</strong> km<br>{row['done_spot']} 개소</td>
                  <td><span class="badge {b1}">{row['total_rate']:.1f}%</span><br>
                      <span class="badge {b2}">올해 {row['plan_rate']:.1f}%</span></td>
                  <td style="text-align:left;">{dp}</td>
                  <td>{row['manager']}</td>
                </tr>"""
            table_html += "</tbody></table>"
            st.html(table_html)

        # 삭제 확인창
        for _, row in df.iterrows():
            cid = row["id"]
            if f"confirm_del_{cid}" not in st.session_state:
                st.session_state[f"confirm_del_{cid}"] = False
            if st.session_state.get(f"confirm_del_{cid}", False):
                st.markdown(f"""
                <div style="background:#fff0f0;border-left:3px solid #e74c3c;border-radius:6px;padding:8px 14px;margin:4px 0;">
                    <strong>⚠️ '{row['name']}' 을(를) 정말 삭제할까요?</strong><br>
                    <small style="color:#888;">삭제하면 공정률 이력까지 모두 사라지며 복구할 수 없습니다.</small>
                </div>""", unsafe_allow_html=True)
                y, n, _ = st.columns([2, 2, 8])
                with y:
                    if st.button("✅ 삭제", key=f"yes_del_{cid}", use_container_width=True):
                        delete_construction(int(cid))
                        st.session_state[f"confirm_del_{cid}"] = False
                        st.rerun()
                with n:
                    if st.button("✖ 취소", key=f"no_del_{cid}", use_container_width=True):
                        st.session_state[f"confirm_del_{cid}"] = False
                        st.rerun()

        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

        # ── 금일 작업량 입력 ──────────────────────────────────
        st.markdown("#### 📥 금일 작업량 입력")
        daily_btn_cols = st.columns(min(len(df), 5))
        for i, (_, row) in enumerate(df.iterrows()):
            cid = row["id"]
            if f"daily_{cid}" not in st.session_state:
                st.session_state[f"daily_{cid}"] = False
            is_open = st.session_state.get(f"daily_{cid}", False)
            with daily_btn_cols[i % 5]:
                lbl = f"🔼 {row['name']}" if is_open else f"📥 {row['name']}"
                if st.button(lbl, key=f"dbtn_{cid}", use_container_width=True):
                    new = not is_open
                    for _, r2 in df.iterrows():
                        st.session_state[f"daily_{r2['id']}"] = False
                        st.session_state[f"edit_{r2['id']}"]  = False
                        st.session_state[f"confirm_del_{r2['id']}"] = False
                    st.session_state[f"daily_{cid}"] = new
                    st.rerun()

        for _, row in df.iterrows():
            cid = row["id"]
            if st.session_state.get(f"daily_{cid}", False):
                st.markdown(f"""<div class="daily-form-wrap">
                    <strong>📥 {row['name']} — 금일 작업량 입력</strong>
                    &nbsp;<small style="color:#555;">※ 입력한 양이 누적시공 및 공정률에 자동 반영됩니다</small>
                </div>""", unsafe_allow_html=True)
                with st.form(key=f"daily_form_{cid}"):
                    fd1, fd2, fd3 = st.columns(3)
                    with fd1:
                        d_km   = st.number_input("금일 시공 (km)",  value=0.0, step=0.1, min_value=0.0, format="%.2f")
                        d_spot = st.number_input("금일 시공 (개소)", value=0,   step=1,   min_value=0)
                    with fd2:
                        d_plan = st.text_input("당일 작업계획", value="")
                        d_by   = st.text_input("입력자 이름",  value="")
                    with fd3:
                        st.markdown(f"""<div style="font-size:11px;color:#555;padding-top:4px;">
                            <b>현재 누적</b><br>{float(row['done_km']):.1f} km / {int(row['done_spot'])} 개소<br><br>
                            <b>입력 후 예상 누적</b><br>{float(row['done_km']):.1f} + 금일km<br>{int(row['done_spot'])} + 금일개소
                        </div>""", unsafe_allow_html=True)
                    ds, dc = st.columns(2)
                    with ds:
                        d_sub = st.form_submit_button("💾 저장", use_container_width=True)
                    with dc:
                        d_can = st.form_submit_button("✖ 취소", use_container_width=True)
                    if d_sub:
                        if not d_by.strip():
                            st.warning("입력자 이름을 입력해주세요.")
                        elif d_km == 0 and d_spot == 0:
                            st.warning("금일 시공량을 입력해주세요.")
                        else:
                            add_daily_work(int(cid), float(d_km), int(d_spot), d_plan.strip(), d_by.strip())
                            st.session_state[f"daily_{cid}"] = False
                            st.rerun()
                    if d_can:
                        st.session_state[f"daily_{cid}"] = False
                        st.rerun()

        st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

        # ── 공사 정보 / 공정률 수정 ───────────────────────────
        st.markdown("#### ✏️ 공사 정보 / 공정률 수정")
        btn_cols = st.columns(min(len(df), 5))
        for i, (_, row) in enumerate(df.iterrows()):
            cid = row["id"]
            if f"edit_{cid}" not in st.session_state:
                st.session_state[f"edit_{cid}"] = False
            is_open = st.session_state.get(f"edit_{cid}", False)
            with btn_cols[i % 5]:
                lbl = f"🔼 {row['name']}" if is_open else f"✏️ {row['name']}"
                if st.button(lbl, key=f"btn_{cid}", use_container_width=True):
                    new = not is_open
                    for _, r2 in df.iterrows():
                        st.session_state[f"edit_{r2['id']}"]        = False
                        st.session_state[f"daily_{r2['id']}"]       = False
                        st.session_state[f"confirm_del_{r2['id']}"] = False
                    st.session_state[f"edit_{cid}"] = new
                    st.rerun()

        for _, row in df.iterrows():
            cid = row["id"]
            ck  = f"confirm_del_{cid}"
            if st.session_state.get(f"edit_{cid}", False):
                st.markdown(f"""<div class="edit-form-wrap">
                    <strong>✏️ {row['name']} — 공사 정보 및 공정률 수정</strong>
                </div>""", unsafe_allow_html=True)
                with st.form(key=f"form_{cid}"):
                    st.markdown("**📌 공사 기본 정보**")
                    fi1, fi2, fi3 = st.columns(3)
                    with fi1:
                        new_name    = st.text_input("공사명",  value=row["name"])
                        new_manager = st.text_input("담당자",  value=row["manager"])
                    with fi2:
                        new_total_km   = st.number_input("전체물량 (km)",   value=float(row["total_km"]),  step=0.1, min_value=0.0, format="%.1f")
                        new_total_spot = st.number_input("전체물량 (개소)", value=int(row["total_spot"]),   step=1,   min_value=0)
                    with fi3:
                        new_plan_km    = st.number_input("올해계획 (km)",   value=float(row["plan_km"]),   step=0.1, min_value=0.0, format="%.1f")
                        new_plan_spot  = st.number_input("올해계획 (개소)", value=int(row["plan_spot"]),    step=1,   min_value=0)
                    new_period = st.text_input("공사기간", value=row["period"] if row["period"] else "", placeholder="26.5.16~27.12.31")
                    st.markdown("**📊 누적 공정률 직접 수정**")
                    fp1, fp2, fp3 = st.columns(3)
                    with fp1:
                        new_km   = st.number_input("누적 완료 (km)",   value=float(row["done_km"]),  step=0.1, min_value=0.0, format="%.1f")
                        new_spot = st.number_input("누적 완료 (개소)", value=int(row["done_spot"]),   step=1,   min_value=0)
                    with fp2:
                        new_by = st.text_input("수정자 이름", value=row["updated_by"])
                    with fp3:
                        st.markdown(f"""<div style="font-size:11px;color:#555;padding-top:4px;">
                            <b>현재 누적</b><br>{float(row['done_km']):.1f} km / {int(row['done_spot'])} 개소<br>
                            전체: {row['total_rate']:.1f}% / 올해: {row['plan_rate']:.1f}%
                        </div>""", unsafe_allow_html=True)
                    sc, cc, dc = st.columns(3)
                    with sc:
                        submitted = st.form_submit_button("💾 저장", use_container_width=True)
                    with cc:
                        cancelled = st.form_submit_button("✖ 취소", use_container_width=True)
                    with dc:
                        del_clicked = st.form_submit_button("🗑 삭제", use_container_width=True)

                    if submitted:
                        if not new_name.strip():
                            st.warning("공사명을 입력해주세요.")
                        elif not new_manager.strip():
                            st.warning("담당자를 입력해주세요.")
                        elif not new_by.strip():
                            st.warning("수정자 이름을 입력해주세요.")
                        else:
                            update_construction_info(int(cid), new_name.strip(), float(new_total_km),
                                                     int(new_total_spot), float(new_plan_km), int(new_plan_spot),
                                                     new_manager.strip(), new_period.strip())
                            if float(new_km) != float(row["done_km"]) or int(new_spot) != int(row["done_spot"]):
                                update_progress(int(cid), float(new_km), int(new_spot), new_by.strip())
                            st.session_state[f"edit_{cid}"] = False
                            st.rerun()
                    if cancelled:
                        st.session_state[f"edit_{cid}"] = False
                        st.rerun()
                    if del_clicked:
                        st.session_state[f"edit_{cid}"] = False
                        st.session_state[ck] = True
                        st.rerun()

                if st.session_state.get(ck, False):
                    st.markdown(f"""
                    <div style="background:#fff0f0;border-left:3px solid #e74c3c;border-radius:6px;padding:8px 14px;margin:4px 0;">
                        <strong>⚠️ '{row['name']}' 을(를) 정말 삭제할까요?</strong><br>
                        <small style="color:#888;">삭제하면 이력까지 모두 사라지며 복구할 수 없습니다.</small>
                    </div>""", unsafe_allow_html=True)
                    y2, n2, _ = st.columns([2, 2, 8])
                    with y2:
                        if st.button("✅ 삭제", key=f"yes_del2_{cid}", use_container_width=True):
                            delete_construction(int(cid))
                            st.session_state[ck] = False
                            st.rerun()
                    with n2:
                        if st.button("✖ 취소", key=f"no_del2_{cid}", use_container_width=True):
                            st.session_state[ck] = False
                            st.rerun()


# ════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ➕ 공사 추가")
    with st.form(key="add_construction_form", clear_on_submit=True):
        add_name       = st.text_input("공사명")
        a1, a2         = st.columns(2)
        with a1:
            add_total_km   = st.number_input("전체물량 (km)",   min_value=0.0, step=0.1, format="%.1f")
            add_plan_km    = st.number_input("올해계획 (km)",   min_value=0.0, step=0.1, format="%.1f")
        with a2:
            add_total_spot = st.number_input("전체물량 (개소)", min_value=0, step=1)
            add_plan_spot  = st.number_input("올해계획 (개소)", min_value=0, step=1)
        add_manager = st.text_input("담당자")
        add_period  = st.text_input("공사기간 (예: 26.5.16~27.12.31)", placeholder="26.5.16~27.12.31")
        add_sub = st.form_submit_button("✅ 공사 추가")
        if add_sub:
            if not add_name.strip():
                st.warning("공사명을 입력해주세요.")
            elif not add_manager.strip():
                st.warning("담당자를 입력해주세요.")
            elif add_total_km <= 0:
                st.warning("전체물량(km)을 입력해주세요.")
            elif add_plan_km <= 0:
                st.warning("올해계획(km)을 입력해주세요.")
            else:
                add_construction(add_name.strip(), float(add_total_km), int(add_total_spot),
                                 float(add_plan_km), int(add_plan_spot), add_manager.strip(), add_period.strip())
                st.success(f"'{add_name}' 공사가 추가되었습니다.")
                st.rerun()

    st.divider()

    st.markdown("## 🕓 수정 이력 조회")
    if len(df) > 0:
        construction_options = {row["name"]: row["id"] for _, row in df.iterrows()}
        selected_name = st.selectbox("공사 선택", options=list(construction_options.keys()), key="history_select")
        if selected_name:
            history_df = get_progress_history(construction_options[selected_name])
            if len(history_df) == 0:
                st.info("수정 이력이 없습니다.")
            else:
                st.markdown(f"**{selected_name}** 이력 ({len(history_df)}건)")
                hist_html = """<table style="width:100%;border-collapse:collapse;font-size:10px;">
                <thead><tr>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">누적km</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">누적개소</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">금일km</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">금일개소</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">당일계획</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">수정자</th>
                  <th style="background:#1e2a3a;color:#c8d8ea;padding:4px;border:1px solid #2e3d50;">수정일시</th>
                </tr></thead><tbody>"""
                for _, hrow in history_df.iterrows():
                    hist_html += f"""<tr>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['누적km']:.1f}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['누적개소']}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['금일km']:.1f}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['금일개소']}</td>
                      <td style="padding:4px;border:1px solid #ddd;">{hrow['당일계획'] or '-'}</td>
                      <td style="padding:4px;border:1px solid #ddd;text-align:center;">{hrow['수정자'] or '-'}</td>
                      <td style="padding:4px;border:1px solid #ddd;font-size:10px;">{hrow['수정일시']}</td>
                    </tr>"""
                hist_html += "</tbody></table>"
                st.html(hist_html)
    else:
        st.info("등록된 공사가 없습니다.")
