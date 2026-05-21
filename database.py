"""
database.py - Google Sheets 기반 CRUD 함수 모음
SQLite 대신 Google Sheets를 DB로 사용 (Streamlit Cloud 영구 저장)
"""

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import streamlit as st

# Google Sheets API 스코프
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Google Sheets ID
SHEET_ID = "1AGkk92hE3A_FNtLZvEcPa7aGTrBgUVBKk-wVALJBNcY"

# 시트 이름
SHEET_CONSTRUCTION = "construction"
SHEET_PROGRESS     = "progress_log"


def get_client():
    """Streamlit secrets에서 인증 정보를 읽어 gspread 클라이언트 반환"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


@st.cache_resource(ttl=60)
def get_sheets():
    """construction, progress_log 두 시트 반환 (60초 캐싱)"""
    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    # 시트가 없으면 자동 생성
    existing = [ws.title for ws in spreadsheet.worksheets()]

    if SHEET_CONSTRUCTION not in existing:
        ws = spreadsheet.add_worksheet(title=SHEET_CONSTRUCTION, rows=1000, cols=20)
        # 헤더 설정
        ws.append_row(["id", "name", "total_km", "total_spot", "plan_km", "plan_spot",
                        "manager", "period", "sort_order", "created_at"])

    if SHEET_PROGRESS not in existing:
        ws = spreadsheet.add_worksheet(title=SHEET_PROGRESS, rows=10000, cols=20)
        ws.append_row(["id", "construction_id", "done_km", "done_spot",
                        "daily_km", "daily_spot", "daily_plan", "updated_by", "updated_at"])

    con_sheet  = spreadsheet.worksheet(SHEET_CONSTRUCTION)
    prog_sheet = spreadsheet.worksheet(SHEET_PROGRESS)
    return con_sheet, prog_sheet


def _next_id(sheet) -> int:
    """해당 시트의 다음 auto-increment ID 반환"""
    records = sheet.get_all_records()
    if not records:
        return 1
    return max(int(r["id"]) for r in records) + 1


def init_db():
    """
    시트가 없으면 생성하고, construction 시트가 비어있으면 샘플 데이터 5개 삽입.
    """
    con_sheet, prog_sheet = get_sheets()

    records = con_sheet.get_all_records()
    if len(records) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sample_constructions = [
            ("A구역 공사", 12.4, 8,  5.2, 3, "김철수", "26.01.01~27.12.31"),
            ("B구역 공사",  8.1, 5,  3.0, 2, "이영희", "26.03.01~27.06.30"),
            ("C구역 공사", 15.0, 12, 6.5, 5, "박민준", "26.02.01~28.02.28"),
            ("D구역 공사",  6.8, 4,  4.0, 2, "최수진", "26.04.01~27.03.31"),
            ("E구역 공사", 20.0, 15, 8.0, 6, "정태영", "26.05.01~28.12.31"),
        ]
        sample_progress = [(4.8, 2), (2.3, 1), (9.2, 7), (5.8, 3), (5.0, 3)]

        for i, (name, total_km, total_spot, plan_km, plan_spot, manager, period) in enumerate(sample_constructions):
            cid = i + 1
            con_sheet.append_row([cid, name, total_km, total_spot, plan_km, plan_spot,
                                   manager, period, cid, now])
            done_km, done_spot = sample_progress[i]
            pid = i + 1
            prog_sheet.append_row([pid, cid, done_km, done_spot, 0, 0, "초기 데이터", manager, now])


@st.cache_data(ttl=30)
def get_all_constructions() -> pd.DataFrame:
    """
    모든 공사 + 최신 공정률 + 이달 시공량을 계산해 DataFrame 반환.
    sort_order 기준 오름차순. (30초 캐싱)
    """
    con_sheet, prog_sheet = get_sheets()

    con_records  = con_sheet.get_all_records()
    prog_records = prog_sheet.get_all_records()

    if not con_records:
        return pd.DataFrame(columns=["id","name","total_km","total_spot","plan_km","plan_spot",
                                      "manager","period","sort_order","done_km","done_spot",
                                      "daily_plan","updated_by","updated_at",
                                      "month_km","month_spot","total_rate","plan_rate"])

    df_con  = pd.DataFrame(con_records)
    df_prog = pd.DataFrame(prog_records) if prog_records else pd.DataFrame()

    # 이번 달 YYYY-MM
    this_month = datetime.now().strftime("%Y-%m")

    results = []
    for _, row in df_con.iterrows():
        cid = int(row["id"])

        # 해당 공사의 progress_log
        if not df_prog.empty:
            prog = df_prog[df_prog["construction_id"].astype(int) == cid].copy()
        else:
            prog = pd.DataFrame()

        # 최신 레코드 (누적값)
        if not prog.empty:
            prog_sorted = prog.sort_values("updated_at", ascending=False)
            latest      = prog_sorted.iloc[0]
            done_km     = float(latest["done_km"])
            done_spot   = int(latest["done_spot"])
            daily_plan  = str(latest["daily_plan"])
            updated_by  = str(latest["updated_by"])
            updated_at  = str(latest["updated_at"])
        else:
            done_km = done_spot = 0
            daily_plan = updated_by = updated_at = ""

        # 이달 시공량 합산
        if not prog.empty:
            this_month_prog = prog[prog["updated_at"].astype(str).str.startswith(this_month)]
            month_km   = float(this_month_prog["daily_km"].astype(float).sum())
            month_spot = int(this_month_prog["daily_spot"].astype(int).sum())
        else:
            month_km = month_spot = 0

        total_km   = float(row["total_km"])
        plan_km    = float(row["plan_km"])
        total_rate = round(done_km / total_km * 100, 1) if total_km > 0 else 0.0
        plan_rate  = round(done_km / plan_km  * 100, 1) if plan_km  > 0 else 0.0

        results.append({
            "id":         cid,
            "name":       str(row["name"]),
            "total_km":   total_km,
            "total_spot": int(row["total_spot"]),
            "plan_km":    plan_km,
            "plan_spot":  int(row["plan_spot"]),
            "manager":    str(row["manager"]),
            "period":     str(row["period"]),
            "sort_order": int(row["sort_order"]) if row["sort_order"] != "" else cid,
            "done_km":    done_km,
            "done_spot":  done_spot,
            "daily_plan": daily_plan,
            "updated_by": updated_by,
            "updated_at": updated_at,
            "month_km":   month_km,
            "month_spot": month_spot,
            "total_rate": total_rate,
            "plan_rate":  plan_rate,
        })

    df = pd.DataFrame(results)
    df = df.sort_values("sort_order", ascending=True).reset_index(drop=True)
    return df


def add_construction(name, total_km, total_spot, plan_km, plan_spot, manager, period=""):
    """새 공사 추가"""
    con_sheet, prog_sheet = get_sheets()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cid       = _next_id(con_sheet)
    records   = con_sheet.get_all_records()
    max_order = max((int(r["sort_order"]) for r in records), default=0)

    con_sheet.append_row([cid, name, total_km, total_spot, plan_km, plan_spot,
                           manager, period, max_order + 1, now])

    pid = _next_id(prog_sheet)
    prog_sheet.append_row([pid, cid, 0, 0, 0, 0, "", manager, now])


def update_construction_info(construction_id, name, total_km, total_spot,
                              plan_km, plan_spot, manager, period):
    """공사 기본 정보 수정"""
    con_sheet, _ = get_sheets()
    records = con_sheet.get_all_records()

    for i, r in enumerate(records):
        if int(r["id"]) == construction_id:
            row_num = i + 2  # 헤더 포함, 1-indexed
            con_sheet.update(f"B{row_num}:I{row_num}",
                             [[name, total_km, total_spot, plan_km, plan_spot, manager, period,
                               r["sort_order"]]])
            break


def add_daily_work(construction_id, daily_km, daily_spot, daily_plan, updated_by):
    """금일 작업량 입력 → 누적값 자동 계산"""
    con_sheet, prog_sheet = get_sheets()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 현재 누적값 조회
    records = prog_sheet.get_all_records()
    prog    = [r for r in records if int(r["construction_id"]) == construction_id]

    if prog:
        prog_sorted = sorted(prog, key=lambda x: x["updated_at"], reverse=True)
        prev_km   = float(prog_sorted[0]["done_km"])
        prev_spot = int(prog_sorted[0]["done_spot"])
    else:
        prev_km = prev_spot = 0

    new_done_km   = prev_km   + daily_km
    new_done_spot = prev_spot + daily_spot

    pid = _next_id(prog_sheet)
    prog_sheet.append_row([pid, construction_id, new_done_km, new_done_spot,
                            daily_km, daily_spot, daily_plan, updated_by, now])


def update_progress(construction_id, done_km, done_spot, updated_by):
    """누적 공정률 직접 수정"""
    _, prog_sheet = get_sheets()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pid = _next_id(prog_sheet)
    prog_sheet.append_row([pid, construction_id, done_km, done_spot,
                            0, 0, "", updated_by, now])


def delete_construction(construction_id):
    """공사 삭제 후 sort_order 재정렬"""
    con_sheet, prog_sheet = get_sheets()

    # construction 삭제
    con_records = con_sheet.get_all_records()
    for i, r in enumerate(con_records):
        if int(r["id"]) == construction_id:
            con_sheet.delete_rows(i + 2)
            break

    # progress_log 삭제 (해당 공사 전체, 뒤에서부터)
    prog_records = prog_sheet.get_all_records()
    rows_to_delete = [i + 2 for i, r in enumerate(prog_records)
                      if int(r["construction_id"]) == construction_id]
    for row_num in sorted(rows_to_delete, reverse=True):
        prog_sheet.delete_rows(row_num)

    # sort_order 재정렬
    con_records = con_sheet.get_all_records()
    for new_order, r in enumerate(con_records, start=1):
        row_num = con_records.index(r) + 2
        con_sheet.update_cell(row_num, 9, new_order)  # sort_order는 9번째 컬럼


def get_progress_history(construction_id) -> pd.DataFrame:
    """특정 공사의 progress_log 전체 최신순 반환"""
    _, prog_sheet = get_sheets()
    records = prog_sheet.get_all_records()

    prog = [r for r in records if int(r["construction_id"]) == construction_id]
    if not prog:
        return pd.DataFrame(columns=["누적km","누적개소","금일km","금일개소","당일계획","수정자","수정일시"])

    df = pd.DataFrame(prog)
    df = df.sort_values("updated_at", ascending=False)
    df = df.rename(columns={
        "done_km":    "누적km",
        "done_spot":  "누적개소",
        "daily_km":   "금일km",
        "daily_spot": "금일개소",
        "daily_plan": "당일계획",
        "updated_by": "수정자",
        "updated_at": "수정일시",
    })
    return df[["누적km","누적개소","금일km","금일개소","당일계획","수정자","수정일시"]]
