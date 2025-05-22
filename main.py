import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import random
import pandas as pd
import json
from io import StringIO

# ─── 1) Google Sheets 인증 & 시트 연결 ────────────────────────────

# gspread 클라이언트와 시트 객체를 캐시하는 함수
@st.cache_resource # 이전에 st.cache 또는 st.cache_data를 사용했을 수 있지만, 객체 초기화에는 st.cache_resource가 적합합니다.
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_str = st.secrets["GOOGLE_SHEET_JSON"]
    creds_dict = json.loads(json_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # sheet 객체까지 이 함수 안에서 열어서 반환
    sheet = client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1LeJbpsS1eOzf2ZT8qIWhzYOf3hrdqefyoV3Qf9o2EgQ/edit"
    ).sheet1
    return sheet

# 캐시된 함수를 호출하여 sheet 객체를 가져옵니다.
sheet = get_gspread_client() # <- 이 부분이 핵심 수정 사항

# ─── 2) 페이지 설정 & 모드 선택 ───────────────────────────────────
st.set_page_config(page_title="영단어 학습 앱", layout="wide")
mode = st.sidebar.radio("🔀 모드 선택", ["단어 등록", "퀴즈 시작"], index=1)

# ─── 3) 모드 전환 시 세션 초기화 ─────────────────────────────────
if "last_mode" not in st.session_state:
    st.session_state.last_mode = None
if st.session_state.last_mode != mode:
    for k in ["quiz_started","quiz_index","quiz_data","quiz_type",
              "all_answers","answered","retry","row_count"]:
        st.session_state.pop(k, None)
    st.session_state.last_mode = mode

# ─── 4) 단어 등록 모드 ─────────────────────────────────────────────
if mode == "단어 등록":
    if "row_count" not in st.session_state:
        st.session_state.row_count = 10

    st.header("📥 단어 등록")
    st.write("영어 단어와 한국어 뜻을 입력하세요. (최초 10개 필드)")

    inputs = []
    for i in range(st.session_state.row_count):
        c1, c2 = st.columns(2)
        with c1:
            eng = st.text_input(f"{i+1}. 영어 단어", key=f"eng_{i}")
        with c2:
            kor = st.text_input(f"{i+1}. 한국어 뜻", key=f"kor_{i}")
        inputs.append((eng, kor))

    ca, cs = st.columns(2)
    with ca:
        if st.button("➕ 한 줄 추가"):
            st.session_state.row_count += 1
            st.rerun()
    with cs:
        if st.button("💾 저장하기"):
            today = datetime.now().strftime("%Y-%m-%d")
            cnt = 0
            for eng, kor in inputs:
                if eng and kor:
                    sheet.append_row([eng.strip(), kor.strip(), today])
                    cnt += 1
            st.success(f"✅ {cnt}개 단어가 저장되었습니다.")
            # 데이터가 업데이트되었으므로 데이터 캐시와 리소스 캐시를 모두 지웁니다.
            # get_gspread_client() 함수의 결과물(sheet 객체) 자체가 캐시되어 있으므로,
            # 데이터가 변경되면 이 캐시를 무효화하여 다음 번에 새로운 sheet 객체를 가져오도록 해야 합니다.
            st.cache_resource.clear() # <- 중요: gspread 클라이언트 캐시를 지웁니다.
            st.cache_data.clear()    # <- 데이터 캐시도 지웁니다.
            st.rerun() # 변경된 데이터로 새로고침
    st.stop()

# ─── 5) 퀴즈 모드 ───────────────────────────────────────────────────

# Google Sheets에서 모든 데이터를 가져오는 함수를 정의하고 캐시합니다.
# sheet 객체는 이미 get_gspread_client()에서 캐시되었으므로, load_quiz_data는 sheet_obj의 변화를 감지하여 캐시를 무효화하지 않습니다.
# 따라서 sheet_obj가 변경될 때 캐시를 지우도록 수동으로 제어해야 합니다.
@st.cache_data
def load_quiz_data(sheet_obj):
    """
    Google Sheets에서 모든 데이터를 가져와 캐시하는 함수.
    이 함수는 sheet_obj의 변화가 없으면 다시 실행되지 않습니다.
    """
    return sheet_obj.get_all_records()

