"""
Council Tracker dashboard.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import os

import joblib
import pandas as pd
import streamlit as st

from config import CURRENT_TERM, RAW_DATA_DIR
from src.ingest.fetch_datasets import main as fetch_datasets
from src.model.engagement_score import add_engagement_priority
from src.model.features import build_feature_table
from src.model.train_outcome_model import CATEGORICAL, NUMERIC, train
from src.pipeline.join_decisions import build_decisions_table
from src.pipeline.load_voting_record import load_vote_events
from src.pipeline.stage import add_stage

st.set_page_config(page_title="Council Tracker", layout="wide")

RRL_PATH = f"{RAW_DATA_DIR}/report_request_log_{CURRENT_TERM}.xlsx"
VR_PATH = f"{RAW_DATA_DIR}/voting_record_{CURRENT_TERM}.csv"
MODEL_PATH = "models/outcome_model.joblib"


def _data_ready() -> bool:
    return os.path.exists(RRL_PATH) and os.path.exists(VR_PATH)


@st.cache_data
def load_decisions() -> pd.DataFrame:
    return add_stage(build_decisions_table(RRL_PATH, VR_PATH))


@st.cache_data
def load_feature_table() -> pd.DataFrame:
    return build_feature_table(load_vote_events(VR_PATH))


@st.cache_data
def load_vote_outcomes_with_predictions(_model_mtime: float) -> pd.DataFrame:
    # _model_mtime busts the cache whenever the model file is retrained.
    features = load_feature_table()
    model = joblib.load(MODEL_PATH)
    features = features.copy()
    features["p_carried"] = model.predict_proba(features[CATEGORICAL + NUMERIC])[:, 1]
    return add_engagement_priority(features, proba_col="p_carried")


@st.cache_resource
def get_model(_model_mtime: float):
    return joblib.load(MODEL_PATH)


@st.cache_data
def committee_motion_lookup() -> tuple[list[str], list[str], dict, dict]:
    features = load_feature_table()
    committees = sorted(features["committee"].unique())
    motion_types = sorted(features["motion_type"].unique())
    committee_overall = features.groupby("committee")["target"].mean().to_dict()
    motion_overall = features.groupby("motion_type")["target"].mean().to_dict()
    return committees, motion_types, committee_overall, motion_overall


st.title("Council Tracker")
st.caption(
    "Decision lifecycle + outcome priority for Toronto City Council, built on the City of Toronto's "
    "Report Request Log and Council Voting Record (Open Government Licence - Toronto)."
)

if not _data_ready():
    st.warning("Raw data hasn't been downloaded yet.")
    if st.button("Download data now"):
        with st.spinner("Downloading from Toronto Open Data..."):
            fetch_datasets()
        st.cache_data.clear()
        st.rerun()
    st.stop()

tab1, tab2, tab3 = st.tabs(["Decision Lifecycle", "Vote Outcomes & Priority", "Try the Model"])

# --- Tab 1: Decision Lifecycle Tracker -------------------------------------
with tab1:
    decisions = load_decisions()
    st.subheader(f"{len(decisions):,} report requests")

    col1, col2 = st.columns(2)
    with col1:
        stage_options = sorted(decisions["stage"].unique())
        stage_filter = st.multiselect("Stage", stage_options, default=stage_options)
    with col2:
        body_options = sorted(decisions["requesting_body"].dropna().unique())
        body_filter = st.multiselect("Requesting body", body_options)

    search = st.text_input("Search agenda title")

    filtered = decisions[decisions["stage"].isin(stage_filter)]
    if body_filter:
        filtered = filtered[filtered["requesting_body"].isin(body_filter)]
    if search:
        filtered = filtered[filtered["agenda_title"].str.contains(search, case=False, na=False)]

    st.bar_chart(decisions["stage"].value_counts())

    st.dataframe(
        filtered[
            ["item_id", "status", "stage", "requesting_body", "meeting_date", "agenda_title",
             "followup_item_id", "followup_final_outcome"]
        ],
        use_container_width=True,
        hide_index=True,
    )

# --- Tab 2: Vote Outcomes & Engagement Priority -----------------------------
with tab2:
    if not os.path.exists(MODEL_PATH):
        st.warning("Model hasn't been trained yet.")
        if st.button("Train model now"):
            with st.spinner("Training..."):
                model = train([VR_PATH])
                os.makedirs("models", exist_ok=True)
                joblib.dump(model, MODEL_PATH)
            st.rerun()
        st.stop()

    st.caption(
        "The Voting Record only contains **recorded votes** -- most routine council business passes on a "
        "no-vote consent agenda and never shows up here at all. This view covers the contested subset of "
        "council business, not everything council has decided."
    )

    model_mtime = os.path.getmtime(MODEL_PATH)
    outcomes = load_vote_outcomes_with_predictions(model_mtime)

    priority_filter = st.select_slider("Minimum engagement priority", options=["Low", "Medium", "High"], value="Low")
    priority_rank = {"Low": 0, "Medium": 1, "High": 2}
    outcomes = outcomes.copy()
    outcomes["priority_rank"] = outcomes["engagement_priority_label"].str.split(" - ").str[0].map(priority_rank)
    shown = outcomes[outcomes["priority_rank"] >= priority_rank[priority_filter]].sort_values(
        "engagement_priority_score", ascending=False
    )

    st.dataframe(
        shown[["agenda_item_title", "committee", "motion_type", "outcome", "p_carried", "engagement_priority_label"]],
        use_container_width=True,
        hide_index=True,
    )

# --- Tab 3: Try the Model ---------------------------------------------------
with tab3:
    if not os.path.exists(MODEL_PATH):
        st.info("Train the model in the 'Vote Outcomes & Priority' tab first.")
        st.stop()

    committees, motion_types, committee_overall, motion_overall = committee_motion_lookup()
    model = get_model(os.path.getmtime(MODEL_PATH))

    st.caption(
        "Pick a hypothetical item and see what the model predicts. For an item that hasn't come to a vote "
        "yet, the motion type is usually unknown -- try 'Unknown' to see the committee-only estimate."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        committee = st.selectbox("Committee", committees)
    with c2:
        motion_type = st.selectbox("Motion type", ["Unknown"] + motion_types)
    with c3:
        term = st.selectbox("Term", [CURRENT_TERM])

    row = pd.DataFrame(
        [
            {
                "committee": committee,
                "motion_type": motion_type,
                "term": term,
                "committee_prior_carry_rate": committee_overall.get(committee, 0.5),
                "motion_type_prior_carry_rate": motion_overall.get(motion_type, 0.5),
            }
        ]
    )
    p = model.predict_proba(row[CATEGORICAL + NUMERIC])[:, 1][0]
    scored = add_engagement_priority(pd.DataFrame({"p_carried": [p]})).iloc[0]

    m1, m2 = st.columns(2)
    m1.metric("P(carried)", f"{p:.0%}")
    m2.metric("Engagement priority", f"{scored['engagement_priority_score']:.2f}")
    st.write(scored["engagement_priority_label"])
