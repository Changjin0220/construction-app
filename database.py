"""
database.py - SQLite DB 초기화 및 CRUD 함수 모음
공정률 관리 앱의 데이터베이스 계층
"""

import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "construction.db"


def get_connection():
    """DB 연결 반환"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    DB와 테이블이 없으면 생성.
    construction 테이블이 비어있을 경우 샘플 데이터 5개 자동 삽입.
    기존 DB에 컬럼이 없으면 자동으로 추가 (마이그레이션).
    """
    conn = get_connection()
    cur = conn.cursor()

    # 공사 목록 테이블 생성 (period 컬럼 포함)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS construction (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            total_km    REAL NOT NULL,
            total_spot  INTEGER NOT NULL,
            plan_km     REAL NOT NULL,
            plan_spot   INTEGER NOT NULL,
            manager     TEXT NOT NULL,
            period      TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        )
    """)

    # 공정률 기록 테이블 생성
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            construction_id   INTEGER NOT NULL,
            done_km           REAL NOT NULL DEFAULT 0,
            done_spot         INTEGER NOT NULL DEFAULT 0,
            daily_km          REAL NOT NULL DEFAULT 0,
            daily_spot        INTEGER NOT NULL DEFAULT 0,
            daily_plan        TEXT DEFAULT '',
            updated_by        TEXT DEFAULT '',
            updated_at        TEXT NOT NULL,
            FOREIGN KEY (construction_id) REFERENCES construction(id)
        )
    """)

    # 기존 DB 마이그레이션: 없는 컬럼 추가
    cur.execute("PRAGMA table_info(construction)")
    con_cols = [row[1] for row in cur.fetchall()]
    if "period" not in con_cols:
        cur.execute("ALTER TABLE construction ADD COLUMN period TEXT DEFAULT ''")
    if "sort_order" not in con_cols:
        cur.execute("ALTER TABLE construction ADD COLUMN sort_order INTEGER DEFAULT 0")
        # 기존 데이터에 sort_order 초기값 설정
        cur.execute("UPDATE construction SET sort_order = id WHERE sort_order = 0")

    cur.execute("PRAGMA table_info(progress_log)")
    log_cols = [row[1] for row in cur.fetchall()]
    if "daily_km" not in log_cols:
        cur.execute("ALTER TABLE progress_log ADD COLUMN daily_km REAL NOT NULL DEFAULT 0")
    if "daily_spot" not in log_cols:
        cur.execute("ALTER TABLE progress_log ADD COLUMN daily_spot INTEGER NOT NULL DEFAULT 0")

    conn.commit()

    # 샘플 데이터: construction 테이블이 비어있을 때만 삽입
    cur.execute("SELECT COUNT(*) FROM construction")
    if cur.fetchone()[0] == 0:
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
            cur.execute("""
                INSERT INTO construction
                    (name, total_km, total_spot, plan_km, plan_spot, manager, period, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, total_km, total_spot, plan_km, plan_spot, manager, period, i + 1, now))

            construction_id = cur.lastrowid
            done_km, done_spot = sample_progress[i]
            cur.execute("""
                INSERT INTO progress_log
                    (construction_id, done_km, done_spot, daily_km, daily_spot, daily_plan, updated_by, updated_at)
                VALUES (?, ?, ?, 0, 0, '초기 데이터', ?, ?)
            """, (construction_id, done_km, done_spot, manager, now))

        conn.commit()

    conn.close()


def get_all_constructions() -> pd.DataFrame:
    """
    모든 공사 목록과 최신 공정률 기록을 조인하여 DataFrame으로 반환.
    sort_order 기준 오름차순 정렬 (등록 순서 유지).
    """
    conn = get_connection()
    this_month = datetime.now().strftime("%Y-%m")

    query = """
        SELECT
            c.id,
            c.name,
            c.total_km,
            c.total_spot,
            c.plan_km,
            c.plan_spot,
            c.manager,
            c.period,
            c.sort_order,
            COALESCE(p.done_km, 0)     AS done_km,
            COALESCE(p.done_spot, 0)   AS done_spot,
            COALESCE(p.daily_plan, '')  AS daily_plan,
            COALESCE(p.updated_by, '')  AS updated_by,
            COALESCE(p.updated_at, c.created_at) AS updated_at,
            COALESCE(m.month_km, 0)    AS month_km,
            COALESCE(m.month_spot, 0)  AS month_spot
        FROM construction c
        LEFT JOIN (
            SELECT * FROM progress_log
            WHERE id IN (
                SELECT id FROM progress_log p2
                WHERE p2.construction_id = progress_log.construction_id
                ORDER BY updated_at DESC LIMIT 1
            )
        ) p ON c.id = p.construction_id
        LEFT JOIN (
            SELECT construction_id,
                   SUM(daily_km)   AS month_km,
                   SUM(daily_spot) AS month_spot
            FROM progress_log
            WHERE strftime('%Y-%m', updated_at) = ?
            GROUP BY construction_id
        ) m ON c.id = m.construction_id
        ORDER BY c.sort_order ASC, c.id ASC
    """

    df = pd.read_sql_query(query, conn, params=(this_month,))
    conn.close()

    df["total_rate"] = df.apply(
        lambda r: round(r["done_km"] / r["total_km"] * 100, 1) if r["total_km"] > 0 else 0.0, axis=1)
    df["plan_rate"] = df.apply(
        lambda r: round(r["done_km"] / r["plan_km"] * 100, 1) if r["plan_km"] > 0 else 0.0, axis=1)

    return df


def add_construction(name: str, total_km: float, total_spot: int,
                     plan_km: float, plan_spot: int, manager: str, period: str = ""):
    """새 공사 추가. sort_order는 현재 최대값 + 1로 자동 설정."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 현재 최대 sort_order 조회
    cur.execute("SELECT COALESCE(MAX(sort_order), 0) FROM construction")
    max_order = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO construction
            (name, total_km, total_spot, plan_km, plan_spot, manager, period, sort_order, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, total_km, total_spot, plan_km, plan_spot, manager, period, max_order + 1, now))

    construction_id = cur.lastrowid
    cur.execute("""
        INSERT INTO progress_log
            (construction_id, done_km, done_spot, daily_km, daily_spot, daily_plan, updated_by, updated_at)
        VALUES (?, 0, 0, 0, 0, '', ?, ?)
    """, (construction_id, manager, now))

    conn.commit()
    conn.close()


