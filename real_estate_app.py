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
    for months in [3, 6, 12]:  # 순차적으로 확장
        all_items = []
        for ym in recent_months(months):
            all_items.extend(fetch_apt_trade(service_key, lawd_cd, ym))
        if dong_filter:
            all_items = [i for i in all_items if dong_filter in i.get("dong", "")]
        if len(all_items) >= 5:
            prices = [i["price_man"] / (i["area_m2"] / M2_TO_PYEONG) for i in all_items]
            return round(sum(prices) / len(prices), 0), len(all_items)
    return None, 0


def calc_jeonse_rate_api(service_key, lawd_cd, area_m2):
    tol = area_m2 * 0.2
    for months in [3, 6, 12]:
        trades, rents = [], []
        for ym in recent_months(months):
            trades.extend(fetch_apt_trade(service_key, lawd_cd, ym))
            rents.extend(fetch_apt_rent(service_key, lawd_cd, ym))
        t = [i for i in trades if abs(i["area_m2"] - area_m2) <= tol]
        r = [i for i in rents  if abs(i["area_m2"] - area_m2) <= tol]
        if t and r:
            return round(sum(i["deposit_man"] for i in r) / len(r) /
                         (sum(i["price_man"] for i in t) / len(t)) * 100, 1)
    return None

def get_apt_list(service_key, lawd_cd, dong):
    """해당 동의 거래 단지 목록 반환"""
    all_items = []
    for ym in recent_months(12):
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

def calc_V(rp, ap, lw, af, pr, jf):
    base = rp * ap * lw * af * jf
    premium = rp * ap * pr
    return round(base + premium, 0)

def calc_jeonse_factor(jr):
    if jr >= 70:   return 1.05
    elif jr >= 55: return 1.00
    else:          return 0.95

def calc_loan(loan, rate, years, loan_type):
    r = rate / 100 / 12
    n = years * 12
    if loan_type == "일시상환":
        monthly = round(loan * r, 4)
        total   = round(monthly * n, 2)
    elif loan_type == "원리금균등상환":
        monthly = round(loan * r * (1+r)**n / ((1+r)**n - 1), 4)
        total   = round(monthly * n - loan, 2)
    else:  # 원금균등상환
        monthly = round(loan / n + loan * r, 4)
        total   = round(loan * r * (n+1) / 2, 2)
    return {"월납입금": monthly, "총이자": total}

def calc_gap(V, A):
    return round((V - A) / A * 100, 2)

def valuation_label(g):
    return "📈 확실한 저평가" if g >= 10 else ("➡️ 적정 가치" if g > -10 else "📉 고평가 국면")

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

