"""Verified draw records, SQLite persistence and official-site import helpers."""
import csv
import io
import json
import sqlite3
import time
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OFFICIAL_URL = 'https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}'
COLUMNS = ['draw_no', 'draw_date', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'bonus']


def create_draw_table(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS lotto_draws (
          draw_no INTEGER PRIMARY KEY, draw_date TEXT NOT NULL,
          n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
          n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
          bonus INTEGER NOT NULL, source TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')


def validate_record(record):
    try:
        draw_no = int(record['draw_no'])
        day = date.fromisoformat(str(record['draw_date']).strip())
        nums = [int(record[f'n{i}']) for i in range(1, 7)]
        bonus = int(record['bonus'])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('회차·날짜·번호 형식이 잘못되었습니다.') from exc
    if draw_no < 1 or day > date.today() or day < date(2002, 12, 7):
        raise ValueError('회차 또는 추첨일이 유효하지 않습니다.')
    if len(set(nums + [bonus])) != 7 or not all(1 <= n <= 45 for n in nums + [bonus]):
        raise ValueError('당첨번호는 1~45 사이의 서로 다른 숫자 7개여야 합니다.')
    return dict(draw_no=draw_no, draw_date=day.isoformat(),
                **{f'n{i}': n for i, n in enumerate(sorted(nums), 1)}, bonus=bonus)


def save_records(db_path, records, source):
    validated = [validate_record(r) for r in records]
    with sqlite3.connect(db_path) as conn:
        conn.executemany('''INSERT INTO lotto_draws
          (draw_no,draw_date,n1,n2,n3,n4,n5,n6,bonus,source)
          VALUES (:draw_no,:draw_date,:n1,:n2,:n3,:n4,:n5,:n6,:bonus,:source)
          ON CONFLICT(draw_no) DO UPDATE SET
          draw_date=excluded.draw_date,n1=excluded.n1,n2=excluded.n2,
          n3=excluded.n3,n4=excluded.n4,n5=excluded.n5,n6=excluded.n6,
          bonus=excluded.bonus,source=excluded.source,updated_at=CURRENT_TIMESTAMP''',
          [{**r, 'source': source} for r in validated])
    return len(validated)


def load_records(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            'SELECT * FROM lotto_draws ORDER BY draw_no DESC')]


def fetch_official_draw(draw_no, timeout=8):
    """Best-effort official endpoint; may be blocked/changed by upstream provider."""
    req = Request(OFFICIAL_URL.format(int(draw_no)), headers={
        'User-Agent': 'Mozilla/5.0 (compatible; LottoDataResearch/1.0)',
        'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise RuntimeError(f'공식 사이트 요청 실패: {exc}') from exc
    if not isinstance(payload, dict):
        raise RuntimeError('예상하지 못한 서버 응답')
    if payload.get('returnValue') == 'fail':
        return None
    if payload.get('returnValue') != 'success':
        raise RuntimeError('지원되지 않는 서버 응답')
    if int(payload.get('drwNo', -1)) != int(draw_no):
        raise ValueError('서버가 요청 회차와 다른 데이터를 반환했습니다.')
    return validate_record({
        'draw_no': payload['drwNo'], 'draw_date': payload['drwNoDate'],
        **{f'n{i}': payload[f'drwtNo{i}'] for i in range(1, 7)},
        'bonus': payload['bnusNo']})


def update_official(db_path, max_requests=30, delay=0.15):
    """Incremental fetch, at most max_requests; no unverified data are saved."""
    records = load_records(db_path)
    known = {r['draw_no'] for r in records}
    next_no = next(n for n in range(1, max(known, default=0)+2) if n not in known)
    added = 0
    for no in range(next_no, next_no + max_requests):
        if no in known:
            continue
        result = fetch_official_draw(no)
        if result is None:
            break
        save_records(db_path, [result], 'official_api')
        added += 1
        if delay and no < next_no + max_requests - 1:
            time.sleep(delay)
    return added


def parse_csv(data):
    if isinstance(data, bytes):
        data = data.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
        raise ValueError('CSV 필수 열: ' + ', '.join(COLUMNS))
    records = [validate_record(r) for r in reader]
    if not records:
        raise ValueError('CSV에 데이터 행이 없습니다.')
    if len({r['draw_no'] for r in records}) != len(records):
        raise ValueError('CSV 내 회차가 중복되었습니다.')
    return records


def frequencies(records, last_n=None):
    selected = records[:last_n] if last_n else records
    counts = {n: 0 for n in range(1, 46)}
    for row in selected:
        for i in range(1, 7):
            counts[int(row[f'n{i}'])] += 1
    return counts
