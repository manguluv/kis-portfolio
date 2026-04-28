import os
import requests
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv('APP_KEY')
APP_SECRET = os.getenv('APP_SECRET')
CANO = os.getenv('CANO')
ACNT_PRDT_CD = os.getenv('ACNT_PRDT_CD', '01')
IS_MOCK = os.getenv('IS_MOCK', 'true').lower() == 'true'

# 모의투자/실전투자 도메인 구분
BASE_URL = "https://openapivts.koreainvestment.com:29443" if IS_MOCK else "https://openapi.koreainvestment.com:9443"

def get_access_token():
    """Access Token 발급"""
    url = f"{BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    res = requests.post(url, headers=headers, json=body)
    return res.json().get("access_token")

def get_balance():
    """계좌 잔고 및 보유 종목 조회"""
    token = get_access_token()
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    
    headers = {
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "TTTC8434R"
    }
    
    # 국내주식 계좌잔고 조회 API 파라미터
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "AFHR_FLPR_YN": "N",      # 시간외단가단위여부
        "UND_FLTR_YN": "N",       # 미포함종목여부 (N: 전체)
        "INQR_DVSN": "00",        # 조회구분 (00: 전체)
        "UNPR_DVSN": "01",        # 단가구분
        "FUND_STTL_ICLD_YN": "F", # 펀드결제분포함여부
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",        # 처리구분 (00: 전량)
        "CTX_AREA_K1": "",        # 연속조회검색조건
        "CTX_AREA_K2": ""         # 연속조회키
    }
    
    res = requests.get(url, headers=headers, params=params)
    data = res.json()
    
    # 응답 구조: output1 (종목별 정보), output2 (요약 정보)
    stocks = data.get("output1", [])
    summary = data.get("output2", {})
    
    return stocks, summary

if __name__ == "__main__":
    try:
        my_stocks, my_summary = get_balance()
        
        # 1. 보유 종목 상세 내역
        print("\n========== 📊 보유 종목 현황 ==========")
        total_eval = 0
        for stock in my_stocks:
            name = stock.get('prdt_name', 'N/A')
            qty = int(stock.get('bldg_qty', 0))
            avg_price = int(float(stock.get('pchs_avg_pric', 0)))
            curr_price = int(float(stock.get('prpr', 0))) # 현재가
            eval_amt = qty * curr_price
            total_eval += eval_amt
            
            print(f"[{name}]")
            print(f"  ↳ 수량: {qty:,}주 | 평균가: {avg_price:,}원 | 현재가: {curr_price:,}원")
            print(f"  ↳ 평가금액: {eval_amt:,}원 | 평가손익: {eval_amt - (qty * avg_price):,}원")
        
        # 2. 현금 및 총자산 요약
        print("\n========== 💰 계좌 요약 ==========")
        print(f"💵 주문가능현금: {int(my_summary.get('ord_psbl_cash', 0)):,}원")
        print(f"📈 총평가금액: {total_eval:,}원")
        print(f"🏦 총자산(eval+cash): {total_eval + int(my_summary.get('ord_psbl_cash', 0)):,}원")
        print("=====================================")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 .env 파일의 APP_KEY, APP_SECRET, 계좌번호를 확인해주세요.")