# 캐시된 함수를 호출하여 데이터를 가져옵니다.
data = load_quiz_data(sheet) # <- 수정된 부분 (함수 호출 방식은 동일)

st.header("Dana's 영어 단어 퀴즈")

# ─── 5.1) 세션 초기화 ─────────────────────────────────────────────
if "quiz_started" not in st.session_state:
    st.session_state.update({
        "quiz_started": False,
        "quiz_index":   0,
        "quiz_data":    [],
        "quiz_type":    "객관식",
        "all_answers":  [],
        "answered":     False,
        "retry":        False,
    })

# ─── 5.2) 퀴즈 시작 화면 ─────────────────────────────────────────
if not st.session_state.quiz_started:
    st.write("#### 기간과 문제 유형을 선택하고 ▶️ 시작 버튼을 누르세요")
    
    date_mode = st.radio("📅 기간 선택 방식", ["특정 날짜", "기간 범위"])
    
    if date_mode == "특정 날짜":
        sel_date = st.date_input("날짜 선택")
        start_date = end_date = sel_date
    else:
        date_range = st.date_input("기간 범위 선택", value=())
        if len(date_range) == 2:
            start_date, end_date = date_range
        elif len(date_range) == 1:
            start_date = end_date = date_range[0]
            st.info("종료 날짜도 선택해주세요")
        else:
            st.warning("시작 날짜와 종료 날짜를 선택해주세요")
            start_date = end_date = None
    
    qtype = st.radio("문제 유형", ["객관식","주관식","혼합"])
    
    if st.button("▶️ 시작"):
        if date_mode == "기간 범위" and (start_date is None or end_date is None):
            st.warning("❌ 기간을 올바르게 선택해주세요.")
        else:
            rows = []
            for r in data: # <- 이미 캐시된 데이터를 사용
                upload_date_str = r.get("업로드날짜", "").strip()
                if upload_date_str:
                    try:
                        upload_date = datetime.strptime(upload_date_str, "%Y-%m-%d").date()
                        if start_date <= upload_date <= end_date:
                            rows.append(r)
                    except ValueError:
                        continue
            
            if not rows:
                msg = f"{start_date.strftime('%Y-%m-%d')}" if date_mode == "특정 날짜" else f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
                st.warning(f"❌ {msg}에 등록된 단어가 없습니다.")
            else:
                st.session_state.quiz_data    = random.sample(rows, min(20, len(rows)))
                st.session_state.quiz_type    = qtype
                st.session_state.quiz_started = True
                st.session_state.quiz_index   = 0
                st.session_state.all_answers  = []
                st.session_state.answered     = False
                st.session_state.retry        = False
                st.rerun()
    st.stop()

# ─── 5.3) 퀴즈 종료 및 요약 ────────────────────────────────────────
if st.session_state.quiz_index >= len(st.session_state.quiz_data):
    total   = len(st.session_state.all_answers)
    correct = sum(a["is_correct"] for a in st.session_state.all_answers)
    st.markdown("#### 🎉 퀴즈 완료!")
    st.write(f"**총 {total}문제 중 {correct}문제 맞았습니다!**")
    df = pd.DataFrame(st.session_state.all_answers)
    st.dataframe(df.rename(columns={
        "word": "영단어", "meaning": "뜻",
        "user_ans": "내 답안", "correct_ans": "정답",
        "is_correct": "정답여부"
    }), use_container_width=True)

    if not st.session_state.retry and correct < total:
        if st.button("🔄 오답 다시 풀기"):
            wrong = [a for a in st.session_state.all_answers if not a["is_correct"]]
            st.session_state.quiz_data   = [{"영단어":w["word"], "뜻":w["meaning"]} for w in wrong]
            st.session_state.quiz_index  = 0
            st.session_state.all_answers = []
            st.session_state.answered    = False
            st.session_state.retry       = False
            st.rerun()
    st.stop()

# ─── 5.4) 문제 화면 ─────────────────────────────────────────────────
q = st.session_state.quiz_data[st.session_state.quiz_index]
st.write(f"#### 문제 {st.session_state.quiz_index+1} / {len(st.session_state.quiz_data)}")