def update_construction_info(construction_id: int, name: str, total_km: float, total_spot: int,
                              plan_km: float, plan_spot: int, manager: str, period: str):
    """
    공사 기본 정보 수정 (공사명, 전체물량, 올해계획, 담당자, 공사기간).
    progress_log는 건드리지 않음.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE construction
        SET name=?, total_km=?, total_spot=?, plan_km=?, plan_spot=?, manager=?, period=?
        WHERE id=?
    """, (name, total_km, total_spot, plan_km, plan_spot, manager, period, construction_id))
    conn.commit()
    conn.close()


def add_daily_work(construction_id: int, daily_km: float, daily_spot: int,
                   daily_plan: str, updated_by: str):
    """
    금일 작업량 입력.
    done_km/done_spot = 기존 누적 + 금일 작업량으로 자동 계산.
    """
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        SELECT done_km, done_spot FROM progress_log
        WHERE construction_id = ?
        ORDER BY updated_at DESC LIMIT 1
    """, (construction_id,))
    row = cur.fetchone()
    prev_km   = row["done_km"]   if row else 0.0
    prev_spot = row["done_spot"] if row else 0

    new_done_km   = prev_km   + daily_km
    new_done_spot = prev_spot + daily_spot

    cur.execute("""
        INSERT INTO progress_log
            (construction_id, done_km, done_spot, daily_km, daily_spot, daily_plan, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (construction_id, new_done_km, new_done_spot, daily_km, daily_spot, daily_plan, updated_by, now))

    conn.commit()
    conn.close()


def update_progress(construction_id: int, done_km: float, done_spot: int,
                    updated_by: str):
    """누적 공정률 직접 수정. daily_km/spot은 0으로 기록."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO progress_log
            (construction_id, done_km, done_spot, daily_km, daily_spot, daily_plan, updated_by, updated_at)
        VALUES (?, ?, ?, 0, 0, '', ?, ?)
    """, (construction_id, done_km, done_spot, updated_by, now))

    conn.commit()
    conn.close()


def delete_construction(construction_id: int):
    """
    공사 삭제 후 나머지 공사의 sort_order를 1부터 재정렬.
    삭제된 공사 아래에 있던 공사들이 한 칸씩 당겨짐.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 공정률 기록 먼저 삭제
    cur.execute("DELETE FROM progress_log WHERE construction_id = ?", (construction_id,))
    # 공사 삭제
    cur.execute("DELETE FROM construction WHERE id = ?", (construction_id,))

    # 남은 공사 sort_order 재정렬 (1, 2, 3 ... 순으로)
    cur.execute("SELECT id FROM construction ORDER BY sort_order ASC, id ASC")
    remaining = cur.fetchall()
    for new_order, r in enumerate(remaining, start=1):
        cur.execute("UPDATE construction SET sort_order = ? WHERE id = ?", (new_order, r[0]))

    conn.commit()
    conn.close()


def get_progress_history(construction_id: int) -> pd.DataFrame:
    """특정 공사의 progress_log 전체를 최신순으로 반환."""
    conn = get_connection()
    query = """
        SELECT
            done_km    AS "누적km",
            done_spot  AS "누적개소",
            daily_km   AS "금일km",
            daily_spot AS "금일개소",
            daily_plan AS "당일계획",
            updated_by AS "수정자",
            updated_at AS "수정일시"
        FROM progress_log
        WHERE construction_id = ?
        ORDER BY updated_at DESC
    """
    df = pd.read_sql_query(query, conn, params=(construction_id,))
    conn.close()
    return df