def grade(gap_pct):
    if gap_pct >= 15: return "⭐ S등급 — 강력 매수"
    if gap_pct >= 5:  return "🅰️ A등급 — 매수 고려"
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
                for ym in recent_months(12):
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
                pyeong_label = st.selectbox("평형 선택(전용평수)", [f"{p}평" for p in pyeong_list])
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
                st.warning("해당 동 최근 1년 거래 데이터 없음 — 직접 입력")
            apt_name = st.text_input("아파트명 직접 입력")
            area_py  = st.number_input("평형", 10.0, 100.0, 33.0, 0.5)
            yr_built = st.number_input("준공연도", 1970, 2025, 2000)
        st.markdown("<span style='color:#2563EB; font-weight:bold'>직접 입력</span>", unsafe_allow_html=True)
        units = st.number_input("세대수", 100, 10000, 500, 50)
        st.subheader("② 가격 데이터")
        st.caption("자동 연동")
        actual_eok = st.number_input("최근 실거래가 (억원)", 0.0, 200.0,
                                    float(avg_price) if avg_price else 0.0, 0.5)
        jeonse_eok = st.number_input("전세가 (억원)", 0.5, 150.0,
                                    float(avg_jeonse) if avg_jeonse else 6.0, 0.5)

        st.markdown("<span style='color:#2563EB; font-weight:bold'>직접 입력</span>", unsafe_allow_html=True)
        price_eok  = st.number_input("현재 매매가 (억원)", 1.0, 200.0, 10.0, 0.5)
        asking_eok = st.number_input("현재 최저 호가 (억원, 0=미입력)", 0.0, 200.0, 0.0, 0.5)
        jr_manual = round(jeonse_eok / price_eok * 100, 1)

        st.subheader("③ 입지 조건")

        st.caption("자동 연동")
        sw = st.selectbox("역세권 (도보 거리)", ["도보 5분 이내", "도보 10분 이내", "도보 15분 이상"],
                        index=["도보 5분 이내", "도보 10분 이내", "도보 15분 이상"].index(sw_auto))

        st.markdown("<span style='color:#2563EB; font-weight:bold'>직접 입력</span>", unsafe_allow_html=True)
        ja    = st.selectbox("주요 업무지구 접근성", ["30분 이내", "1시간 이내", "1시간 초과"])
        brand = st.checkbox("1군 브랜드 (삼성·현대·GS·DL·대우·포스코·롯데·HDC·SK·호반)")
        gtx   = st.selectbox("GTX 호재", ["없음", "계획 발표", "착공 중"])
        recon = st.checkbox("재건축 대상 (25년↑ + 용적률 200% 미만 + 서울/1기신도시)")

        st.subheader("⑤ 투자자 정보")
        invest_type = st.selectbox("투자 방식", ["실거주", "갭투자 (전세 임대)"])
        own         = st.selectbox("보유 주택 수", ["1주택(=무주택)", "2주택 (조정지역)", "3주택↑ / 법인"])
        regulated   = st.checkbox("규제지역 (강남3구·용산)",
                                   value=any(k in region for k in ["강남구","서초구","송파구","용산구"]))
        cash_input  = st.number_input("보유 현금 (억원)", 0.0, 200.0, 3.0, 0.5)

        if invest_type == "실거주":
            loan_input    = st.number_input("대출 가능액 (억원)", 0.0, 200.0, 7.0, 0.5)
            interest_rate = st.number_input("대출 금리 (%)", 1.0, 10.0, 4.0, 0.1)
            loan_type     = st.selectbox("상환 방식", ["원리금균등상환", "원금균등상환", "일시상환"])
            loan_years    = st.selectbox("대출 만기(연)", [10, 20, 30], index=1)
            budget        = round(cash_input + loan_input, 2)
            max_gap       = 999
        else:
            loan_input    = 0.0
            interest_rate = 0.0
            loan_type     = "일시상환"
            loan_years    = 0
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
                rp_src = f"✅ API 실거래 {api_cnt}건 평균"
            else:
                rp     = fallback
                why    = "API 키 미입력" if not svc_key else f"건수 부족({api_cnt}건)"
                rp_src = f"⚠️ 하드코딩 기준값 ({why})"

            # 전세가율 — 항상 입력값 기준 (단지별 정확)
            jr     = round(jeonse_eok / price_eok * 100, 1)
            jr_src = f"입력값 기준 {jr:.1f}% (전세 {jeonse_eok}억 / 매매 {price_eok}억)"

            # 계산
            lw   = calc_loc_weight(sw, ja)
            af   = calc_age_factor(yr_built, recon)
            pr   = calc_premium_rate(units, brand, gtx)
            jf   = calc_jeonse_factor(jr)
            V    = calc_V(rp, area_py, lw, af, pr, jf)         
            A    = price_eok * 10000
            gp   = calc_gap(V, A)
            V_eok = round(V / 10000, 2)
            ci = required_cash(price_eok, jeonse_eok, own, invest_type, cash_input, loan_input, regulated)
            b_ok = ci["필요현금"] <= budget and (price_eok - jeonse_eok) <= max_gap
            ag   = round((asking_eok - actual_eok) / actual_eok * 100, 2) if actual_eok > 0 else None
            sig  = signal(gp, ag)
            

            # 시장 신호 (내재가치와 분리)
            trade_total = len([i for i in all_trade_items
                            if i["name"] == apt_name
                            and abs(i["area_m2"] / M2_TO_PYEONG - area_py) <= 2])
            trade_signal = "활발" if trade_total >= 5 else ("보합" if trade_total >= 2 else "침체")

            # 출처
            st.info(f"📊 **평당가:** {rp_src}\n\n🏠 **전세가율:** {jr_src}")

            # 등급
            st.subheader("📋 분석 결과")
            st.markdown(f"### {grade(gp)}")
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
| 전세가율 보정 (Jeonse_Factor) | {jf:.2f}x |
| 가산율 (Premium Rate) | {pr*100:.0f}% |
| 프리미엄 | {round(rp * area_py * pr / 10000, 2)}억 |
| **내재 가치(V)** | **{V_eok}억** |
| **저평가율** | **{gp:+.2f}%** |
                """)

            # 예산
            st.markdown("---")
            st.markdown("#### 💼 투자 예산")

            if ci["대출액"] > 0:
                loan_info     = calc_loan(ci["대출액"], interest_rate, loan_years, loan_type)
                total_interest = loan_info["총이자"]
                monthly        = loan_info["월납입금"]
                total_cost     = round(price_eok + ci["취득세"] + ci["복비"] + total_interest, 2)
            else:
                total_interest = 0
                monthly        = 0
                total_cost     = round(price_eok + ci["취득세"] + ci["복비"], 2)

            b1, b2, b3, b4, b5 = st.columns(5)
            b1.metric("필요 현금", f"{ci['필요현금']:.2f}억",
                    help=f"{ci['mode']}\n매매가 {price_eok}억 - 대출 {ci['대출액']:.2f}억 + 취득세 {ci['취득세']:.3f}억 + 복비 {ci['복비']:.3f}억")
            b2.metric("총 비용", f"{total_cost:.2f}억",
                    help=f"매매가 {price_eok}억 + 취득세 {ci['취득세']:.3f}억 + 복비 {ci['복비']:.3f}억" +
                        (f" + {loan_years}년 이자 {total_interest:.2f}억" if total_interest > 0 else ""))
            b3.metric("총 이자", f"{total_interest:.2f}억" if total_interest > 0 else "-")
            b4.metric("취득세", f"{ci['취득세']:.3f}억")
            b5.metric("복비",   f"{ci['복비']:.3f}억")

            if ci["대출액"] > 0:
                st.info(f"대출 {ci['대출액']:.2f}억 | {loan_type} {loan_years}년 | 월 납입: {monthly:.3f}억 ({monthly*10000:.0f}만원, 첫 달 기준) | 총 이자: {total_interest:.2f}억")
                with st.expander("📅 연차별 월납입금 상세"):
                    if loan_type == "원리금균등상환":
                        st.markdown("| 연차 | 월납입 | 이자 | 원금 |\n|---|---|---|---|")
                        r = interest_rate / 100 / 12
                        n = loan_years * 12
                        remaining = ci["대출액"]
                        for year in range(1, loan_years + 1):
                            month = (year - 1) * 12 + 1
                            interest_m = round(remaining * r, 4)
                            principal_m = round(monthly - interest_m, 4)
                            st.markdown(f"| {year}년차 | {monthly*10000:.0f}만원 | {interest_m*10000:.0f}만원 | {principal_m*10000:.0f}만원 |")
                            for _ in range(12):
                                interest_m = remaining * r
                                remaining -= (monthly - interest_m)
                    elif loan_type == "원금균등상환":
                        r = interest_rate / 100 / 12
                        n = loan_years * 12
                        principal_m = ci["대출액"] / n
                        st.markdown("| 연차 | 월납입 | 이자 | 원금 |\n|---|---|---|---|")
                        for year in range(1, loan_years + 1):
                            month = (year - 1) * 12 + 1
                            remaining = ci["대출액"] - principal_m * (month - 1)
                            m = round(principal_m + remaining * r, 4)
                            st.markdown(f"| {year}년차 | {m*10000:.0f}만원 | {remaining*r*10000:.0f}만원 | {principal_m*10000:.0f}만원 |")
                    elif loan_type == "일시상환":
                        st.markdown("| 연차 | 월납입 | 이자 | 원금 |\n|---|---|---|---|")
                        for year in range(1, loan_years + 1):
                            st.markdown(f"| {year}년차 | {monthly*10000:.0f}만원 | {monthly*10000:.0f}만원 | 0만원 |")
            if b_ok: st.success(f"✅ 예산 적합 — 가용 {budget}억 내 진입 가능")
            else:    st.error(f"❌ 예산 초과 — 필요 {ci['필요현금']:.2f}억 > 가용 {budget}억")

            # 호가
            if ag is not None:
                st.markdown("---")
                st.markdown("#### 🏷️ 호가 분석")
                h1, h2 = st.columns(2)
                h1.metric("호가 괴리율", f"{ag:+.2f}%")
                h2.metric("판정", "🔥 급매" if ag <= 0 else ("⚠️ 호가 상승" if ag >= 10 else "정상"))

            # 시장 신호
            st.markdown("---")
            st.markdown("#### 📊 시장 신호")
            
            # 거래량
            s1, s2 = st.columns(2)
            s1.metric("거래량 추이", trade_signal,
                      delta="수요 강함" if trade_signal == "활발" else
                            ("수요 약함" if trade_signal == "침체" else None))
            
            # 가격 추세 (trend_data 있으면)
            if svc_key and apt_name:
                with st.spinner("가격 추세 계산 중..."):
                    trend_data = fetch_price_trend(svc_key, lawd_cd, apt_name, area_py)
                if len(trend_data) >= 2:
                    values = list(trend_data.values())
                    recent_p = values[-1]
                    prev_p   = values[-3] if len(values) >= 3 else values[0]
                    change   = round((recent_p - prev_p) / prev_p * 100, 1)
                    s2.metric("가격 추세 (1년)", f"{change:+.1f}%",
                              delta="상승" if change >= 5 else ("하락" if change <= -5 else "보합"))

            # Action Plan
            st.markdown("---")
            st.markdown("#### 🎯 Action Plan")
            pros, cons = [], []
            if sw == "도보 5분 이내":    pros.append("역세권 우수 (도보 5분)")
            elif sw == "도보 10분 이내": pros.append("역세권 양호 (도보 10분)")
            else:                        cons.append("역세권 거리 있음 (도보 15분 이상)")

            if ja == "30분 이내":   pros.append("주요 업무지구 30분 이내")
            elif ja == "1시간 초과": cons.append("주요 업무지구 접근성 낮음")
            if jr >= 65:            pros.append(f"전세가율 {jr}% — 하방 경직성 강함")
            if recon:               pros.append("재건축 기대 가치 반영")
            if gp < 0:              cons.append(f"시세 대비 {abs(gp):.1f}% 고평가")
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
            if svc_key and apt_name and 'trend_data' in locals() and len(trend_data) >= 2:
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
                        range=[0, max(df["평균가(억)"]) * 1.2]
                    ),
                    xaxis=dict(
                        gridcolor="#f0f0f0",
                        tickfont=dict(size=13, color="#111"),
                        tickangle=-45,
                        type="category",
                        range=[-0.5, len(df) - 0.3],
                    ),
                    margin=dict(l=10, r=40, t=40, b=60),
                    height=320,
                    font=dict(color="#111", size=13),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"거래 기준: {apt_name} {area_py}평 / 데이터 {len(trend_data)}개 구간")
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
| 지역 평균 평당가 | 국토부 아파트 매매 실거래 (최근 3~12개월 자동 확장) |
| 전세가율 | 국토부 아파트 전월세 실거래 (유사 평형 비교) |

### 저평가율 판단
| 구간 | 판단 |
|---|---|
| +10% 이상 | 확실한 저평가 |
| -10%~+10% | 적정 가치 |
| -10% 이하 | 고평가 |

### ⚠️ 참고용 보조 도구입니다. 투자 전 임장·공인중개사·세무사 확인 필수.
    """)
