# 로또 AI 분석 시스템 B — 2단계 모바일 웹

## 스마트폰에서 사용하기
스마트폰에 Python을 설치할 필요가 없습니다. GitHub 저장소에 이 폴더의 파일(`app.py`, `lotto_data.py`, `requirements.txt` 등)을 업로드하고 [Streamlit Community Cloud](https://share.streamlit.io/)에서 GitHub 저장소를 연결한 다음, 메인 파일을 `app.py`로 지정해 배포하세요. 배포 주소를 스마트폰 Chrome 또는 Safari로 열고 **홈 화면에 추가**하면 편리합니다.

- GitHub: https://github.com/
- Streamlit 배포: https://share.streamlit.io/
- Streamlit Cloud 무료 호스팅은 휴면·재시작·재배포 시 로컬 SQLite 데이터가 사라질 수 있습니다. 당첨 데이터와 생성 기록은 필요할 때 CSV로 백업하세요.
- 공개 배포 시 앱 방문자들이 같은 SQLite 파일을 공유할 수 있습니다. 개인 기록의 프라이버시와 영구 저장이 필요하면 로그인 및 외부 데이터베이스를 추가해야 합니다.

## PC에서 로컬 실행
Python 3.10 이상 설치 후:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 기능
- 로또 6/45 번호 생성, 홀짝 조건, 조합 간 중복 최소화, 생성 기록 저장, CSV 다운로드
- 공개된 회차별 동행복권 응답을 통한 점진적 수집(한 번에 최대 30회차)
- CSV 업로드(필수 열 `draw_no,draw_date,n1,n2,n3,n4,n5,n6,bonus`)
- 추첨번호 검증, SQLite 저장, 회차 목록, 번호별 빈도 그래프, CSV 백업

## 수집 유의사항
공식 사이트의 공개 응답 URL은 사전 공지 없이 변경되거나 접근이 제한될 수 있습니다. API가 동작하지 않으면 신뢰할 수 있는 당첨 결과 CSV를 직접 업로드하세요. CSV는 형식과 번호의 유효성을 검사하지만 **출처의 진위까지 자동 확인하지는 못합니다**. CSV를 가져올 때는 출처를 직접 확인하세요. 앱은 발표되지 않은 회차를 만들어내지 않습니다.

현재 수집 방식은 처음부터 30회차씩 누적합니다. 장기간 자동 스케줄 수집, 공식 데이터 전체 일괄 다운로드, 머신러닝, 백테스트는 이후 단계입니다.

## 테스트
```bash
python -m unittest discover -p 'test_*.py'
```

## 확률에 대한 안내
통계와 조건 필터는 공정한 로또 추첨에서 1등 당첨 확률을 높이지 않습니다.
