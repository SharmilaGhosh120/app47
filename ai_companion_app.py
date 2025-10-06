
"""
AI Companion — Ethical Streamlit Demo App

This Streamlit app demonstrates:
- Integration with OpenAI API via st.secrets["OPENAI_API_KEY"]
- A consent-first data collection form (name, email, phone, optional note)
- Simple chat interface that uses OpenAI to generate replies
- Local SQLite storage of user submissions (consent recorded)
- Placeholder guidance for IP / browser logging and payment integration (Stripe)
- Minimal dependencies; adjust models and policies as needed.

IMPORTANT ETHICS / SAFETY NOTES:
- This example does NOT implement any "Complete Human Meta Data" training or collection.
- Do NOT collect, combine, or use personal data without explicit, informed consent.
- If you need to collect IP or browser info, configure your deployment (proxy or platform)
  to forward headers such as X-Forwarded-For. The app shows placeholders where that
  data can be captured securely by your hosting infrastructure and logged safely.
- Replace the OpenAI usage below with your approved model / API and comply with its terms.

To run:
1. Put your OpenAI API key in Streamlit secrets (e.g., ~/.streamlit/secrets.toml):
   [OPENAI]
   OPENAI_API_KEY = "sk-..."
2. Run: streamlit run ai_companion_app.py
"""

import streamlit as st
import sqlite3
import time
import os
from typing import Optional
import json

# Optional: import OpenAI only if available at runtime
try:
    import openai
except Exception:
    openai = None

# ---------- Configuration ----------
DB_PATH = "ai_companion.db"
APP_TITLE = "AI Companion — Ethical Demo"
OPENAI_SECRET_SECTION = "OPENAI"
OPENAI_KEY_NAME = "OPENAI_API_KEY"

# ---------- Helpers ----------
def init_db(path: str = DB_PATH):
    conn = sqlite3.connect(path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            consent INTEGER,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    return conn

def save_user(conn, name, email, phone, consent, note):
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO users (name, email, phone, consent, note) VALUES (?, ?, ?, ?, ?)
        ''',
        (name, email, phone, int(bool(consent)), note)
    )
    conn.commit()
    return cur.lastrowid

def save_chat(conn, user_id, role, message):
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO chat_logs (user_id, role, message) VALUES (?, ?, ?)
        ''',
        (user_id, role, message)
    )
    conn.commit()

def get_openai_api_key():
    # Attempt to read from Streamlit secrets first (recommended)
    try:
        key = st.secrets[OPENAI_SECRET_SECTION][OPENAI_KEY_NAME]
        return key
    except Exception:
        # fallback to environment
        return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAIKEY")

def call_openai_chat(messages, model="gpt-4o-mini", max_tokens=512, temperature=0.7):
    """
    Simple wrapper to call OpenAI chat completions.
    NOTE: Replace or adjust model name and parameters as needed and allowed.
    """
    key = get_openai_api_key()
    if not key:
        st.error("OpenAI API key not found. Set it in Streamlit secrets or environment variable 'OPENAI_API_KEY'.")
        return "Error: missing API key."

    if openai is None:
        st.error("openai library not installed in this environment (pip install openai).")
        return "Error: openai library not installed."

    openai.api_key = key
    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return f"Error: {e}"

# ---------- UI ----------
st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(APP_TITLE)
st.markdown("**Demo / Example — Consent-first AI companion.**")

# Display simple privacy summary and consent checkbox
with st.expander("Privacy summary (click to expand)"):
    st.markdown(
        """
        - We collect only the information you provide with your explicit consent.
        - Collected data in this demo is stored locally in an SQLite database file.
        - IP or browser data collection is *not* performed automatically by this demo.
          If you deploy the app behind a proxy or platform that forwards headers (e.g., X-Forwarded-For),
          you can capture IPs server-side and attach them to logs. Only do this with clear notice & consent.
        - Payments should be implemented using a PCI-compliant provider (e.g., Stripe). This demo shows where to add it.
        - Do NOT use scraped or sensitive datasets (e.g., "Complete Human Meta Data") without explicit legal bases and consent.
        """
    )

# Cookie-like consent UI
if "cookies_accepted" not in st.session_state:
    st.session_state["cookies_accepted"] = False

if not st.session_state["cookies_accepted"]:
    col1, col2 = st.columns([7,1])
    with col1:
        st.info("We use cookies to improve the site. You can accept or continue without accepting.")
    with col2:
        if st.button("Accept cookies"):
            st.session_state["cookies_accepted"] = True

