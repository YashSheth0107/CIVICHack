"""
Load and clean the Council Voting Record CSV.

Real schema (verified against member-voting-record-2022-2026.csv):
    _id, Term, First Name, Last Name, Committee, Date/Time,
    Agenda Item #, Agenda Item Title, Motion Type, Vote, Result,
    Vote Description

IMPORTANT CAVEAT (from the dataset's own notes): "Votes generated in
the report are recorded votes only." Most routine council business
passes on a consent agenda with NO recorded vote and therefore never
appears here at all. Treat this dataset as "the contested subset of
council business", not the full universe of decisions -- that full
universe comes from the Report Request Log / agenda items instead.
See src/pipeline/stage.py for how the two datasets combine.

One row in the raw CSV = one councillor's vote on one motion. This
module collapses that to one row per *vote event* (every councillor
who voted on the same item/motion/timestamp shares one outcome).
"""
from __future__ import annotations

import re

import pandas as pd

# Matches every Result value observed in the 2022-2026 term file, e.g.
#   "Carried, 25-1"   "Not Carried, 10-15"   "Lost (tie), 11-11"   "Carried"
_RESULT_RE = re.compile(
    r"^(?P<verdict>Carried|Not Carried|Lost)\s*(?P<tie>\(tie\))?\s*(?:,\s*(?P<yes>\d+)-(?P<no>\d+))?$",
    re.IGNORECASE,
)


def parse_result(result_raw: str) -> dict:
    """Parse a Result string into a structured outcome.

    Returns dict with: outcome ('carried'/'not_carried'), is_tie (bool),
    yes_count, no_count (ints or None if not reported).
    """
    if not isinstance(result_raw, str):
        return {"outcome": None, "is_tie": False, "yes_count": None, "no_count": None}

    m = _RESULT_RE.match(result_raw.strip())
    if not m:
        # Unseen format -- fail loud rather than silently mislabel a vote.
        raise ValueError(f"Unrecognized Result format: {result_raw!r}")

    verdict = m.group("verdict").lower()
    outcome = "carried" if verdict == "carried" else "not_carried"
    yes = int(m.group("yes")) if m.group("yes") else None
    no = int(m.group("no")) if m.group("no") else None
    return {
        "outcome": outcome,
        "is_tie": bool(m.group("tie")),
        "yes_count": yes,
        "no_count": no,
    }


def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    # Source data mixes a few datetime string shapes (e.g. "15:17 PM" --
    # a 24h hour with a 12h suffix), so let pandas infer per-row.
    df["Date/Time"] = pd.to_datetime(df["Date/Time"], errors="coerce", format="mixed")
    return df


def load_vote_events(path: str) -> pd.DataFrame:
    """Collapse per-councillor rows into one row per recorded vote event.

    A vote event is uniquely identified by (Agenda Item #, Committee,
    Date/Time, Motion Type, Vote Description) -- the same item can have
    multiple recorded votes (e.g. an amendment, then the main motion).
    """
    df = load_raw(path)

    # Result is identical for every councillor's row within one vote event,
    # so it's safe (and avoids pandas groupby/apply group-column pitfalls)
    # to parse it per-row before grouping, then just take the first value.
    parsed = df["Result"].apply(parse_result).apply(pd.Series)
    df = pd.concat([df, parsed], axis=1)

    vote_lower = df["Vote"].str.lower()
    df["_is_yes"] = vote_lower == "yes"
    df["_is_no"] = vote_lower == "no"
    df["_is_absent"] = vote_lower.str.startswith("absent")

    group_keys = ["Agenda Item #", "Agenda Item Title", "Committee", "Date/Time", "Motion Type", "Result", "Vote Description", "Term"]
    events = (
        df.groupby(group_keys, dropna=False)
        .agg(
            n_yes_recorded=("_is_yes", "sum"),
            n_no_recorded=("_is_no", "sum"),
            n_absent_recorded=("_is_absent", "sum"),
            outcome=("outcome", "first"),
            is_tie=("is_tie", "first"),
            yes_count=("yes_count", "first"),
            no_count=("no_count", "first"),
        )
        .reset_index()
    )
    events = events.rename(
        columns={
            "Agenda Item #": "agenda_item_id",
            "Agenda Item Title": "agenda_item_title",
            "Committee": "committee",
            "Date/Time": "vote_datetime",
            "Motion Type": "motion_type",
            "Result": "result_raw",
            "Vote Description": "vote_description",
            "Term": "term",
        }
    )
    return events.sort_values("vote_datetime").reset_index(drop=True)


if __name__ == "__main__":
    import sys

    events = load_vote_events(sys.argv[1] if len(sys.argv) > 1 else "data/raw/voting_record_2022-2026.csv")
    print(f"{len(events)} vote events across {events['agenda_item_id'].nunique()} agenda items")
    print(events["outcome"].value_counts())
