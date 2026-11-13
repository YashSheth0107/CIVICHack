"""
Classify each report request's current lifecycle stage. Rule-based on
purpose: the fields needed are already structured, so there's no need
for NLP here (keep that budget for topic tagging / summarization later).

Stages, in order of progress:
  requested            -- status is open (NCF); no follow-up report yet.
  report_delivered      -- closed, and points at a follow-up item, but
                            that item has no recorded vote (either it
                            passed on a no-vote consent agenda, or
                            hasn't reached council yet -- can't fully
                            tell apart without agenda/minutes data).
  decided_carried       -- follow-up item has a recorded vote, carried.
  decided_not_carried    -- follow-up item has a recorded vote, failed.
  closed_without_item    -- closed, but Closed-by was a date, not a new
                            item number (e.g. withdrawn, superseded,
                            answered outside the agenda process).
  ambiguous_multi_item   -- closed by more than one follow-up item
                            number; needs a human (or a smarter rule) to
                            pick the one that actually settled it.
"""
from __future__ import annotations

import pandas as pd

from src.pipeline.join_decisions import build_decisions_table


def classify_stage(row: pd.Series) -> str:
    if row["has_multiple_followups"]:
        return "ambiguous_multi_item"
    if row["is_open"]:
        return "requested"
    if row["followup_item_id"] is None:
        return "closed_without_item"
    outcome = row.get("followup_final_outcome")
    if pd.isna(outcome):
        return "report_delivered"
    return "decided_carried" if outcome == "carried" else "decided_not_carried"


def add_stage(decisions: pd.DataFrame) -> pd.DataFrame:
    decisions = decisions.copy()
    decisions["stage"] = decisions.apply(classify_stage, axis=1)
    return decisions


if __name__ == "__main__":
    import sys

    rrl_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/report_request_log_2022-2026.xlsx"
    vr_path = sys.argv[2] if len(sys.argv) > 2 else "data/raw/voting_record_2022-2026.csv"

    decisions = add_stage(build_decisions_table(rrl_path, vr_path))
    print(decisions["stage"].value_counts())
