import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ─────────────────────────────────────────────
# 1. 지역 DB (법정동코드 + fallback 평당가 만원/평)
# ─────────────────────────────────────────────
REGION_DB = {
    # 서울
    "강남구":        ("11680", 12000), "서초구":        ("11650", 11000),
    "송파구":        ("11710", 8500),  "용산구":        ("11170", 9000),
    "성동구":        ("11200", 7500),  "마포구":        ("11440", 6500),
    "강동구":        ("11740", 6000),  "영등포구":      ("11560", 5500),
    "동작구":        ("11590", 5200),  "광진구":        ("11215", 5000),
    "양천구":        ("11470", 4800),  "서대문구":      ("11410", 4500),
    "은평구":        ("11380", 4000),  "노원구":        ("11350", 3800),
    "도봉구":        ("11320", 3500),  "강북구":        ("11305", 3300),
    "성북구":        ("11290", 4200),  "중랑구":        ("11260", 3600),
    "동대문구":      ("11230", 4000),  "중구":          ("11140", 5500),
    "종로구":        ("11110", 5000),  "강서구":        ("11500", 4500),
    "구로구":        ("11530", 3800),  "금천구":        ("11545", 3500),
    "관악구":        ("11620", 4000),
    # 경기 남부
    "성남시 분당구": ("41135", 5500),  "성남시 수정구": ("41131", 3000),
    "성남시 중원구": ("41133", 3200),  "과천시":        ("41150", 7000),
    "수원시 영통구": ("41117", 3500),  "수원시 장안구": ("41111", 2800),
    "수원시 권선구": ("41113", 2700),  "수원시 팔달구": ("41115", 2600),
    "용인시 수지구": ("41465", 3800),  "용인시 기흥구": ("41463", 3200),
    "용인시 처인구": ("41461", 2200),  "화성시":        ("41590", 3000),
    "평택시":        ("41220", 2000),  "안양시 동안구": ("41173", 3200),
    "안양시 만안구": ("41171", 2700),  "의왕시":        ("41430", 3000),
    "군포시":        ("41410", 2800),
    # 인천
    "인천 연수구":   ("28185", 3200),  "인천 서구":     ("28260", 2400),
    "인천 남동구":   ("28200", 2300),  "인천 부평구":   ("28237", 2200),
    "인천 계양구":   ("28245", 2000),  "인천 미추홀구": ("28177", 2100),
    "인천 동구":     ("28140", 1800),  "인천 중구":     ("28110", 1900),
    # 안산·시흥
    "안산시 단원구": ("41273", 2000),  "안산시 상록구": ("41271", 1900),
    "시흥시":        ("41390", 2000),
}

REGION_NAMES = list(REGION_DB.keys())
M2_TO_PYEONG = 3.3058
API_TRADE = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
API_RENT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
KAKAO_KEY = "d764a0c64ce8fe827fe0cc0feab5ea6c"

# ─────────────────────────────────────────────
# 2. 국토교통부 실거래가 API
# ─────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_apt_trade(service_key, lawd_cd, deal_ymd):
    url = API_TRADE
    params = {"ServiceKey": service_key, "LAWD_CD": lawd_cd,
              "DEAL_YMD": deal_ymd, "numOfRows": 1000, "pageNo": 1}
    try:
        resp = requests.get(url, params=params, timeout=10)
        root = ET.fromstring(resp.content)
        if not root.findtext(".//resultCode", "").startswith("00"):
            return []
        items = []
        for item in root.findall(".//item"):
            try:
                price = int(item.findtext("dealAmount", "0").replace(",", "").strip())
                area  = float(item.findtext("excluUseAr", "0").strip())
                if price > 0 and area > 10:
                    items.append({
                        "price_man": price,
                        "area_m2":   area,
                        "year":      int(item.findtext("buildYear", "0").strip() or 0),
                        "name":      item.findtext("aptNm", "").strip(),
                        "dong":      item.findtext("umdNm", "").strip(),
                    })
            except Exception:
                continue
        return items
    except Exception:
        return []


