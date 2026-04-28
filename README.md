# KIS Portfolio Manager

한국투자증권 Open API(KIS Developers)를 활용한 국내 주식 잔고 조회 및 포트폴리오 관리 도구입니다.

## 기능
- 보유 종목별 수량, 평균 단가, 현재가, 평가금액 조회
- 계좌별 주문 가능 현금 및 총 자산 요약
- 포트폴리오 자동화 기반 데이터 추출

## 설정
1. `.env.example`을 복사하여 `.env` 파일을 생성합니다.
2. 한국투자증권 개발자 포털에서 발급받은 키와 계좌 정보를 입력합니다.
3. `IS_MOCK` 값을 환경에 맞게 설정합니다 (true: 모의투자, false: 실전투자).

## 실행
```bash
pip install -r requirements.txt
python kis_client.py
```
