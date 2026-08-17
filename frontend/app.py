"""Minimal Streamlit chat UI for the Invoice AI Assistant, calling the FastAPI backend."""

import requests
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000/ask"

st.set_page_config(page_title="Invoice AI Assistant", page_icon="🧾")
st.title("🧾 Invoice AI Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask about your invoices...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(BACKEND_URL, json={"question": question}, timeout=60)
                response.raise_for_status()
                answer = response.json()["answer"]
            except requests.RequestException as e:
                answer = f"Error calling backend: {e}"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
