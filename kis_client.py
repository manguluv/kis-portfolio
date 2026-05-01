import os
import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv('APP_KEY')
APP_SECRET = os.getenv('APP_SECRET')
CANO = os.getenv('CANO')
ACNT_PRDT_CD = os.getenv('ACNT_PRDT_CD', '01')
IS_MOCK = os.getenv('IS_MOCK', 'true').lower() == 'true'

# 모의/실전 도메인 및 TR_ID 구분
if IS_MOCK:
    BASE_URL = "https://openapivts.koreainvestment.com:29443"
    DOMESTIC_TR_ID = "VTTC8434R"
    OVERSEAS_TR_ID = "VTRN3018R"
else:
    BASE_URL = "https://openapi.koreainvestment.com:9443"
    DOMESTIC_TR_ID = "TTTC8434R"
    OVERSEAS_TR_ID = "TTTS3012R"

def get_token():
    path = "/oauth2/tokenP"
    url = f"{BASE_URL}{path}"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
    }
    res = requests.post(url, headers=headers, json=body)
    res_json = res.json()
    if "access_token" not in res_json:
        raise RuntimeError(f"토큰 발급 실패: {res_json}")
    return res_json["access_token"]

def _base_headers(token, tr_id):
    return {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
    }

def fetch_domestic(token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    res = requests.get(url, headers=_base_headers(token, DOMESTIC_TR_ID), params=params)
    data = res.json()
    if data.get("rt_cd") != "0":
        raise RuntimeError(f"국내주식 조회 실패: [{data.get('msg_cd')}] {data.get('msg1', '').strip()}")
    return data

def get_exchange_rate(tr_crcy_cd="USD"):
    """yfinance를 이용한 실시간 환율 조회 (USD -> KRW)"""
    try:
        # KRW=X ticker는 Yahoo Finance에서 USD/KRW 환율을 의미
        ticker = yf.Ticker("KRW=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"[경고] yfinance 환율 조회 실패: {e}. 기본 환율 1,350원 적용.")
    return 1350.0

def fetch_overseas(token, ovrs_excg_cd="NASD", tr_crcy_cd="USD"):
    """해외주식 잔고 조회. ovrs_excg_cd: NASD(미국전체)/NYSE/AMEX 등."""
    url = f"{BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "TR_CRCY_CD": tr_crcy_cd,
        "OVRS_ICLD_EXRS_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }
    res = requests.get(url, headers=_base_headers(token, OVERSEAS_TR_ID), params=params)
    data = res.json()
    if data.get("rt_cd") != "0":
        raise RuntimeError(f"해외주식 조회 실패: [{data.get('msg_cd')}] {data.get('msg1', '').strip()}")
    return data

def get_merged_portfolio():
    """국내/해외 계좌 잔고를 병합하여 한화 평가금액 기준으로 반환"""
    token = get_token()
    
    # 1. 국내주식 조회
    d_data = fetch_domestic(token)
    d_stocks_raw = d_data.get("output1", [])
    d_stocks = d_stocks_raw if isinstance(d_stocks_raw, list) else ([d_stocks_raw] if isinstance(d_stocks_raw, dict) else [])
    d_summary = d_data.get("output2", {})
    if isinstance(d_summary, list): d_summary = d_summary[0] if d_summary else {}

    # 2. 해외주식 조회 및 환율 적용 (yfinance 활용)
    exchange_rate = get_exchange_rate("USD")
    o_data = fetch_overseas(token, "NASD", "USD")
    o_stocks_raw = o_data.get("output1", [])
    o_stocks = o_stocks_raw if isinstance(o_stocks_raw, list) else ([o_stocks_raw] if isinstance(o_stocks_raw, dict) else [])
    o_summary = o_data.get("output2", {})
    if isinstance(o_summary, list): o_summary = o_summary[0] if o_summary else {}

    # 3. 데이터 정규화 및 병합
    portfolio = []
    total_eval_krw = 0

    # 국내 주식 추가
    for s in d_stocks:
        qty = int(s.get("hldg_qty", 0))
        if qty > 0:
            price = int(float(s.get("prpr", 0)))
            eval_amt = qty * price
            total_eval_krw += eval_amt
            portfolio.append({
                "type": "국내",
                "name": s.get("prdt_name"),
                "code": s.get("pdno"),
                "qty": qty,
                "price": price,
                "currency": "KRW",
                "eval_amt": eval_amt,
                "profit_loss": int(float(s.get("evlu_pfls_amt", 0)))
            })

    # 해외 주식 추가 (한화 변환) - 시세가 없을 경우 yfinance로 보완
    for s in o_stocks:
        qty = int(s.get("ovrs_cblc_qty", 0))
        if qty > 0:
            code = s.get("ovrs_pdno")
            price_usd = float(s.get("ovrs_now_pric", 0))
            
            # API에서 현재가가 0일 경우 yfinance로 실시간 가격 조회
            if price_usd == 0:
                try:
                    ticker = yf.Ticker(code)
                    price_usd = float(ticker.history(period="1d")['Close'].iloc[-1])
                except Exception:
                    price_usd = 0

            price_krw = int(price_usd * exchange_rate)
            eval_amt = qty * price_krw
            total_eval_krw += eval_amt
            
            # API에서 제공하는 평가손익이 있으면 환율 적용, 없으면 yfinance 기반 단순 계산
            profit_loss_usd = float(s.get("evlu_pfls_amt", 0))
            if profit_loss_usd != 0:
                profit_loss_krw = int(profit_loss_usd * exchange_rate)
            else:
                pchs_avg = float(s.get("pchs_avg_pric", 0))
                profit_loss_krw = int((price_usd - pchs_avg) * qty * exchange_rate)

            portfolio.append({
                "type": "해외(미국)",
                "name": s.get("ovrs_item_name") or code,
                "code": code,
                "qty": qty,
                "price": price_usd,
                "price_krw": price_krw,
                "currency": "USD",
                "eval_amt": eval_amt,
                "profit_loss": profit_loss_krw
            })

    # 4. 요약 정보 구성
    cash_krw = int(float(d_summary.get("prvs_rcdl_excc_amt", 0)))
    
    summary = {
        "cash": cash_krw,
        "stock_eval": total_eval_krw,
        "total_assets": cash_krw + total_eval_krw,
        "exchange_rate_usd": exchange_rate,
        "holdings": portfolio
    }
    
    return summary

if __name__ == "__main__":
    print(f"KIS Developers API 병합 조회 중... (환경: {'모의투자' if IS_MOCK else '실전투자'})")
    try:
        result = get_merged_portfolio()
        
        print(f"\n💱 적용 환율: {result['exchange_rate_usd']:,.2f} 원/USD")
        print(f"💰 주문가능현금: {result['cash']:,} 원")
        print(f"📈 주식 평가금액: {result['stock_eval']:,} 원")
        print(f"💎 총 자산 규모: {result['total_assets']:,} 원")
        
        print(f"\n📋 [보유 종목 상세]")
        print(f"{'구분':<10} | {'종목명':<20} | {'수량':<8} | {'단가':<15} | {'평가금액':<15} | {'손익':<15}")
        print("-" * 100)
        for h in result['holdings']:
            if h['currency'] == 'USD':
                price_str = f"${h['price']:,.2f} ({h['price_krw']:,}원)"
            else:
                price_str = f"{h['price']:,}원"
            print(f"{h['type']:<10} | {h['name']:<20} | {h['qty']:<8} | {price_str:<15} | {h['eval_amt']:<15,} | {h['profit_loss']:<15,}")
            
    except RuntimeError as e:
        print(f"❌ 오류 발생: {e}")
