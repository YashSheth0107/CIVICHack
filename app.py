"""
Council Tracker dashboard.

Run with:
    streamlit run app.py

This file is the PRESENTATION layer only -- plain-language labels,
friendly formatting, layout. All real logic (loading, joining,
modeling) lives in src/ and has zero UI concerns, so nothing here
should be treated as a source of truth about the data.
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

# --- Plain-language lookups (presentation only -- the real data keeps
# its original values; these only change what's displayed) -----------------
STAGE_LABELS = {
    "requested": "Report requested",
    "report_delivered": "Report delivered, awaiting vote",
    "decided_carried": "Passed",
    "decided_not_carried": "Did not pass",
    "closed_without_item": "Closed, no vote needed",
    "ambiguous_multi_item": "Unclear outcome",
}

# The Report Request Log abbreviates which body asked for the report.
# Only the common ones are mapped with confidence -- anything else is
# shown as-is rather than guessing at a name that might be wrong.
COMMITTEE_NAMES = {
    "CC": "City Council",
    "EX": "Executive Committee",
    "PH": "Planning and Housing Committee",
    "IE": "Infrastructure and Environment Committee",
    "EC": "Economic and Community Development Committee",
    "GG": "General Government Committee",
    "AU": "Audit Committee",
    "TE": "Toronto and East York Community Council",
    "TEYCC": "Toronto and East York Community Council",
    "NY": "North York Community Council",
    "SC": "Scarborough Community Council",
    "EY": "Etobicoke York Community Council",
    "HL": "Board of Health",
    "BOH": "Board of Health",
}


def friendly_committee(code: str) -> str:
    if not isinstance(code, str):
        return code
    return COMMITTEE_NAMES.get(code.strip().upper(), code)


# Toronto's 4 Community Councils each cover one of the old pre-amalgamation
# municipalities -- a decision routed through one of them is local to that
# part of the city. Everything else (City Council itself, and the
# standing committees like Planning and Housing) is city-wide, not tied
# to one area.
def area_of(committee_code_or_name: str) -> str:
    name = friendly_committee(committee_code_or_name)
    if not isinstance(name, str):
        return "City-wide"
    name_lower = name.lower()
    for area in ["Toronto and East York", "North York", "Scarborough", "Etobicoke York"]:
        if area.lower() in name_lower:
            return area
    return "City-wide"


def download_button(df: pd.DataFrame, filename: str, key: str) -> None:
    """Download exactly what's currently shown in the table above it."""
    st.download_button(
        "Download this table as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


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


# --- Header ------------------------------------------------------------
st.title("Council Tracker")
st.markdown("##### See what's happening at Toronto City Hall — and when your voice matters most.")

with st.expander("How to use this page"):
    st.markdown(
        """
Toronto City Council handles thousands of decisions. This page turns two of the City's own public
records into something easier to follow:

- **Browse Decisions** — every report Council or a committee has asked for, and where it stands
  right now: still waiting, delivered, passed, or didn't pass.
- **Where Your Voice Matters** — of the votes that were actually contested (not just rubber-stamped),
  which ones were genuinely close. A close vote is where showing up or writing in is most likely to
  make a difference — a landslide, in either direction, usually isn't.
- **Explore the Model** *(optional, for the curious)* — a hands-on way to see how the prediction
  behind the "close vote" signal actually works.
        """
    )

if not _data_ready():
    # Auto-bootstrap rather than requiring a click -- on a host with an
    # ephemeral filesystem (e.g. Streamlit Community Cloud), every cold
    # start/wake-from-sleep starts with no data on disk, and a visitor
    # opening the link shouldn't have to click a button before seeing
    # anything.
    #
    # Guarded by a retry counter: if fetch_datasets() "succeeds" (no
    # exception) but the files still aren't on disk afterward -- e.g. a
    # host where the working directory isn't what we expect, or a
    # network/permissions quirk that doesn't raise -- this would
    # otherwise retry -> rerun -> retry forever, showing as an endless
    # spinner with no error rather than failing loudly.
    attempts = st.session_state.get("_data_bootstrap_attempts", 0)
    if attempts >= 2:
        st.error(
            f"Could not prepare the data after {attempts} attempts. "
            f"Expected files at '{RRL_PATH}' and '{VR_PATH}' (cwd: {os.getcwd()}) but they're not there. "
            "Check the app logs for the real error."
        )
        st.stop()

    st.session_state["_data_bootstrap_attempts"] = attempts + 1
    with st.spinner(f"Setting things up for the first time... (attempt {attempts + 1})"):
        fetch_datasets()

    if not _data_ready():
        st.error(f"Download ran without error, but the expected files are still missing (cwd: {os.getcwd()}).")
        st.stop()

    st.session_state["_data_bootstrap_attempts"] = 0
    st.cache_data.clear()
    st.rerun()

decisions = load_decisions()

# --- At-a-glance summary -------------------------------------------------
counts = decisions["stage"].value_counts()
pending = counts.get("requested", 0) + counts.get("report_delivered", 0)
passed = counts.get("decided_carried", 0)
failed = counts.get("decided_not_carried", 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total report requests", f"{len(decisions):,}")
c2.metric("Still pending", f"{pending:,}")
c3.metric("Passed", f"{passed:,}")
c4.metric("Did not pass", f"{failed:,}")

st.divider()

tab1, tab2, tab3 = st.tabs(["Browse Decisions", "Where Your Voice Matters", "Explore the Model"])

# --- Tab 1: Decision Lifecycle Tracker -------------------------------------
with tab1:
    st.markdown(
        "Every report Council or a committee has ever requested, and where it stands right now. "
        "Use the filters to find something specific."
    )

    label_to_stage = {v: k for k, v in STAGE_LABELS.items()}
    stage_label_options = [STAGE_LABELS[s] for s in decisions["stage"].unique()]

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_labels = st.multiselect("What's happening", stage_label_options, default=stage_label_options)
    with col2:
        area_options = ["All of Toronto", "City-wide", "Toronto and East York", "North York", "Scarborough", "Etobicoke York"]
        area_filter = st.selectbox("Part of the city", area_options)
    with col3:
        committee_display = sorted(decisions["requesting_body"].dropna().apply(friendly_committee).unique())
        body_filter = st.multiselect("Requested by (specific committee)", committee_display)

    search = st.text_input("Search by title", placeholder="e.g. housing, bike lanes, budget...")

    selected_stages = [label_to_stage[s] for s in selected_labels]
    filtered = decisions[decisions["stage"].isin(selected_stages)].copy()
    if area_filter != "All of Toronto":
        filtered = filtered[filtered["requesting_body"].apply(area_of) == area_filter]
    if body_filter:
        matching_codes = [c for c in decisions["requesting_body"].dropna().unique() if friendly_committee(c) in body_filter]
        filtered = filtered[filtered["requesting_body"].isin(matching_codes)]
    if search:
        filtered = filtered[filtered["agenda_title"].str.contains(search, case=False, na=False)]

    chart_data = decisions["stage"].map(STAGE_LABELS).value_counts()
    st.bar_chart(chart_data)

    filtered["What's happening"] = filtered["stage"].map(STAGE_LABELS)
    filtered["Area"] = filtered["requesting_body"].apply(area_of)
    filtered["Requested by"] = filtered["requesting_body"].apply(friendly_committee)
    display_cols = {
        "item_id": "Item #",
        "agenda_title": "Title",
        "Area": "Area",
        "Requested by": "Requested by",
        "meeting_date": "Date requested",
        "What's happening": "What's happening",
    }
    show_technical = st.checkbox("Show technical details (item numbers, follow-up links)")
    if show_technical:
        display_cols = {
            **display_cols,
            "followup_item_id": "Follow-up item",
            "followup_final_outcome": "Follow-up result",
            "status": "Raw status code",
        }

    shown = filtered.rename(columns=display_cols)[list(display_cols.values())]
    st.caption(f"Showing {len(shown):,} of {len(decisions):,} report requests")
    st.dataframe(
        shown,
        use_container_width=True,
        hide_index=True,
        column_config={"Date requested": st.column_config.DateColumn("Date requested", format="MMM D, YYYY")},
    )
    download_button(shown, "council_decisions.csv", key="download_tab1")

# --- Tab 2: Vote Outcomes & Engagement Priority -----------------------------
with tab2:
    if not os.path.exists(MODEL_PATH):
        # Same auto-bootstrap reasoning, and same retry guard, as the
        # data download above.
        attempts = st.session_state.get("_model_bootstrap_attempts", 0)
        if attempts >= 2:
            st.error(f"Could not train the model after {attempts} attempts. Check the app logs for the real error.")
            st.stop()

        st.session_state["_model_bootstrap_attempts"] = attempts + 1
        with st.spinner(f"Setting things up for the first time... (attempt {attempts + 1})"):
            model = train([VR_PATH])
            os.makedirs("models", exist_ok=True)
            joblib.dump(model, MODEL_PATH)

        if not os.path.exists(MODEL_PATH):
            st.error("Training ran without error, but the model file still wasn't saved.")
            st.stop()

        st.session_state["_model_bootstrap_attempts"] = 0
        st.rerun()

    st.markdown(
        "These are council votes that were actually **contested** — not unanimous, not rubber-stamped. "
        "They're sorted by how close the vote was: the closer the vote, the more a resident's voice "
        "could realistically have tipped it."
    )
    with st.expander("Why don't I see everything Council has voted on?"):
        st.markdown(
            "Most routine council business passes with no recorded vote at all (a quiet \"consent agenda\"), "
            "so it never shows up here — its absence just means it wasn't contested, not that it's undecided. "
            "This tab only covers the subset of business that actually came to a recorded vote."
        )

    model_mtime = os.path.getmtime(MODEL_PATH)
    outcomes = load_vote_outcomes_with_predictions(model_mtime)

    col1, col2 = st.columns(2)
    with col1:
        priority_choice = st.radio(
            "Show me:",
            ["Close calls only", "Close calls + leaning either way", "Everything (incl. landslides)"],
            horizontal=True,
        )
    with col2:
        area_options_2 = ["All of Toronto", "City-wide", "Toronto and East York", "North York", "Scarborough", "Etobicoke York"]
        area_filter_2 = st.selectbox("Part of the city", area_options_2, key="area_tab2")

    min_rank = {"Close calls only": 2, "Close calls + leaning either way": 1, "Everything (incl. landslides)": 0}[priority_choice]
    priority_rank = {"Low": 0, "Medium": 1, "High": 2}

    outcomes = outcomes.copy()
    outcomes["priority_rank"] = outcomes["engagement_priority_label"].str.split(" - ").str[0].map(priority_rank)
    shown = outcomes[outcomes["priority_rank"] >= min_rank].sort_values("engagement_priority_score", ascending=False)
    if area_filter_2 != "All of Toronto":
        shown = shown[shown["committee"].apply(area_of) == area_filter_2]

    shown["Area"] = shown["committee"].apply(area_of)
    shown["Committee"] = shown["committee"].apply(friendly_committee)
    shown["What happened"] = shown["outcome"].map({"carried": "Passed", "not_carried": "Did not pass"})
    # ProgressColumn's `format` is a plain printf string applied to the raw
    # cell value -- it does NOT multiply by 100 for you. Left as a 0-1
    # fraction, "%.0f%%" on 0.95 just rounds 0.95 to the nearest whole
    # number and prints "1%", not "95%" (confirmed against Streamlit's own
    # docs). Scaling to 0-100 here, with min/max updated to match below,
    # is what actually fixes the displayed number.
    shown["p_carried"] = (shown["p_carried"] * 100).round(1)

    tab2_display = shown.rename(
        columns={
            "agenda_item_title": "What was voted on",
            "motion_type": "Type of motion",
            "p_carried": "Predicted chance of passing",
            "engagement_priority_label": "Priority",
        }
    )[["What was voted on", "Area", "Committee", "Type of motion", "What happened", "Predicted chance of passing", "Priority"]]

    st.caption(f"Showing {len(shown):,} of {len(outcomes):,} contested votes")
    st.dataframe(
        tab2_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Predicted chance of passing": st.column_config.ProgressColumn(
                "Predicted chance of passing", format="%.0f%%", min_value=0, max_value=100
            )
        },
    )
    download_button(tab2_display, "council_vote_priorities.csv", key="download_tab2")