@st.cache_data(ttl=3600)  # 임시로 캐시 비활성화
def fetch_apt_rent(service_key, lawd_cd, deal_ymd):
    url = API_RENT
    params = {"ServiceKey": service_key, "LAWD_CD": lawd_cd,
              "DEAL_YMD": deal_ymd, "numOfRows": 1000, "pageNo": 1}
    try:
        resp = requests.get(url, params=params, timeout=10)
        root = ET.fromstring(resp.content)
        if not root.findtext(".//resultCode", "").startswith("00"):
            return []
        items = []
        for item in root.findall(".//item"):
            try:
                deposit = int(item.findtext("deposit", "0").replace(",", "").strip())
                monthly = int(item.findtext("monthlyRent", "0").replace(",", "").strip())
                area    = float(item.findtext("excluUseAr", "0").strip())
                if monthly == 0 and deposit > 0 and area > 0:
                    items.append({"deposit_man": deposit, "area_m2": area, "name":        item.findtext("aptNm", "").strip(),})
            except Exception as e:
                continue
        if len(items) == 0 and root.findall('.//item'):
            sample = root.findall('.//item')[0]
        return items
    except Exception as e:
        return []


def recent_months(n=3):
    now = datetime.now()
    return [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(1, n+1)]


def calc_region_price_api(service_key, lawd_cd, dong_filter=""):
    all_items = []
    for ym in recent_months(3):
        all_items.extend(fetch_apt_trade(service_key, lawd_cd, ym))
    
    # 동 필터 적용
    if dong_filter:
        all_items = [i for i in all_items if dong_filter in i.get("dong", "")]
    
    if len(all_items) < 5:
        return None, len(all_items)
    prices = [i["price_man"] / (i["area_m2"] / M2_TO_PYEONG) for i in all_items]
    return round(sum(prices) / len(prices), 0), len(all_items)


def calc_jeonse_rate_api(service_key, lawd_cd, area_m2):
    trades, rents = [], []
    for ym in recent_months(3):
        trades.extend(fetch_apt_trade(service_key, lawd_cd, ym))
        rents.extend(fetch_apt_rent(service_key, lawd_cd, ym))
    tol = area_m2 * 0.2
    t = [i for i in trades if abs(i["area_m2"] - area_m2) <= tol]
    r = [i for i in rents  if abs(i["area_m2"] - area_m2) <= tol]
    if not t or not r:
        return None
    return round(sum(i["deposit_man"] for i in r) / len(r) /
                 (sum(i["price_man"] for i in t) / len(t)) * 100, 1)

def get_apt_list(service_key, lawd_cd, dong):
    """해당 동의 거래 단지 목록 반환"""
    all_items = []
    for ym in recent_months(3):
        all_items.extend(fetch_apt_trade(service_key, lawd_cd, ym))
    if dong:
        all_items = [i for i in all_items if dong in i.get("dong", "")]
    # 단지명 중복 제거
    names = sorted(set(i["name"] for i in all_items if i["name"]))
    return names, all_items


def get_pyeong_list(all_items, apt_name):
    """선택한 단지의 거래 평형 목록 반환"""
    items = [i for i in all_items if i["name"] == apt_name]
    pyeongs = sorted(set(round(i["area_m2"] / M2_TO_PYEONG) for i in items))
    return pyeongs, items


def get_apt_info(all_trade_items, all_rent_items, apt_name, pyeong):
    # 매매 실거래가
    trade = [i for i in all_trade_items
             if i["name"] == apt_name
             and abs(i["area_m2"] / M2_TO_PYEONG - pyeong) <= 2]
    # 전세가
    rent = [i for i in all_rent_items
            if i.get("name") == apt_name
            and abs(i["area_m2"] / M2_TO_PYEONG - pyeong) <= 2]

    avg_price  = round(sum(i["price_man"] for i in trade) / len(trade) / 10000, 2) if trade else None
    avg_jeonse = round(sum(i["deposit_man"] for i in rent) / len(rent) / 10000, 2) if rent else None
    years = [i["year"] for i in trade if i["year"] > 0]
    year  = max(years) if years else None

    return avg_price, avg_jeonse, year, len(trade)

