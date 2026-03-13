import streamlit as st
import google.generativeai as genai
from groq import Groq
import tempfile
import os
from pathlib import Path

groq_default = os.environ.get("GROQ_API_KEY", "")
gemini_default = os.environ.get("GEMINI_API_KEY", "")

st.set_page_config(page_title="สรุปประชุม", page_icon="🎙️", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Space+Mono:wght@400;700&display=swap');
* { font-family: 'Sarabun', sans-serif; }
body, .stApp { background-color: #0f0f14; color: #e8e6e0; }
h1, h2, h3 { font-family: 'Space Mono', monospace !important; }
.main-title { font-family: 'Space Mono', monospace; font-size: 2rem; font-weight: 700; color: #f0e6c8; letter-spacing: -1px; margin-bottom: 0.2rem; }
.sub-title { color: #6b7a6e; font-size: 1rem; margin-bottom: 2rem; }
.result-box { background: #12121a; border-left: 3px solid #8fa87d; border-radius: 0 8px 8px 0; padding: 1.2rem 1.5rem; margin-top: 0.8rem; white-space: pre-wrap; font-size: 0.95rem; line-height: 1.8; color: #d4d0c8; }
.transcript-box { background: #12121a; border-left: 3px solid #5a7a8a; border-radius: 0 8px 8px 0; padding: 1.2rem 1.5rem; margin-top: 0.8rem; white-space: pre-wrap; font-size: 0.88rem; line-height: 1.7; color: #9a9890; max-height: 300px; overflow-y: auto; }
.status-pill { display: inline-block; background: #1e2e1e; color: #8fa87d; border: 1px solid #3a5a3a; border-radius: 20px; padding: 0.2rem 0.8rem; font-size: 0.8rem; font-family: 'Space Mono', monospace; margin-bottom: 1rem; }
.stButton > button { background: #8fa87d !important; color: #0f0f14 !important; border: none !important; border-radius: 8px !important; font-family: 'Sarabun', sans-serif !important; font-weight: 700 !important; font-size: 1rem !important; padding: 0.6rem 2rem !important; width: 100%; transition: all 0.2s ease !important; }
.stButton > button:hover { background: #a8c494 !important; transform: translateY(-1px); }
.divider { border: none; border-top: 1px solid #2a2a38; margin: 1.5rem 0; }
label, .stMarkdown p { color: #b0aea8 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🎙️ สรุปประชุม</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">อัปโหลดไฟล์เสียง → ถอดคำพูด → สรุปอัตโนมัติ</div>', unsafe_allow_html=True)

with st.expander("⚙️ ตั้งค่า API Keys (ครั้งแรกเท่านั้น)", expanded=not st.session_state.get("keys_saved")):
    groq_key = st.text_input(
        "Groq API Key (ถอดเสียง)",
        type="password",
        placeholder="gsk_...",
        value=st.session_state.get("groq_api_key", groq_default),
        help="ฟรี สมัครที่ https://console.groq.com"
    )
    gemini_key = st.text_input(
        "Gemini API Key (สรุป)",
        type="password",
        placeholder="AIzaSy...",
        value=st.session_state.get("gemini_api_key", gemini_default),
        help="ฟรี สมัครที่ https://aistudio.google.com"
    )
    if groq_key and gemini_key:
        st.session_state["groq_api_key"] = groq_key
        st.session_state["gemini_api_key"] = gemini_key
        st.session_state["keys_saved"] = True
        st.success("✅ บันทึก API Keys แล้ว")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "📁 อัปโหลดไฟล์เสียงประชุม",
    type=["mp3", "mp4", "m4a", "wav", "ogg", "webm"],
    help="รองรับ mp3, mp4, m4a, wav, ogg, webm — ขนาดสูงสุด 25MB"
)

col1, col2 = st.columns([1, 2])
with col1:
    language = st.selectbox("ภาษา", ["th", "en"], index=0)
with col2:
    summary_style = st.selectbox(
        "รูปแบบสรุป",
        ["สรุปประเด็นหลัก + Action Items", "สรุปแบบละเอียด", "เฉพาะ Action Items", "Minutes of Meeting (MOM)"],
        index=0,
    )

PROMPTS = {
    "สรุปประเด็นหลัก + Action Items": """สรุปการประชุมต่อไปนี้เป็นภาษาไทย โดยแบ่งเป็น:\n\n**📌 ประเด็นหลักที่หารือ**\n(สรุปสั้นๆ 3-7 ประเด็น)\n\n**✅ Action Items**\n(งานที่ต้องทำ พร้อมผู้รับผิดชอบและ deadline ถ้ามี)\n\n**🔑 ข้อสรุป / การตัดสินใจ**\n(สิ่งที่ตกลงกันในที่ประชุม)""",
    "สรุปแบบละเอียด": """สรุปการประชุมต่อไปนี้แบบละเอียดเป็นภาษาไทย ครอบคลุมทุกประเด็นที่หารือ การตัดสินใจ ข้อถกเถียง และผลสรุป""",
    "เฉพาะ Action Items": """จากการประชุมต่อไปนี้ ให้ระบุ Action Items ทั้งหมด พร้อมผู้รับผิดชอบและ deadline (ถ้ามีการกล่าวถึง) เป็นภาษาไทย""",
    "Minutes of Meeting (MOM)": """เขียน Minutes of Meeting (MOM) ภาษาไทยจากการประชุมต่อไปนี้ ประกอบด้วย:\n- วัตถุประสงค์การประชุม\n- ผู้เข้าร่วม (ถ้ามีการกล่าวถึง)\n- สรุปการหารือแต่ละหัวข้อ\n- มติที่ประชุม\n- Action Items และผู้รับผิดชอบ""",
}

if st.button("🚀 เริ่มสรุปประชุม"):
    if not uploaded_file:
        st.warning("⚠️ กรุณาอัปโหลดไฟล์เสียงก่อน")
    elif not st.session_state.get("groq_api_key") or not st.session_state.get("gemini_api_key"):
        st.warning("⚠️ กรุณาใส่ API Keys ทั้งสองตัวก่อน")
    else:
        with st.status("🎙️ กำลังถอดคำพูด (Groq Whisper)...", expanded=True) as status:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            try:
                client = Groq(api_key=st.session_state["groq_api_key"])
                with open(tmp_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        file=(uploaded_file.name, audio_file.read()),
                        model="whisper-large-v3-turbo",
                        language=language,
                        response_format="text",
                    )
                transcript = transcription
                status.update(label="✅ ถอดคำพูดสำเร็จ", state="complete")
            except Exception as e:
                st.error(f"❌ Groq Error: {e}")
                os.unlink(tmp_path)
                st.stop()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        with st.status("✨ กำลังสรุป (Gemini)...", expanded=True) as status:
            try:
                genai.configure(api_key=st.session_state["gemini_api_key"])
                gemini = genai.GenerativeModel("gemini-1.5-flash")
                prompt = PROMPTS[summary_style] + f"\n\n---\nข้อความจากการประชุม:\n{transcript}"
                response = gemini.generate_content(prompt)
                summary = response.text
                status.update(label="✅ สรุปสำเร็จ", state="complete")
            except Exception as e:
                st.error(f"❌ Gemini Error: {e}")
                st.stop()

        st.markdown('<div class="status-pill">✓ เสร็จสิ้น</div>', unsafe_allow_html=True)
        st.markdown("### 📋 สรุปการประชุม")
        st.markdown(f'<div class="result-box">{summary}</div>', unsafe_allow_html=True)
        st.markdown('<hr class="divider">', unsafe_allow_html=True)

        with st.expander("📝 ดู Transcript ต้นฉบับ"):
            st.markdown(f'<div class="transcript-box">{transcript}</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button("⬇️ ดาวน์โหลดสรุป (.txt)", data=summary, file_name="meeting_summary.txt", mime="text/plain")
        with col_b:
            st.download_button("⬇️ ดาวน์โหลด Transcript (.txt)", data=transcript, file_name="transcript.txt", mime="text/plain")
