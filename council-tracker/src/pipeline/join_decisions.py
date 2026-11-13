"""
Join the Report Request Log and Voting Record into one decisions table,
keyed on the shared item-number format (e.g. "2023.CC1.2").

This does NOT produce a 1:1 join -- that's expected:
  - A report request's `item_id` is the *original* agenda item that asked
    for a report. Its `closed_by_item_ids` points at the *follow-up* item
    where that report actually came back. The vote (if any) happens on
    the follow-up item, not the original request.
  - Most agenda items never appear in the Voting Record at all, because
    most council business passes on a consent agenda with no recorded
    vote (see load_voting_record.py). Absence of a vote != undecided.
"""
from __future__ import annotations

import pandas as pd

from src.pipeline.load_report_request_log import load_requests
from src.pipeline.load_voting_record import load_vote_events


def build_decisions_table(report_request_log_path: str, voting_record_path: str) -> pd.DataFrame:
    requests_df = load_requests(report_request_log_path)
    votes_df = load_vote_events(voting_record_path)

    # One row per agenda item for the voting side: an item can have several
    # vote events (amendments, then the main motion) -- keep the LAST
    # recorded vote as that item's effective outcome, and remember how
    # many recorded votes it took to get there (a proxy for how contested
    # it was -- useful later for the engagement-priority model).
    votes_df = votes_df.sort_values("vote_datetime")
    item_outcomes = (
        votes_df.groupby("agenda_item_id")
        .agg(
            final_outcome=("outcome", "last"),
            final_result_raw=("result_raw", "last"),
            n_recorded_votes=("outcome", "size"),
            last_vote_datetime=("vote_datetime", "last"),
            committee=("committee", "last"),
        )
        .reset_index()
    )

    # Follow-up item each request resolves to, where there is exactly one.
    requests_df = requests_df.copy()
    requests_df["followup_item_id"] = requests_df["closed_by_item_ids"].apply(
        lambda ids: ids[0] if len(ids) == 1 else None
    )
    requests_df["has_multiple_followups"] = requests_df["closed_by_item_ids"].apply(len) > 1

    merged = requests_df.merge(
        item_outcomes.rename(columns=lambda c: f"followup_{c}" if c != "agenda_item_id" else c),
        left_on="followup_item_id",
        right_on="agenda_item_id",
        how="left",
    ).drop(columns=["agenda_item_id"])

    return merged


if __name__ == "__main__":
    import sys

    rrl_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/report_request_log_2022-2026.xlsx"
    vr_path = sys.argv[2] if len(sys.argv) > 2 else "data/raw/voting_record_2022-2026.csv"

    decisions = build_decisions_table(rrl_path, vr_path)
    print(f"{len(decisions)} report requests joined")
    has_followup_vote = decisions["followup_final_outcome"].notna()
    print(f"{has_followup_vote.sum()} have a recorded vote on their follow-up item")
    print(decisions.loc[has_followup_vote, "followup_final_outcome"].value_counts())