# ─────────────────────────────────────────────
# 3. 계산 함수
# ─────────────────────────────────────────────

def calc_loc_weight(sw, ja):
    t = {"도보 5분 이내": 1.15, "도보 10분 이내": 1.05, "도보 15분 이상": 1.0}
    j = {"30분 이내": 1.1, "1시간 이내": 1.05, "1시간 초과": 1.0}
    return min(round(t.get(sw, 1.0) * j.get(ja, 1.0), 4), 1.2)

def calc_age_factor(yb, recon):
    age = 2025 - yb
    if age <= 5:    return 1.2
    if recon:       return 1.15
    return max(round(1.0 - age * 0.01, 4), 0.75)

def calc_premium_rate(units, brand, gtx):
    r  = 0.10 if units >= 2000 else (0.05 if units >= 1000 else 0.0)
    r += 0.05 if brand else 0.0
    r += {"착공 중": 0.15, "계획 발표": 0.05, "없음": 0.0}.get(gtx, 0.0)
    return r

def calc_V(rp, ap, lw, af, pr):
    return round(rp * ap * lw * af + rp * ap * pr, 0)

def calc_gap(V, A):
    return round((V - A) / A * 100, 2)

def valuation_label(g):
    return "📈 확실한 저평가" if g >= 10 else ("➡️ 적정 가치" if g > -10 else "📉 고평가 국면")

def momentum(jr, ss, mt):
    sj = max(0.0, min(40.0, round(40 * (jr - 45) / 25, 1)))
    ss_ = {"부족 (80% 미만)": 30, "적정 (80~120%)": 15, "과잉 (120% 초과)": 0}.get(ss, 15)
    st_ = {"상승 (매물↓, 거래↑)": 30, "보합": 15, "하락 (매물↑, 거래↓)": 0}.get(mt, 15)
    return {"전세가율": sj, "공급물량": ss_, "거래추이": st_, "합계": sj + ss_ + st_}

def momentum_grade(s):
    return "상 🟢" if s >= 70 else ("중 🟡" if s >= 40 else "하 🔴")

def acq_tax(price, own):
    p = price * 10000
    if own == "1주택(=무주택)":
        r = 0.01 if p < 6 else (0.02 if p < 9 else 0.03)
    elif own == "2주택 (조정지역)": r = 0.08
    else: r = 0.12
    return round(price * r, 4)

def brokerage(p):
    return round(p * (0.005 if p < 2 else (0.004 if p < 9 else 0.009)), 4)

def required_cash(price, jeonse, own, invest_type, cash_input, loan_input, regulated):
    tax  = acq_tax(price, own)
    brok = brokerage(price)
    if invest_type == "갭투자 (전세 임대)":
        gap  = round(price - jeonse, 4)
        cash = round(gap + tax + brok, 4)
        mode = "갭투자"
        l    = 0
    else:
        l    = loan_input
        cash = round(price - l + tax + brok, 4)
        mode = "실거주 (대출 활용)"
    return {"mode": mode, "취득세": tax, "복비": brok, "대출액": l, "필요현금": cash}

def grade(gap_pct, mom):
    if gap_pct >= 15 and mom >= 70: return "⭐ S등급 — 강력 매수"
    if gap_pct >= 5  and mom >= 40: return "🅰️ A등급 — 매수 고려"
    return "🅱️ B등급 — 관망/보유"

def signal(gap_pct, ag):
    if ag is None: return ""
    if gap_pct > 0 and ag <= 0:  return "🚨 급매 포착! 즉시 임장 권장"
    if gap_pct > 0 and ag >= 10: return "⚠️ 추격 매수 주의 — 집주인 호가 상승 중"
    return ""

