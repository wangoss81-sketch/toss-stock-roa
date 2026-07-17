# Toss ROA

토스증권 Open API를 이용한 TQQQ 전용 라오어식 무한매수법 자동매매 스타터입니다.

기본 실행은 항상 드라이런입니다. 실제 주문은 `--execute`를 명시해야만 제출됩니다.

## 준비

```bash
cp config.example.json config.json
```

`config.json`에 토스 Open API의 `client_id`, `client_secret`을 넣습니다.
민감정보를 파일에 넣기 싫다면 환경변수 `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`을 사용할 수 있습니다.

텔레그램으로 제어하려면 기존 봇 토큰을 쓰거나 BotFather에서 새 봇을 만듭니다.
토큰은 `telegram.bot_token`에 넣거나 환경변수 `TELEGRAM_BOT_TOKEN`으로 넣을 수 있습니다.
`telegram.allowed_chat_ids`를 비워두면 아무 채팅에서나 명령을 받을 수 있으니, 실제 주문 전에는 본인 chat id만 넣는 것을 권장합니다.

## 설정

- `symbol`: `TQQQ`
- `currency`: `USD`
- `average_down_buy_quantity`: 현재가가 평단가 이하일 때 종가 지정가로 매수할 수량
- `previous_close_buy_quantity`: 현재가가 전날 종가 기준선 이하일 때 종가 지정가로 매수할 수량
- `previous_close_multiplier`: 전날 종가 기준선 배수. 기본값은 `1.15`
- `take_profit_multiplier`: 전량 매도 기준 배수. 기본값은 평단가의 `1.10`
- `min_cash_buffer`: 계좌에 남겨둘 현금

## 실행

계좌 조회:

```bash
./run.sh --config config.json --accounts
```

드라이런:

```bash
./run.sh --config config.json
```

실제 주문:

```bash
./run.sh --config config.json --execute
```

텔레그램 봇 실행:

```bash
./run.sh bot --config config.json
```

VM에서 24시간 서비스로 등록:

```bash
chmod +x scripts/install_systemd.sh
./scripts/install_systemd.sh
```

서비스 로그 확인:

```bash
sudo journalctl -u toss-roa.service -f
```

## 텔레그램 명령

봇은 입력창 아래에 버튼 메뉴를 표시합니다. 버튼을 누르면 해당 명령과 같은 동작을 합니다.

- `상태 조회`: `/status`
- `주문 미리보기`: `/plan`
- `현재 주문`: `/orders`
- `자동 상태`: `/auto`
- `자동 ON`: `/auto_on`
- `자동 OFF`: `/auto_off`
- `실행`: 실제 주문 확인 버튼을 표시

`실행` 버튼은 바로 주문을 제출하지 않습니다. `주문 실행 확인`을 한 번 더 눌러야 실제 주문이 제출됩니다.

- `/status`: 현재가, 전날 종가, 보유 수량, 평단가, 평단 대비 수익률, 목표 매도가, 목표까지 남은 비율, 매수 가능 금액, 진행 중 주문 수
- `/plan`: 오늘 걸 주문 미리보기
- `/orders`: 진행 중인 TQQQ 주문 상세 보기
- `/run`: 실제 주문 제출
- `/auto`: 자동 실행 상태 확인
- `/auto_on`: 설정한 시간에 매일 자동 주문 실행 켜기
- `/auto_off`: 자동 주문 실행 끄기

`telegram.auto.run_at`은 `HH:MM` 형식입니다. 예를 들어 `"18:00"`과 `"Asia/Seoul"`이면 한국시간 매일 18:00에 `/run`과 같은 작업을 한 번 실행합니다.

## 현재 구현된 규칙

1. 진행 중 주문이 있으면 중복 방지를 위해 새 주문을 만들지 않습니다.
2. 보유 수량이 있으면 `평단가 * 1.10` 가격에 TQQQ 전량 지정가 매도 주문을 매일 겁니다.
3. 보유 수량이 있으면 `평단가` 가격에 TQQQ 1주 종가 지정가(`LIMIT` + `CLS`) 매수 주문을 매일 겁니다. 종가가 평단가 이하이면 체결됩니다.
4. `전날 종가 * 1.15` 가격에 TQQQ 1주 종가 지정가(`LIMIT` + `CLS`) 매수 주문을 매일 겁니다. 종가가 해당 가격 이하이면 체결됩니다.
5. 보유 수량이 있으면 하루 주문 계획은 총 3개입니다: 전량 매도 1개, LOC 매수 2개.

실전 사용 전에는 장 시간, 주문 가능 시간, 계좌 현금, 세금과 수수료를 반드시 확인하세요. 이 코드는 자동매매 골격이며 투자 판단을 대신하지 않습니다.
