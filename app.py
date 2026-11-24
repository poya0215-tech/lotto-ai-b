"""Lotto 6/45 analysis MVP: random ticket generation and SQLite history."""
import itertools
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from lotto_data import create_draw_table, load_records, update_official, parse_csv, save_records, frequencies
import streamlit as st

DB_PATH = Path(__file__).with_name("lotto.db")
RNG = secrets.SystemRandom()


def initialize_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS generated_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            method TEXT NOT NULL,
            numbers TEXT NOT NULL
        )""")


def generate_tickets(count: int, odd_target: int | None, minimize_overlap: bool):
    """Sample unique 6/45 tickets; optionally greedily minimize pairwise overlap."""
    tickets = []
    seen = set()
    for _ in range(count):
        candidates = []
        # More candidates improve diversity but do not improve draw odds.
        for _ in range(300 if minimize_overlap else 1):
            ticket = tuple(sorted(RNG.sample(range(1, 46), 6)))
            if ticket in seen or (odd_target is not None and sum(n % 2 for n in ticket) != odd_target):
                continue
            candidates.append(ticket)
        # Rejection sampling for constrained odd/even targets.
        while not candidates:
            ticket = tuple(sorted(RNG.sample(range(1, 46), 6)))
            if ticket not in seen and (odd_target is None or sum(n % 2 for n in ticket) == odd_target):
                candidates.append(ticket)
        if minimize_overlap and tickets:
            ticket = min(candidates, key=lambda t: (max(len(set(t) & set(old)) for old in tickets), sum(len(set(t) & set(old)) for old in tickets)))
        else:
            ticket = candidates[0]
        tickets.append(ticket)
        seen.add(ticket)
    return tickets


def save_tickets(tickets, method):
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    batch_id = f"{created_at}-{secrets.token_hex(4)}"
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO generated_tickets(batch_id, created_at, method, numbers) VALUES (?, ?, ?, ?)",
            [(batch_id, created_at, method, ",".join(map(str, ticket))) for ticket in tickets],
        )
    return batch_id


def load_history():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT created_at, batch_id, method, numbers FROM generated_tickets ORDER BY id DESC LIMIT 500", conn
        )


def main():
    st.set_page_config(page_title="로또 AI 분석 시스템 B", page_icon="🎱", layout="wide")
    initialize_database()
    create_draw_table(DB_PATH)
    st.title("🎱 로또 AI 분석 시스템 B")
    st.caption("2단계 · 모바일 웹 · 조합 생성 · 실제 당첨 데이터 수집 및 통계")
    st.warning("이 프로그램은 당첨을 예측하지 않습니다. 모든 6/45 조합의 1등 확률은 동일합니다.")

    tab1, tab2, tab3 = st.tabs(["🎟️ 번호 생성", "📋 생성 기록", "📊 당첨 데이터"])
    with tab1:
        count = st.slider("생성할 게임 수", min_value=1, max_value=20, value=5)
        odd_label = st.selectbox("홀수 개수", ["제한 없음", "2개", "3개", "4개"], index=0)
        odd_target = None if odd_label == "제한 없음" else int(odd_label[0])
        minimize_overlap = st.checkbox("게임 간 번호 겹침 최소화", value=True)
        st.caption("홀짝 조건과 겹침 최소화는 조합의 형태만 바꾸며, 1등 당첨 확률을 높이지 않습니다.")
        if st.button("번호 생성 및 저장", type="primary"):
            tickets = generate_tickets(count, odd_target, minimize_overlap)
            method = f"uniform;odd={odd_target};diversity={minimize_overlap}"
            batch_id = save_tickets(tickets, method)
            st.session_state["tickets"] = tickets
            st.session_state["batch_id"] = batch_id
        if "tickets" in st.session_state:
            tickets = st.session_state["tickets"]
            frame = pd.DataFrame(tickets, columns=[f"번호 {i}" for i in range(1, 7)])
            frame.index = range(1, len(frame) + 1)
            frame.index.name = "게임"
            st.dataframe(frame, use_container_width=True)
            st.download_button("CSV 다운로드", frame.to_csv(index=True).encode("utf-8-sig"), file_name="lotto_tickets.csv", mime="text/csv")
            st.info(f"저장된 배치: {st.session_state['batch_id']}")
    with tab3:
        st.subheader("역대 당첨 데이터")
        st.caption("공식 동행복권 사이트의 공개 회차별 응답을 사용합니다. 사이트 정책 변경이나 접속 제한 시 CSV 업로드를 이용하세요.")
        records = load_records(DB_PATH)
        st.metric("저장된 추첨 회차", len(records))
        st.caption("첫 수집은 최대 30회차씩 진행됩니다. 버튼을 반복해서 눌러 이어서 수집하세요.")
        if st.button("공식 사이트에서 다음 30회차 가져오기"):
            try:
                added = update_official(DB_PATH, max_requests=30)
                st.success(f"검증 후 {added}개 회차를 저장했습니다.")
                if added == 0:
                    st.info("새 회차가 없거나, 다음 회차가 아직 발표되지 않았습니다.")
                records = load_records(DB_PATH)
            except Exception as exc:
                st.error(f"수집에 실패했습니다: {exc}")
                st.info("네트워크 차단이나 공식 사이트 변경 가능성이 있습니다. CSV 가져오기를 이용하세요.")
        with st.expander("CSV 파일에서 당첨번호 가져오기"):
            st.caption("열 이름: draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus")
            uploaded = st.file_uploader("CSV 선택", type=['csv'])
            if uploaded is not None and st.button("CSV 검증 후 저장"):
                try:
                    incoming = parse_csv(uploaded.getvalue())
                    saved = save_records(DB_PATH, incoming, 'csv_import')
                    st.success(f"검증 완료: {saved}개 회차를 저장했습니다.")
                    records = load_records(DB_PATH)
                except Exception as exc:
                    st.error(f"CSV 오류: {exc}")
        if records:
            st.dataframe(pd.DataFrame(records)[['draw_no','draw_date','n1','n2','n3','n4','n5','n6','bonus','source']],
                         hide_index=True, use_container_width=True)
            st.download_button("당첨 데이터 CSV 백업", pd.DataFrame(records).to_csv(index=False).encode('utf-8-sig'),
                               file_name='lotto_draws_backup.csv', mime='text/csv')
            window = st.selectbox("분석 범위", ["전체", "최근 10회", "최근 30회", "최근 50회", "최근 100회"])
            limit = None if window == "전체" else int(window.split()[1].replace('회', ''))
            freq = frequencies(records, limit)
            st.subheader("번호별 출현 빈도 (보너스 제외)")
            st.bar_chart(pd.DataFrame({'번호': list(freq), '출현 횟수': list(freq.values())}).set_index('번호'))
            st.caption("출현 빈도는 과거 통계이며, 미래 당첨 확률의 우위를 의미하지 않습니다.")
        else:
            st.info("아직 저장된 당첨 데이터가 없습니다. 공식 사이트 수집 또는 CSV 업로드를 시작하세요.")
    with tab2:
        history = load_history()
        st.metric("최근 저장 기록", f"{len(history)}게임")
        st.dataframe(history, use_container_width=True, hide_index=True)
        if not history.empty:
            st.download_button("기록 CSV 다운로드", history.to_csv(index=False).encode("utf-8-sig"), file_name="lotto_history.csv", mime="text/csv")


if __name__ == "__main__":
    main()