@st.cache_data(ttl=86400)  # 24시간 캐시
def get_station_distance(apt_name, dong, region_name):
    """카카오맵 API로 아파트 → 가장 가까운 지하철역 거리 계산"""
    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    
    # 1. 아파트 좌표 검색
    search_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    import re
    apt_name_clean = re.sub(r'[^\w\s]', '', apt_name)  # 특수문자 제거
    resp = requests.get(search_url, headers=headers,
                    params={"query": f"{region_name} {dong} {apt_name_clean}", "size": 1})
    result = resp.json()
    if not result.get("documents"):
        resp = requests.get(search_url, headers=headers,
                            params={"query": f"{region_name} {dong}", "size": 1})
        result = resp.json()
    if not result.get("documents"):
        return None, None
    
    x = result["documents"][0]["x"]  # 경도
    y = result["documents"][0]["y"]  # 위도
    
    # 2. 주변 지하철역 검색
    station_resp = requests.get(search_url, headers=headers,
                                params={"query": "지하철역", "x": x, "y": y,
                                        "radius": 2000, "size": 1,
                                        "category_group_code": "SW8"})
    stations = station_resp.json()
    if not stations["documents"]:
        return None, None
    
    nearest = stations["documents"][0]
    distance_m = int(nearest["distance"])
    station_name = nearest["place_name"]
    
    return station_name, distance_m


def distance_to_walk(meters):
    """거리 → 도보 시간 변환 (분속 67m 기준)"""
    minutes = round(meters / 67)
    if minutes <= 5:   return "도보 5분 이내"
    elif minutes <= 10: return "도보 10분 이내"
    else:              return "도보 15분 이상"

@st.cache_data(ttl=86400)
def fetch_price_trend(service_key, lawd_cd, apt_name, area_py):
    """5년치 6개월 간격 가격 추이 — 거래 없으면 인접 월 자동 탐색"""
    current_year = datetime.now().year
    trend = {}
    search_windows = {
        "01": ["01", "02", "03"],  # 상반기: 1→2→3월
        "07": ["07", "08", "09"],  # 하반기: 7→8→9월
    }
    for year in range(current_year - 4, current_year + 1):
        for base_month, months in search_windows.items():
            for month in months:
                ym = f"{year}{month}"
                items = fetch_apt_trade(service_key, lawd_cd, ym)
                same = [i for i in items
                        if i["name"] == apt_name
                        and abs(i["area_m2"] / M2_TO_PYEONG - area_py) <= 2]
                if same:
                    avg = round(sum(i["price_man"] for i in same) / len(same) / 10000, 2)
                    label = f"{year}.{base_month}"
                    trend[label] = avg
                    break  # 데이터 찾으면 다음 반기로
    return trend

# ─────────────────────────────────────────────
# 4. UI
# ─────────────────────────────────────────────
st.set_page_config(page_title="부동산 내재가치 평가기", page_icon="🏠", layout="wide")
st.title("🏠 부동산 내재가치 평가 프로그램")
st.caption("서울·경기·인천 | 국토교통부 실거래가 API 연동")

with st.expander("🔑 API 설정 (국토교통부 실거래가 자동 조회)", expanded=False):
    ac1, ac2 = st.columns([3, 1])
    with ac1:
        svc_key = st.secrets["MOLIT_KEY"]
    with ac2:
        use_api = True

tab1, tab2 = st.tabs(["📊 단지 분석", "ℹ️ 계산 로직"])

