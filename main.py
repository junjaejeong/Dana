import streamlit as st
import gspread
import json
from datetime import datetime
import random
import pandas as pd

# ✅ 1. Streamlit secrets에서 JSON 문자열 불러오기
google_sheet_json_str = st.secrets["GOOGLE_SHEET_JSON"]

# ✅ 2. 문자열 → 딕셔너리로 변환
try:
    credentials_dict = json.loads(google_sheet_json_str)
except json.JSONDecodeError as e:
    st.error("❌ GOOGLE_SHEET_JSON가 유효한 JSON 형식이 아님니다.")
    st.error(f"JSON 오류: {e}")
    st.stop()

# ✅ 3. gspread 인증
try:
    client = gspread.service_account_from_dict(credentials_dict)
except Exception as e:
    st.error("❌ Google Sheets 인증에 실패했습니다.")
    st.error("🔍 서비스 계정 JSON 형식을 확인하고, GCP에서 API가 활성화되었는지 확인해주세요.")
    st.error(f"오류 메시지: {e}")
    st.stop()

# ✅ 4. 스프레드시트 연결
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1LeJbpsS1eOzf2ZT8qIWhzYOf3hrdqefyoV3Qf9o2EgQ/edit"

try:
    sheet = client.open_by_url(SPREADSHEET_URL).sheet1
    st.success("✅ Google 스프레드시트 연결 성공!")
except gspread.exceptions.SpreadsheetNotFound:
    st.error("❌ 스프레드시트를 찾을 수 없습니다. URL이 정확한지, 서비스 계정이 편집자로 추가되어있는지 확인해주세요.")
    st.stop()
except gspread.exceptions.APIError as e:
    st.error("❌ Google Sheets API 오류 발생!")
    st.error(f"서비스 계정: {credentials_dict.get('client_email')}")
    st.error(f"문서 URL: {SPREADSHEET_URL}")
    st.error("🔍 서비스 계정에 스프레드시트를 공용했는지, GCP에서 Sheets API가 활성화되어 있는지 확인해주세요.")
    st.error(f"오류 메시지: {e}")
    st.stop()
except Exception as e:
    st.error("❌ 알 수 없는 오류가 발생했습니다.")
    st.error(f"오류 메시지: {e}")
    st.stop()

# ✅ 5. 연결한 sheet에서 데이터 가져오기
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    st.write("### 데이터 조회", df)
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