st.divider()

st.header("Create account / Start conversation")
with st.form("signup_form"):
    name = st.text_input("Full name", placeholder="Jane Doe")
    email = st.text_input("Email")
    phone = st.text_input("Phone (optional)")
    note = st.text_area("Anything you'd like the AI to know (optional)", max_chars=1000)
    consent = st.checkbox("I consent to my data being stored for the purposes described above", value=False)
    submitted = st.form_submit_button("Create account & start")

conn = init_db()

user_id: Optional[int] = None
if submitted:
    if not name or not email:
        st.warning("Please provide at least your name and email to continue.")
    elif not consent:
        st.warning("Please provide consent to proceed.")
    else:
        user_id = save_user(conn, name, email, phone, consent, note)
        st.success(f"Account created (id={user_id}). You can now chat with the AI below.")
        # Save initial note as a system message
        if note:
            save_chat(conn, user_id, "system", note)

# If user_id not from immediate submit, allow entering existing ID for demo
if user_id is None:
    user_id_input = st.text_input("If you already created an account in this session, enter your user id here", value="")
    if user_id_input.strip().isdigit():
        user_id = int(user_id_input.strip())

st.divider()

st.header("AI Companion Chat")
if user_id:
    # Load chat history (last 20)
    cur = conn.cursor()
    cur.execute("SELECT role, message, created_at FROM chat_logs WHERE user_id = ? ORDER BY id DESC LIMIT 40", (user_id,))
    rows = cur.fetchall()
    if rows:
        st.subheader("Recent conversation")
        for role, message, created_at in reversed(rows):
            if role == "user":
                st.markdown(f"**You — {created_at}**: {message}")
            elif role == "assistant":
                st.markdown(f"**AI — {created_at}**: {message}")
            else:
                st.markdown(f"**{role} — {created_at}**: {message}")

    # Chat input
    user_message = st.text_input("Message", key="chat_input")
    col_send, col_clear = st.columns([1,1])
    with col_send:
        if st.button("Send"):
            if not user_message:
                st.warning("Type a message first.")
            else:
                save_chat(conn, user_id, "user", user_message)
                st.info("Sending to AI...")
                # Build messages for OpenAI (system context from user's earlier note)
                system_messages = []
                cur.execute("SELECT message FROM chat_logs WHERE user_id = ? AND role = 'system' ORDER BY id ASC", (user_id,))
                for (m,) in cur.fetchall():
                    system_messages.append({"role":"system","content":m})
                messages = system_messages + [{"role":"user","content":user_message}]
                reply = call_openai_chat(messages)
                # store reply
                save_chat(conn, user_id, "assistant", reply)
                st.success("AI replied:")
                st.write(reply)
    with col_clear:
        if st.button("Clear conversation"):
            cur.execute("DELETE FROM chat_logs WHERE user_id = ?", (user_id,))
            conn.commit()
            st.experimental_rerun()
else:
    st.info("Create an account above to start chatting with the AI.")

st.divider()

st.header("Admin & Data Export (demo)")
st.markdown("This admin panel demos exporting stored user entries as JSON for portability.")
if st.button("Export users to JSON"):
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, phone, consent, note, created_at FROM users")
    users = []
    for row in cur.fetchall():
        users.append({
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "consent": bool(row[4]),
            "note": row[5],
            "created_at": row[6]
        })
    export_json = json.dumps(users, indent=2, default=str)
    st.download_button("Download users.json", data=export_json, file_name="users_export.json", mime="application/json")

st.markdown("### Where to add IP / browser logging (if you need it)")
st.markdown(
    """
If you deploy behind a reverse proxy or platform (e.g., Streamlit Community Cloud, Cloud Run, or a standard web server),
configure the server to forward headers such as `X-Forwarded-For` and `User-Agent`. Your backend code (server side)
should read those headers and associate them with the user's id.
Store a hashed/anonymized version of the IP if required by privacy policy.
Always display the policy and obtain consent before collecting.
"""
)

st.markdown("### Payment integration (placeholder)")
st.markdown(
    """
For payments, integrate a PCI-compliant provider (like Stripe). Do NOT handle raw card data yourself.
Implement payment flow on the server-side and store only tokens/receipts. This demo intentionally omits payment code.
"""
)

st.markdown("---")
st.caption("Demo app — adjust, secure, and review legal/privacy requirements before any real deployment.")