with tab1:
    L, R = st.columns([1, 1], gap="large")

    with L:
        avg_price, avg_jeonse = None, None
        sw_auto = "도보 15분 이상"
        st.subheader("① 단지 검색")
        region = st.selectbox("지역 (구 단위)", REGION_NAMES)

        # 동 목록 자동 로드
        dong_names = []
        all_region_items = []
        all_rent_items = []
        if svc_key:
            with st.spinner("동 목록 불러오는 중..."):
                for ym in recent_months(3):
                    all_region_items.extend(fetch_apt_trade(svc_key, REGION_DB[region][0], ym))
                    all_rent_items.extend(fetch_apt_rent(svc_key, REGION_DB[region][0], ym))
            dong_names = sorted(set(i["dong"] for i in all_region_items if i["dong"]))

        if dong_names:
            dong_input = st.selectbox("법정동 선택", dong_names)
        else:
            dong_input = st.text_input("법정동 직접 입력", placeholder="예: 역삼동")

        # 단지 목록 필터링
        if dong_input and all_region_items:
            apt_names_filtered = sorted(set(
                i["name"] for i in all_region_items
                if i["dong"] == dong_input and i["name"]
            ))
        else:
            apt_names_filtered = []
            if svc_key and dong_input:
                apt_names_filtered, all_region_items = get_apt_list(svc_key, REGION_DB[region][0], dong_input)

        # 단지 목록 자동 로드
        apt_names, all_trade_items = [], []
        if svc_key and dong_input:
            with st.spinner("단지 목록 불러오는 중..."):
                apt_names, all_trade_items = get_apt_list(svc_key, REGION_DB[region][0], dong_input)

        if apt_names:
            apt_name = st.selectbox("아파트 선택", apt_names)
            
            # 평형 목록 자동 로드
            pyeong_list, apt_items = get_pyeong_list(all_trade_items, apt_name)
            if pyeong_list:
                pyeong_label = st.selectbox("평형 선택", [f"{p}평" for p in pyeong_list])
                area_py = int(pyeong_label.replace("평", ""))
                
                # 단지 정보 자동 추출
                avg_price, avg_jeonse, yr_auto, trade_cnt = get_apt_info(all_trade_items, all_rent_items, apt_name, area_py)
                
                # 역세권 자동 계산 (yr_auto 여부 무관하게 항상 실행)
                station_name, dist_m = get_station_distance(apt_name, dong_input, region)
                if dist_m is not None:
                    sw_auto = distance_to_walk(dist_m)
                    st.caption(f"🚇 가장 가까운 역: {station_name} ({dist_m}m, 도보 약 {round(dist_m/67)}분)")
                else:
                    sw_auto = "도보 15분 이상"

                if yr_auto:
                    yr_built = yr_auto
                    st.caption(f"📋 자동 추출 — 준공: {yr_built}년 / 실거래가: {avg_price}억 / 전세가: {avg_jeonse}억 ({trade_cnt}건)")
                else:
                    yr_built = st.number_input("준공연도 (자동추출 실패)", 1970, 2025, 2000)
            else:
                area_py = st.number_input("평형 직접 입력", 10.0, 100.0, 33.0, 0.5)
                yr_built = st.number_input("준공연도", 1970, 2025, 2000)
        else:
            if dong_input:
                st.warning("해당 동 최근 3개월 거래 데이터 없음 — 직접 입력")
            apt_name = st.text_input("아파트명 직접 입력")
            area_py  = st.number_input("평형", 10.0, 100.0, 33.0, 0.5)
            yr_built = st.number_input("준공연도", 1970, 2025, 2000)
        st.caption("직접 입력")
        units = st.number_input("세대수", 100, 10000, 500, 50)
        st.subheader("② 가격 데이터")
        st.caption("자동 연동")
        actual_eok = st.number_input("최근 실거래가 (억원)", 0.0, 200.0,
                                    float(avg_price) if avg_price else 0.0, 0.5)
        jeonse_eok = st.number_input("전세가 (억원)", 0.5, 150.0,
                                    float(avg_jeonse) if avg_jeonse else 6.0, 0.5)

        st.caption("직접 입력")
        price_eok  = st.number_input("현재 매매가 (억원)", 1.0, 200.0, 10.0, 0.5)
        asking_eok = st.number_input("현재 최저 호가 (억원, 0=미입력)", 0.0, 200.0, 0.0, 0.5)

        st.subheader("③ 입지 조건")

        st.caption("자동 연동")
        sw = st.selectbox("역세권 (도보 거리)", ["도보 5분 이내", "도보 10분 이내", "도보 15분 이상"],
                        index=["도보 5분 이내", "도보 10분 이내", "도보 15분 이상"].index(sw_auto))

        st.caption("직접 입력")
        ja    = st.selectbox("주요 업무지구 접근성", ["30분 이내", "1시간 이내", "1시간 초과"])
        brand = st.checkbox("1군 브랜드 (삼성·현대·GS·DL·대우·포스코·롯데·HDC·SK·호반)")
        gtx   = st.selectbox("GTX 호재", ["없음", "계획 발표", "착공 중"])
        recon = st.checkbox("재건축 대상 (25년↑ + 용적률 200% 미만 + 서울/1기신도시)")

        st.subheader("④ 모멘텀 지표")
        st.caption("직접 입력")
        jr_manual = round(jeonse_eok / price_eok * 100, 1)
        supply    = st.selectbox("향후 2년 공급 물량", ["부족 (80% 미만)", "적정 (80~120%)", "과잉 (120% 초과)"])
        trend     = st.selectbox("최근 거래/매물 추이", ["상승 (매물↓, 거래↑)", "보합", "하락 (매물↑, 거래↓)"])

        st.subheader("⑤ 투자자 정보")
        invest_type = st.selectbox("투자 방식", ["실거주", "갭투자 (전세 임대)"])
        own         = st.selectbox("보유 주택 수", ["1주택(=무주택)", "2주택 (조정지역)", "3주택↑ / 법인"])
        regulated   = st.checkbox("규제지역 (강남3구·용산)",
                                   value=any(k in region for k in ["강남구","서초구","송파구","용산구"]))
        cash_input  = st.number_input("보유 현금 (억원)", 0.0, 200.0, 3.0, 0.5)

        if invest_type == "실거주":
            loan_input    = st.number_input("대출 가능액 (억원)", 0.0, 200.0, 7.0, 0.5)
            interest_rate = st.number_input("대출 금리 (%)", 1.0, 10.0, 4.0, 0.1)
            budget        = round(cash_input + loan_input, 2)
            max_gap       = 999
        else:
            loan_input    = 0.0
            interest_rate = 0.0
            budget        = cash_input
            max_gap       = cash_input

        st.caption(f"총 가용 자금: {budget}억")

        run = st.button("🔍 분석 시작", use_container_width=True, type="primary")

    with R:
        if run:
            lawd_cd, fallback = REGION_DB[region]
            area_m2 = area_py * M2_TO_PYEONG

            # API 호출
            api_price, api_cnt, jr_api = None, 0, None
            if use_api and svc_key:
                with st.spinner("🔄 국토교통부 실거래가 조회 중..."):
                    api_price, api_cnt = calc_region_price_api(svc_key, lawd_cd, dong_input)
                    jr_api = calc_jeonse_rate_api(svc_key, lawd_cd, area_m2)

            # 평당가 결정
            if api_price and api_cnt >= 5:
                rp     = api_price
                rp_src = f"✅ API 실거래 {api_cnt}건 평균 (최근 3개월)"
            else:
                rp     = fallback
                why    = "API 키 미입력" if not svc_key else f"건수 부족({api_cnt}건)"
                rp_src = f"⚠️ 하드코딩 기준값 ({why})"

            # 전세가율 결정
            jr     = jr_api if jr_api else jr_manual
            jr_src = f"✅ API 실거래 {jr:.1f}%" if jr_api else f"수동 입력 {jr}%"

            # 계산
            lw   = calc_loc_weight(sw, ja)
            af   = calc_age_factor(yr_built, recon)
            pr   = calc_premium_rate(units, brand, gtx)
            V    = calc_V(rp, area_py, lw, af, pr)
            A    = price_eok * 10000
            gp   = calc_gap(V, A)
            mom  = momentum(jr, supply, trend)
            ci = required_cash(price_eok, jeonse_eok, own, invest_type, cash_input, loan_input, regulated)
            b_ok = ci["필요현금"] <= budget and (price_eok - jeonse_eok) <= max_gap
            ag   = round((asking_eok - actual_eok) / actual_eok * 100, 2) if actual_eok > 0 else None
            sig  = signal(gp, ag)
            V_eok = round(V / 10000, 2)

            # 출처
            st.info(f"📊 **평당가:** {rp_src}\n\n🏠 **전세가율:** {jr_src}")

            # 등급
            st.subheader("📋 분석 결과")
            st.markdown(f"### {grade(gp, mom['합계'])}")
            if sig: st.warning(sig)

            # 가치 요약
            st.markdown("---")
            st.markdown("#### 💰 가치 평가 요약")
            c1, c2, c3 = st.columns(3)
            c1.metric("현재 시세", f"{price_eok}억")
            c2.metric("내재 가치(V)", f"{V_eok}억", delta=f"{gp:+.1f}%",
                      delta_color="normal" if gp >= 0 else "inverse")
            c3.metric("판단", valuation_label(gp))

            # 계산 내역
            st.markdown("---")
            with st.expander("🔢 계산 세부 내역"):
                st.markdown(f"""
| 항목 | 값 |
|---|---|
| 지역 평당가 (Region_Price) | **{rp:,.0f}** 만원/평 |
| 출처 | {rp_src} |
| 평형 | {area_py} 평 |
| 입지 가중치 (Loc_Weight) | {lw} |
| 연식 팩터 (Age_Factor) | {af} |
| 가산율 (Premium Rate) | {pr*100:.0f}% |
| 프리미엄 | {round(rp * area_py * pr / 10000, 2)}억 |
| **내재 가치(V)** | **{V_eok}억** |
| **저평가율** | **{gp:+.2f}%** |
                """)

            # 모멘텀
            st.markdown("---")
            st.markdown("#### 📈 상승 모멘텀")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("전세가율", f"{mom['전세가율']:.1f}/40")
            m2.metric("공급물량", f"{mom['공급물량']}/30")
            m3.metric("거래추이", f"{mom['거래추이']}/30")
            m4.metric("총점", f"{mom['합계']:.1f}/100", delta=momentum_grade(mom['합계']))

            # 예산
            st.markdown("---")
            st.markdown("#### 💼 투자 예산")
            b1, b2, b3 = st.columns(3)
            b1.metric("필요 현금", f"{ci['필요현금']:.2f}억", help=ci['mode'])
            b2.metric("취득세",   f"{ci['취득세']:.3f}억")
            b3.metric("복비",     f"{ci['복비']:.3f}억")
            if ci["대출액"] > 0:
                monthly_interest = round(ci["대출액"] * (interest_rate / 100) / 12, 4)
                st.info(f"예상 대출: {ci['대출액']:.2f}억 | 월 이자: {monthly_interest:.3f}억 ({monthly_interest*10000:.0f}만원)")
            if b_ok: st.success(f"✅ 예산 적합 — 가용 {budget}억 내 진입 가능")
            else:    st.error(f"❌ 예산 초과 — 필요 {ci['필요현금']:.2f}억 > 가용 {budget}억")

            # 호가
            if ag is not None:
                st.markdown("---")
                st.markdown("#### 🏷️ 호가 분석")
                h1, h2 = st.columns(2)
                h1.metric("호가 괴리율", f"{ag:+.2f}%")
                h2.metric("판정", "🔥 급매" if ag <= 0 else ("⚠️ 호가 상승" if ag >= 10 else "정상"))

            # Action Plan
            st.markdown("---")
            st.markdown("#### 🎯 Action Plan")
            pros, cons = [], []
            if lw >= 1.1:           pros.append(f"역세권·직주근접 우수 (Loc={lw})")
            if jr >= 65:            pros.append(f"전세가율 {jr}% — 하방 경직성 강함")
            if recon:               pros.append("재건축 기대 가치 반영")
            if supply.startswith("부족"): pros.append("인근 공급 부족")
            if gp < 0:              cons.append(f"시세 대비 {abs(gp):.1f}% 고평가")
            if supply.startswith("과잉"): cons.append("인근 공급 과잉")
            if jr < 50:             cons.append(f"전세가율 {jr}% — 하방 취약")
            if not b_ok:            cons.append(f"예산 부족 ({ci['필요현금']-budget:.2f}억 초과)")
            age_now = 2025 - yr_built
            if 15 <= age_now <= 24: cons.append(f"준공 {age_now}년차 — 감가 구간")

            if pros:
                st.markdown("**✅ 강점 (PROS)**")
                for p in pros: st.markdown(f"- {p}")
            if cons:
                st.markdown("**❌ 약점 (CONS)**")
                for c in cons: st.markdown(f"- {c}")

            if b_ok and gp >= 5:  st.success("👉 예산 내 진입 가능, 매수 검토 권장")
            elif not b_ok:        st.warning("👉 예산 조정 필요")
            else:                 st.info("👉 적정 가치 수준, 급매 출현 시 매수 검토")
            # 가격 추이 차트
            if svc_key and apt_name:
                with st.spinner("가격 추이 조회 중..."):
                    trend_data = fetch_price_trend(svc_key, lawd_cd, apt_name, area_py)
                if len(trend_data) >= 2:
                    st.markdown("---")
                    st.markdown("#### 📈 5년 가격 추이 (6개월 간격)")
                    import pandas as pd
                    import plotly.graph_objects as go

                    df = pd.DataFrame(list(trend_data.items()), columns=["시점", "평균가(억)"])
                    df = df.sort_values("시점").reset_index(drop=True)

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df["시점"],
                        y=df["평균가(억)"],
                        mode="lines+markers+text",
                        text=[f"{v}억" for v in df["평균가(억)"]],
                        textposition="top center",
                        textfont=dict(size=14, color="#111"),
                        line=dict(color="#2563EB", width=2.5),
                        marker=dict(size=8, color="#2563EB"),
                        fill="tozeroy",
                        fillcolor="rgba(37, 99, 235, 0.08)"
                    ))
                    fig.update_layout(
                        xaxis_title="",
                        yaxis_title="거래가 (억원)",
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        yaxis=dict(
                            gridcolor="#f0f0f0",
                            tickfont=dict(size=13, color="#111"),
                            range=[0, max(df["평균가(억)"]) * 1.2]  # 상단 20% 여백
                        ),
                        xaxis=dict(
                            gridcolor="#f0f0f0",
                            tickfont=dict(size=13, color="#111"),
                            tickangle=-45,
                            type="category",  # ← 추가: 문자열 카테고리로 처리
                            range=[-0.5, len(df) - 0.3],  # ← 양 끝 여백
                        ),
                        margin=dict(l=10, r=40, t=40, b=60),
                        height=320,
                        font=dict(color="#111", size=13),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"거래 기준: {apt_name} {area_py}평 / 데이터 {len(trend_data)}개 구간")
                else:
                    st.markdown("---")
                    st.caption("가격 추이 데이터 부족 (해당 단지 거래 없음)")
        else:
            st.info("왼쪽 항목 입력 후 '분석 시작'을 눌러주세요.")

with tab2:
    st.markdown("""
### 내재 가치 공식
```
V = (Region_Price × 평형 × Loc_Weight × Age_Factor) + Premium
Premium = Region_Price × 평형 × 가산율 합계
```

### API 연동 항목
| 항목 | API |
|---|---|
| 지역 평균 평당가 | 국토부 아파트 매매 실거래 (최근 3개월) |
| 전세가율 | 국토부 아파트 전월세 실거래 (유사 평형 비교) |

### 저평가율 판단
| 구간 | 판단 |
|---|---|
| +10% 이상 | 확실한 저평가 |
| -10%~+10% | 적정 가치 |
| -10% 이하 | 고평가 |

### ⚠️ 참고용 보조 도구입니다. 투자 전 임장·공인중개사·세무사 확인 필수.
    """)
