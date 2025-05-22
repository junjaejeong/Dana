import streamlit as st
import gspread
import json
from datetime import datetime
import random
import pandas as pd

# ✅ 1. Streamlit secrets에서 JSON 문자열 발환
google_sheet_json_str = st.secrets["GOOGLE_SHEET_JSON"]

# ✅ 2. 문자열 → 디션에드 변환
try:
    credentials_dict = json.loads(google_sheet_json_str)
except json.JSONDecodeError as e:
    st.error("❌ GOOGLE_SHEET_JSON이 유효한 JSON 형식이 아님니다.")
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

# ✅ 5. 페이지 설정
st.set_page_config(page_title="영단어 학습 앱", layout="wide")
mode = st.sidebar.radio("🔀 모드 선택", ["단어 등록", "퀴즈 시작"], index=1)

# ✅ 6. 단어 등록 모드
if mode == "단어 등록":
    st.header("📥 단어 등록")
    st.write("영어 단어와 한국어 뜻을 입력하세요.")

    inputs = []
    for i in range(10):
        c1, c2 = st.columns(2)
        with c1:
            eng = st.text_input(f"{i+1}. 영어 단어", key=f"eng_{i}")
        with c2:
            kor = st.text_input(f"{i+1}. 뜻", key=f"kor_{i}")
        inputs.append((eng, kor))

    if st.button("💾 저장하기"):
        today = datetime.now().strftime("%Y-%m-%d")
        cnt = 0
        for eng, kor in inputs:
            if eng and kor:
                sheet.append_row([eng.strip(), kor.strip(), today])
                cnt += 1
        st.success(f"✅ {cnt}개 단어가 저장되었습니다.")

# ✅ 7. 퀴즈 모드
elif mode == "퀴즈 시작":
    st.header("Dana's 영어 단어 퀴즈")
    try:
        raw_data = sheet.get_all_values()
        if len(raw_data) < 2:
            st.info("등록된 단어가 충분하지 않습니다.")
        else:
            df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
            if '영단어' not in df.columns or '뜻' not in df.columns:
                st.error("❌ 시트의 첫 행에 '영단어'와 '뜻' 컬럼명이 필요합니다.")
            else:
                quiz_data = df.sample(n=min(10, len(df)))
                for idx, row in quiz_data.iterrows():
                    st.write(f"#### Q{idx+1}. {row['뜻']}")
                    ans = st.text_input("답안:", key=f"answer_{idx}")
    except Exception as e:
        st.error(f"데이터 조회 또는 처리 중 오류 발생: {e}")