# --- Tab 3: Explore the Model ------------------------------------------
with tab3:
    if not os.path.exists(MODEL_PATH):
        st.info("This fills in automatically once the previous tab has set up the model.")
        st.stop()

    committees, motion_types, committee_overall, motion_overall = committee_motion_lookup()
    model = get_model(os.path.getmtime(MODEL_PATH))

    st.markdown(
        "Curious how the \"close call\" prediction actually works? Pick a committee and a type of motion "
        "below and see what the model estimates — this is the same model behind the previous tab, just "
        "with knobs you can turn yourself."
    )
    st.caption(f"Based on recorded votes from the current council term ({CURRENT_TERM}).")

    c1, c2 = st.columns(2)
    with c1:
        committee = st.selectbox("Committee", committees)
    with c2:
        motion_type = st.selectbox(
            "Type of motion",
            ["Don't know yet"] + motion_types,
            help="For a report that hasn't come to a vote yet, this usually isn't known -- "
            "'Don't know yet' shows the estimate based on the committee alone.",
        )
    motion_key = "Unknown" if motion_type == "Don't know yet" else motion_type

    row = pd.DataFrame(
        [
            {
                "committee": committee,
                "motion_type": motion_key,
                "term": CURRENT_TERM,
                "committee_prior_carry_rate": committee_overall.get(committee, 0.5),
                "motion_type_prior_carry_rate": motion_overall.get(motion_key, 0.5),
            }
        ]
    )
    p = model.predict_proba(row[CATEGORICAL + NUMERIC])[:, 1][0]
    scored = add_engagement_priority(pd.DataFrame({"p_carried": [p]})).iloc[0]

    priority_word = scored["engagement_priority_label"].split(" - ")[0]

    m1, m2 = st.columns(2)
    m1.metric("Predicted chance it passes", f"{p:.0%}")
    m2.metric("Priority to weigh in", priority_word)
    st.write(scored["engagement_priority_label"])

st.divider()
st.caption(
    "Data: City of Toronto Report Request Log and Council Voting Record, "
    "under the Open Government Licence - Toronto."
)
