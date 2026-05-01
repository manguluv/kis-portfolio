import os
import requests
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
    OVERSEAS_TR_ID = "JTTN3018R"

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

def fetch_overseas(token, ovrs_excg_cd="NASD", tr_crcy_cd="USD"):
    """해외주식 잔고 조회. ovrs_excg_cd: NASD/NYSE/AMEX/TKSE/SEHK 등"""
    url = f"{BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "TR_CRCY_CD": tr_crcy_cd,
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }
    res = requests.get(url, headers=_base_headers(token, OVERSEAS_TR_ID), params=params)
    data = res.json()
    if data.get("rt_cd") != "0":
        raise RuntimeError(f"해외주식 조회 실패: [{data.get('msg_cd')}] {data.get('msg1', '').strip()}")
    return data

if __name__ == "__main__":
    print(f"KIS Developers API 연결 중... (환경: {'모의투자' if IS_MOCK else '실전투자'})")

    token = get_token()

    # 국내주식
    print("\n[국내주식] 조회 중...")
    d_data = fetch_domestic(token)
    raw_d1 = d_data.get("output1", [])
    d_stocks = raw_d1 if isinstance(raw_d1, list) else ([raw_d1] if isinstance(raw_d1, dict) else [])
    raw_d2 = d_data.get("output2", {})
    d_summary = raw_d2[0] if isinstance(raw_d2, list) else (raw_d2 if isinstance(raw_d2, dict) else {})

    total_domestic_eval = 0
    for s in d_stocks:
        qty = int(s.get("hldg_qty", 0))
        if qty > 0:
            name = s.get("prdt_name")
            price = int(float(s.get("prpr", 0)))
            total_domestic_eval += qty * price
            print(f"  -> {name}: {qty}주 ({price:,}원)")

    # 해외주식
    print("\n[해외주식] 조회 중...")
    try:
        o_data = fetch_overseas(token)
        raw_o1 = o_data.get("output1", [])
        o_stocks = raw_o1 if isinstance(raw_o1, list) else ([raw_o1] if isinstance(raw_o1, dict) else [])
        for s in o_stocks:
            qty = int(s.get("ovrs_cblc_qty", 0))
            if qty > 0:
                name = s.get("ovrs_pdno")
                print(f"  -> {name}: {qty}주")
        if not o_stocks:
            print("  (보유 해외주식 없음)")
    except RuntimeError as e:
        print(f"  [경고] {e}")

    # 계좌 요약
    print("\n[계좌 요약]")
    cash = d_summary.get("prvs_rcdl_excc_amt", d_summary.get("ord_psbl_cash", "0"))
    try:
        cash_val = int(float(cash))
    except Exception:
        cash_val = 0
    tot_eval = int(float(d_summary.get("tot_evlu_amt", 0)))
    print(f"  -> 주문가능현금:  {cash_val:,}원")
    print(f"  -> 국내 평가금액: {total_domestic_eval:,}원")
    if tot_eval:
        print(f"  -> 계좌 총 평가: {tot_eval:,}원")
