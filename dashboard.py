import streamlit as st
import sqlite3
import pandas as pd
import json
import subprocess
import time
import os
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Razorpay AI Finance Controller", layout="wide", page_icon="💸")

# Inject custom CSS for colorful metric tiles
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background-color: #f0f2f6;
    border-radius: 8px;
    padding: 15px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
}
/* Total Ingested */
div[data-testid="stMetric"]:nth-of-type(1) div[data-testid="metric-container"] {
    border-left: 5px solid #0052FF;
}
/* Deterministic Matches */
div[data-testid="stMetric"]:nth-of-type(2) div[data-testid="metric-container"] {
    border-left: 5px solid #00C853;
}
/* AI Matches */
div[data-testid="stMetric"]:nth-of-type(3) div[data-testid="metric-container"] {
    border-left: 5px solid #FF00FF;
}
/* Pending Human Review */
div[data-testid="stMetric"]:nth-of-type(4) div[data-testid="metric-container"] {
    border-left: 5px solid #FF3D00;
}
</style>
""", unsafe_allow_html=True)

st.title("💸 Razorpay AI Finance Controller")
st.markdown("Automated Multi-Source Reconciliation Engine (OMS ↔ Gateway ↔ Settlement ↔ Bank)")

# --- Sidebar Actions ---
with st.sidebar:
    st.header("Control Panel")
    demo_replay = st.toggle("🎥 Demo Replay (Golden Run)", value=False, help="Load known-good completed run data to bypass live Gemini quota limits during the demo.")
    
    if st.button("🚀 Run Live Pipeline", type="primary", use_container_width=True, disabled=demo_replay):
        st.cache_data.clear()
        with st.spinner("Running 3-Tier Reconciliation Pipeline (including live Gemini AI analysis)..."):
            try:
                # Use absolute path to venv python to ensure correct env
                python_exe = os.path.join(os.getcwd(), ".venv", "bin", "python")
                if not os.path.exists(python_exe):
                    python_exe = "python"
                    
                result = subprocess.run(
                    [python_exe, "evaluate.py"], 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                st.success("Pipeline executed successfully!")
                st.toast("Pipeline complete!", icon="✅")
            except subprocess.CalledProcessError as e:
                st.error(f"Pipeline failed!\n\n{e.stderr}\n\n{e.stdout}")
    
    st.markdown("---")
    st.markdown("""
    **Pipeline Steps:**
    1. **Tier 1**: Exact matching
    2. **Tier 2**: Fuzzy matching
    3. **Tier 3**: AI Gemini Investigation
    """)

# --- Helper Functions ---
def get_data_paths():
    if demo_replay:
        return "results/golden/metrics.json", "results/golden/audit_trail.db"
    return "results/metrics.json", "audit_trail.db"

@st.cache_data(ttl=2)
def load_metrics(metrics_path):
    try:
        with open(metrics_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def get_db_connection(db_path):
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- Load Data ---
metrics_path, db_path = get_data_paths()
metrics = load_metrics(metrics_path)
conn = get_db_connection(db_path)

if demo_replay:
    st.info("🎥 **DEMO REPLAY MODE ACTIVE** — Displaying data from a completed Golden Run. Live API calls are disabled.", icon="ℹ️")

if metrics and conn:
    # --- Top KPIs ---
    st.markdown("### Executive Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records Ingested", metrics.get("total_records", 0))
    
    # Calculate unique matched records 
    try:
        # Get the batch_id from metrics
        batch_id = metrics.get("batch_id")
        if not batch_id:
            # Fallback to the most recent batch in the DB
            batch_id = conn.execute("SELECT id FROM batch_runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]

        matched_decisions = conn.execute("SELECT record_source, record_id, matched_source, matched_record_id, match_tier FROM match_decisions WHERE decision = 'matched' AND batch_id = ?", (batch_id,)).fetchall()
        unique_matched_records = set()
        for d in matched_decisions:
            unique_matched_records.add((d["record_source"], d["record_id"]))
            if d["matched_record_id"] and d["matched_source"] != "AI_SUGGESTED":
                unique_matched_records.add((d["matched_source"], d["matched_record_id"]))
        total_unique_matched = len(unique_matched_records)
    except Exception:
        total_unique_matched = 0

    try:
        human_review_count = conn.execute("SELECT COUNT(*) FROM match_decisions WHERE decision != 'matched' AND batch_id = ?", (batch_id,)).fetchone()[0]
        queue_df = pd.read_sql(f"SELECT * FROM match_decisions WHERE decision != 'matched' AND batch_id = '{batch_id}'", conn)
        audit_df = pd.read_sql(f"SELECT md.record_source, md.record_id, md.matched_record_id, md.decision, md.match_tier, ai.explanation, md.confidence, ai.prompt_text FROM match_decisions md JOIN ai_investigations ai ON md.id = ai.match_decision_id WHERE md.batch_id = '{batch_id}'", conn)
    except Exception as e:
        human_review_count = 0
        queue_df = pd.DataFrame()
        audit_df = pd.DataFrame()

    matches_made = metrics.get('matches_made', 0)
    col2.metric("Successful Matches (Pairs)", matches_made)
    
    ai_matches = metrics.get("tier3_matched", 0)
    col3.metric("AI Match Decisions (Pairs)", ai_matches)
    
    col4.metric("Exceptions (Pairs)", human_review_count, delta_color="inverse")
    
    if ai_matches == 0:
        st.warning("⚠️ **Note:** Tier 3 AI processed 0 successful matches. Check the Human Review Queue below to see if the LLM API quota was exhausted or if it flagged everything for manual review.")

    # --- Tabs ---
    tab1, tab2, tab3 = st.tabs(["📊 Reconciliation Funnel", "⚠️ Human Review Queue", "🤖 AI Audit Trail"])
    
    with tab1:
        st.markdown("### The 3-Tier Match Funnel")
        total_decisions = metrics.get("tier1_matched", 0) + metrics.get("tier2_matched", 0) + ai_matches + human_review_count
        fig = go.Figure(go.Funnel(
            y=["Total Evaluated Pairs", "Tier 1 Matches (Pairs)", "Tier 2 Matches (Pairs)", "Tier 3 AI Matches (Pairs)", "Exceptions (Pairs)"],
            x=[
                total_decisions, 
                metrics.get("tier1_matched", 0), 
                metrics.get("tier2_matched", 0), 
                ai_matches, 
                human_review_count
            ],
            textinfo="value+percent initial"
        ))
        fig.update_layout(margin={"t": 30, "b": 10})
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### Exceptions Requiring Human Review")
        st.markdown("These records failed all 3 tiers (including AI analysis) and require manual ops intervention.")
        if not queue_df.empty:
            for _, row in queue_df.iterrows():
                with st.expander(f"🛑 {row['record_source'].upper()} | {row['record_id']} - {row['decision'].upper()}"):
                    st.write(f"**Explanation:** {row['explanation']}")
                    st.write(f"**Tier Reached:** {row['match_tier']}")
        else:
            st.info("No exceptions in queue!")

    with tab3:
        st.markdown("### Immutable AI Audit Trail")
        st.markdown("Every AI decision is logged with its prompt, confidence score, and structured explanation for full auditability.")
        if not audit_df.empty:
            for _, row in audit_df.iterrows():
                with st.expander(f"🤖 {row['record_source'].upper()} | {row['record_id']} ➔ {row['matched_record_id']} (Confidence: {row['confidence']})"):
                    st.write(f"**Decision:** {row['decision']}")
                    st.write(f"**AI Explanation:** {row['explanation']}")
        else:
            st.info("No AI explanations logged yet.")

else:
    st.info("No metrics found. Click 'Run Live Pipeline' in the sidebar or toggle 'Demo Replay'.")

if conn:
    conn.close()
