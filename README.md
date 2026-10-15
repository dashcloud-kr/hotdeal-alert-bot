# hotdeal-alert-bot — 24/7 핫딜 알림 텔레그램 봇

[![CI](https://github.com/dashcloud-kr/hotdeal-alert-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/dashcloud-kr/hotdeal-alert-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

뽐뿌 핫딜 게시판을 **5분마다** 확인해서 **내 키워드에 맞는 핫딜만** 실시간(또는 1시간 다이제스트)으로 알려주는 텔레그램 봇입니다.
[대시클라우드(DashCloud)](https://dashcloud.kr)에서 **평생 무료로 24시간** 가동할 수 있습니다.

> **English** — A Telegram bot that watches Korean hot-deal boards (Ppomppu RSS) and notifies you only about deals matching your keywords and price range — in real time or as an hourly digest. Built to run 24/7 on [DashCloud](https://dashcloud.kr) for free.

## 기능

| 기능 | 설명 |
| --- | --- |
| 키워드 필터 | 포함 키워드 최대 20개 (예: `아이패드`, `노트북`). 없으면 전체 수신 |
| 제외 키워드 | 최대 10개 (예: `중고`, `리퍼`) — 제목에 있으면 알림 제외 |
| 가격 필터 | `/price 1만-5만` — 제목에서 자동 파싱한 가격 기준 |
| 실시간/다이제스트 | 실시간 즉시 알림 또는 1시간마다 모아서 한 번에 |
| 중복 방지 | 게시글 번호 기준 — 같은 글은 절대 두 번 오지 않음 |
| 과거 글 폭탄 방지 | 봇 시작 시 기존 글은 알림 없이 등록만 |
| 출처 확장 | 소스 모듈 구조 (`app/services/sources.py`) — 게시판 추가 쉬움 |

## 명령어

```
/add 아이패드 에어팟    알림 키워드 추가
/ban 중고 리퍼          제외 키워드
/keywords /del 아이패드  목록/삭제

/mode realtime          실시간 알림 (기본)
/mode digest            1시간마다 모아서 알림
/price 1만-5만           가격 범위 (5만-, -3만, off 가능)

/latest                 최신 핫딜 5건 미리보기
/settings               내 설정 요약
/status /id             봇 상태 / 내 chat id
```

## 동작 방식

- **5분 폴링**: 뽐뿌 핫딜 게시판 RSS를 5분마다 수집, 새 글만 처리 (게시글 번호 dedup)
- **가격 파싱**: 제목의 `(39,180원/무료)` 같은 패턴에서 자동 추출 — 실측 15/15건 파싱
- **다이제스트**: 1시간마다 큐에 쌓인 핫딜을 한 메시지로 (4096자 초과 시 자동 분할)
- 상태는 SQLite(WAL)에 영구 저장 — 재시작·재배포해도 키워드/설정/중복 기록 유지

## 30초 로컬 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 에 TELEGRAM_BOT_TOKEN 입력 — @BotFather 에서 발급

python bot.py
```

## DashCloud로 24시간 무료 가동

1. [dashcloud.kr](https://dashcloud.kr) 가입 — 휴대폰 인증 1회, 결제 정보 불필요
2. 이 폴더를 대시보드에 **드래그 앤 드롭**
3. 환경변수에 `TELEGRAM_BOT_TOKEN` 등록
4. 배포 — `dashcloud.json`이 런타임(Python 3.12)과 진입점을 자동 설정합니다

> 노트북을 덮어도 봇이 계속 돌아갑니다. Free 플랜은 평생 무료이며 갱신·슬립이 없습니다.

## 구조

```
hotdeal-alert-bot/
├── bot.py                     # 엔트리포인트 (마이그레이션·잡 등록)
├── app/
│   ├── clients/rss.py         # RSS HTTP 클라이언트
│   ├── services/
│   │   ├── rss.py             # RSS 파싱 + HotdealItem (guid·가격·날짜)
│   │   ├── sources.py         # 수집 소스 정의 (뽐뿌)
│   │   ├── matching.py        # 키워드·가격 필터 (순수 함수)
│   │   └── repository.py      # SQLite CRUD (아이템·키워드·설정·큐)
│   ├── handlers/hotdeal.py    # 명령어 + 폴링/다이제스트 잡
│   └── utils/                 # 가격 파싱·메시지 포맷
└── tests/                     # 88개 (RSS 파싱·매칭·CRUD·잡 통합)
```

## 테스트

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q
```

## 주의

- 뽐뿌 핫딜 게시판 RSS 기준이며, 게시판 사정에 따라 피드가 변경될 수 있습니다
- 알림은 정보 제공용이며 구매 판단의 책임은 사용자에게 있습니다

## 라이선스

[MIT](LICENSE) — 자유롭게 복사·수정·배포하세요.
