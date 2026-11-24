"""Lotto 6/45 analysis MVP: random ticket generation and SQLite history."""
import itertools
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from lotto_data import create_draw_table, load_records, update_official, parse_csv, save_records, frequencies
try:
    import streamlit as st
except ModuleNotFoundError:
    st = None
from pro_stats import analyze, tests

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
    st.set_page_config(page_title="로또 AI 분석 시스템 B", page_icon="🎱", layout="centered")
    initialize_database()
    create_draw_table(DB_PATH)
    st.title("로또 AI System B PRO v3.0")
    st.caption("3단계 · 모바일 웹 · 정밀 통계 및 검정")
    st.warning("이 프로그램은 당첨을 예측하지 않습니다. 모든 6/45 조합의 1등 확률은 동일합니다.")

    tab1, tab2, tab3, tab4 = st.tabs(["번호 생성", "기록", "데이터", "정밀 통계"])
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
    with tab4:
        rows = load_records(DB_PATH)
        if not rows:
            st.info("먼저 당첨 데이터를 가져오세요.")
        else:
            r = analyze(rows)
            missing = sorted(set(range(1, max(r['ids'])+1))-set(r['ids']))
            st.write(f"저장 {len(rows)}회 · 마지막 저장 회차 {max(r['ids'])} · 내부 누락 {len(missing)}회")
            if missing:
                st.warning(f"누락 회차 예시: {missing[:30]}. 간격과 최근 통계는 관측 자료 기준입니다.")
            st.caption("최신 실제 회차와 원본의 정확성은 공식 사이트에서 별도 확인하세요. 최근 N회는 저장된 N개 관측입니다.")
            section = st.selectbox("분석 항목", ["전체 빈도","단기 빈도","중장기 빈도","평균 출현 간격","미출현 기간","동시 출현","상관관계","홀짝","고저","합계","끝자리","연속번호","직전 회차 중복","무작위성 검정","독립성 검정"])
            if section in ("전체 빈도","단기 빈도","중장기 빈도"):
                cols = {"전체 빈도":["전체"],"단기 빈도":["최근 5회","최근 10회","최근 20회"],"중장기 빈도":["최근 50회","최근 100회","최근 200회"]}[section]
                st.bar_chart(r['freq'][cols])
                st.dataframe(r['freq'][cols])
            elif section in ("평균 출현 간격","미출현 기간"):
                st.dataframe(r['gaps']); st.caption("미관측 번호는 결측값입니다. 누락 회차가 있으면 실제 간격과 다를 수 있습니다.")
            elif section == "동시 출현":
                st.write("번호쌍"); st.dataframe(r['pairs'].head(50),hide_index=True)
                st.write("세 번호"); st.dataframe(r['triples'].head(50),hide_index=True)
            elif section == "상관관계":
                import altair as alt
                matrix=r['corr'].rename_axis('번호 A').reset_index().melt(id_vars='번호 A',var_name='번호 B',value_name='상관계수').dropna()
                st.altair_chart(alt.Chart(matrix).mark_rect().encode(x=alt.X('번호 A:O',axis=alt.Axis(labels=False)),y=alt.Y('번호 B:O',axis=alt.Axis(labels=False)),color=alt.Color('상관계수:Q',scale=alt.Scale(domain=[-1,1],scheme='redblue')),tooltip=['번호 A','번호 B','상관계수']).properties(height=350),use_container_width=True)
                st.caption("비복원 추출 자체가 번호 사이 음의 상관을 유발합니다. 결측 상관은 표시하지 않습니다.")
            elif section in ("무작위성 검정","독립성 검정"):
                st.caption("999회 몬테카를로 검정. 독립성 검정은 인접 회차 겹침 분포만 검사하며 모든 의존성을 검출하지는 않습니다. 두 검정의 보수적 기준은 각각 0.025입니다.")
                if len(rows)<30: st.warning("표본이 적습니다. 최소 30회 관측 후 검정하세요.")
                elif st.button("검정 실행"):
                    with st.spinner("계산 중"):
                        st.write(tests(r))
                    st.info("작은 p값은 추가 조사 신호이지 미래 예측력의 증거가 아닙니다.")
            else:
                key={"홀짝":"odd","고저":"low","합계":"total","끝자리":"ending","연속번호":"consecutive","직전 회차 중복":"overlap"}[section]
                st.bar_chart(r[key].rename("횟수")); st.dataframe(r[key].rename("횟수"))
                st.caption("홀짝은 홀수 개수, 고저는 1~22 개수, 연속번호는 인접 번호쌍 개수입니다. 직전 중복은 실제 연속 회차만 포함합니다.")
    with tab2:
        history = load_history()
        st.metric("최근 저장 기록", f"{len(history)}게임")
        st.dataframe(history, use_container_width=True, hide_index=True)
        if not history.empty:
            st.download_button("기록 CSV 다운로드", history.to_csv(index=False).encode("utf-8-sig"), file_name="lotto_history.csv", mime="text/csv")


if __name__ == "__main__":
    main()