q_type = st.session_state.quiz_type
if q_type == "혼합":
    type_key = f"qtype_{st.session_state.quiz_index}"
    if type_key not in st.session_state:
        st.session_state[type_key] = random.choice(["객관식", "주관식"])
    q_type = st.session_state[type_key]

if q_type == "객관식":
    st.markdown("""<style>div[role='radiogroup'] > label {
        display: flex !important; align-items: center !important;
        margin-bottom: 0.5rem !important; margin-right: 0 !important;
    }</style>""", unsafe_allow_html=True)

    direction_key = f"direction_{st.session_state.quiz_index}"
    if direction_key not in st.session_state:
        st.session_state[direction_key] = random.choice(["kor_to_eng", "eng_to_kor"])
    direction = st.session_state[direction_key]

    opt_key = f"opts_{st.session_state.quiz_index}"
    if opt_key not in st.session_state:
        if direction == "kor_to_eng":
            distractors = [d["영단어"] for d in data if d["영단어"].strip().lower() != q["영단어"].strip().lower()]
            opts = random.sample(distractors, min(3, len(distractors))) + [q["영단어"]]
        else:
            distractors = [d["뜻"] for d in data if d["뜻"].strip().lower() != q["뜻"].strip().lower()]
            opts = random.sample(distractors, min(3, len(distractors))) + [q["뜻"]]
        random.shuffle(opts)
        st.session_state[opt_key] = opts
    options = st.session_state[opt_key]

    if direction == "kor_to_eng":
        question_text = f'"{q["뜻"]}"에 해당하는 영어 단어는?'
        correct_answer = q["영단어"]
    else:
        question_text = f'"{q["영단어"]}"의 뜻은?'
        correct_answer = q["뜻"]

    sel_key = f"sel_{st.session_state.quiz_index}"
    selected = st.radio(question_text, options, key=sel_key)

    if not st.session_state.answered:
        if st.button("정답 확인하기", key=f"check_btn_{st.session_state.quiz_index}"):
            is_corr = (selected.strip().lower() == correct_answer.strip().lower())
            st.session_state.all_answers.append({
                "word": q["영단어"], "meaning": q["뜻"],
                "user_ans": selected, "correct_ans": correct_answer,
                "is_correct": is_corr
            })
            st.session_state.answered = True
            st.rerun()
    else:
        last_answer = st.session_state.all_answers[-1]
        if last_answer["is_correct"]:
            st.success("✅ 정답입니다!")
        else:
            st.error(f"❌ 오답입니다. 정답: {correct_answer}")

        if st.button("▶️ 다음 문제 풀기", key=f"next_btn_{st.session_state.quiz_index}"):
            st.session_state.pop(opt_key, None)
            st.session_state.pop(sel_key, None)
            st.session_state.pop(direction_key, None)
            if st.session_state.quiz_type == "혼합":
                st.session_state.pop(f"qtype_{st.session_state.quiz_index}", None)
            st.session_state.quiz_index += 1
            st.session_state.answered = False
            st.rerun()

elif q_type == "주관식":
    inp_key = f"input_{st.session_state.quiz_index}"
    ans = st.text_input(f'"{q["뜻"]}"에 해당하는 영어 단어는?', key=inp_key)

    if not st.session_state.answered:
        if st.button("정답 확인하기", key=f"check_sa_btn_{st.session_state.quiz_index}"):
            is_corr = (ans.strip().lower() == q["영단어"].strip().lower())
            st.session_state.all_answers.append({
                "word": q["영단어"], "meaning": q["뜻"],
                "user_ans": ans, "correct_ans": q["영단어"],
                "is_correct": is_corr
            })
            st.session_state.answered = True
            st.rerun()
    else:
        last_answer = st.session_state.all_answers[-1]
        if last_answer["is_correct"]:
            st.success("✅ 정답입니다!")
        else:
            st.error(f"❌ 오답입니다. 정답: {q['영단어']}")

        if st.button("▶️ 다음 문제 풀기", key=f"next_sa_btn_{st.session_state.quiz_index}"):
            st.session_state.pop(inp_key, None)
            if st.session_state.quiz_type == "혼합":
                st.session_state.pop(f"qtype_{st.session_state.quiz_index}", None)
            st.session_state.quiz_index += 1
            st.session_state.answered = False
            st.rerun()
