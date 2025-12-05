import streamlit as st
import pandas as pd
from backend import ask_bot, df as backend_df

# 1. PAGE CONFIG
st.set_page_config(page_title="Autonomous Claims Agent", page_icon="🤖", layout="wide")

# 2. CSS STYLING
st.markdown("""
<style>
    .kpi-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
    }
    .kpi-value { font-size: 24px; font-weight: bold; color: #4CAF50; }
    .kpi-label { font-size: 14px; color: #AAA; }
</style>
""", unsafe_allow_html=True)

# 3. SIDEBAR / KPIs
with st.sidebar:
    st.header("📊 Dashboard Stats")
    
    # Calculate KPIs from backend_df
    total_claims = len(backend_df)
    total_amount = backend_df['amount'].sum() if 'amount' in backend_df else 0
    denial_rate = 0
    if 'status' in backend_df:
        denied_count = backend_df[backend_df['status'] == 'denied'].shape[0]
        denial_rate = (denied_count / total_claims) * 100 if total_claims > 0 else 0

    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{total_claims:,}</div>
        <div class="kpi-label">Total Claims</div>
    </div>
    <div style="height: 10px"></div>
    <div class="kpi-card">
        <div class="kpi-value">${total_amount:,.0f}</div>
        <div class="kpi-label">Total Volume</div>
    </div>
    <div style="height: 10px"></div>
    <div class="kpi-card">
        <div class="kpi-value">{denial_rate:.1f}%</div>
        <div class="kpi-label">Denial Rate</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    st.markdown("### Quick Filters")
    if st.button("Show Denied Claims"):
        st.session_state.prompt_input = "How many claims were denied?"
    if st.button("Diabetes Analysis"):
        st.session_state.prompt_input = "What is the total claim amount for Diabetes?"

# 4. MAIN CHAT INTERFACE
st.title("🤖 Autonomous Claims Agent")
st.markdown("Ask about **Data Analytics** (counts, sums) or **Policy Rules**.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle Quick Filter clicks (Pre-fills the input)
if "prompt_input" in st.session_state:
    prompt = st.session_state.prompt_input
    del st.session_state.prompt_input # Consume it
    # Force a rerun to process the input automatically isn't clean in Streamlit, 
    # so we usually just populate the chat input or run it directly.
    # For simplicity, we process it as if the user typed it:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = ask_bot(prompt)
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})

# Standard Chat Input
elif prompt := st.chat_input("Ask a question about claims..."):
    # User message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = ask_bot(prompt)
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})