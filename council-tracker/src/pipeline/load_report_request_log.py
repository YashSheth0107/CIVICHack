"""
Load and clean the Report Request Log XLSX.

Real schema (verified against reportrequestlog2022-2026.xlsx, sheet 0):
    Status, Req.\\nBody, Meeting \\nDate, Item Number, Agenda title,
    Directive, Rpt \\nto:, Report Back Timing, Assigned to, Closed \\nby,
    Date for Order, Unnamed: 11 (empty, dropped)

Notes on the two trickiest fields:
  - `Status`: NOT a clean 'Open'/'Closed' pair. The real values are
    'NCF' (~66% of rows -- the pending/not-yet-reported-back state;
    sources vary on the literal expansion, but functionally it's the
    "still open" status) and 'closed' in three different casings
    ('closed', 'Closed', 'CLOSED'). We normalize case and treat
    anything that isn't a "closed" variant as open. This is the
    cheapest signal for the lifecycle "stage" in src/pipeline/stage.py
    -- a report that's still open hasn't come back to council yet.
  - `Closed by`: despite the name, this is NOT reliably a date. It holds
    EITHER the date the request was closed OR the item number(s) of the
    follow-up report that closed it (sometimes several, newline- or
    space-separated, e.g. "2023.EX3.1 \\n2023.PH4.7\\n2023.PH5.5"). We
    split it into closed_by_date and closed_by_item_ids so downstream
    code doesn't have to guess which one it's looking at.

`Item Number` (e.g. "2023.CC1.2") uses the same format as `Agenda Item #`
in the Voting Record, which is the join key used in join_decisions.py.
"""
from __future__ import annotations

import re

import pandas as pd

_ITEM_ID_RE = re.compile(r"\b\d{4}\.[A-Z]{2,4}\d+\.\d+\b")

_COLUMN_MAP = {
    "Status": "status",
    "Req.\nBody": "requesting_body",
    "Meeting \nDate": "meeting_date",
    "Item Number": "item_id",
    "Agenda title": "agenda_title",
    "Directive": "directive",
    "Rpt \nto:": "report_to",
    "Report Back Timing": "report_back_timing",
    "Assigned to": "assigned_to",
    "Closed \nby": "closed_by_raw",
    "Date for Order": "date_for_order",
}


def _split_closed_by(value) -> tuple[pd.Timestamp | None, list[str]]:
    """closed_by_raw is either a date or one-or-more item numbers."""
    if not isinstance(value, str):
        # Already a real date (pandas may have parsed it on read).
        ts = pd.to_datetime(value, errors="coerce")
        return (ts if pd.notna(ts) else None), []

    item_ids = _ITEM_ID_RE.findall(value)
    if item_ids:
        return None, item_ids

    ts = pd.to_datetime(value, errors="coerce")
    return (ts if pd.notna(ts) else None), []


def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0)
    df = df.rename(columns=_COLUMN_MAP)
    df = df[[c for c in _COLUMN_MAP.values() if c in df.columns]]
    return df


def load_requests(path: str) -> pd.DataFrame:
    df = load_raw(path)

    df["meeting_date"] = pd.to_datetime(df["meeting_date"], errors="coerce")
    df["date_for_order"] = pd.to_datetime(df["date_for_order"], errors="coerce")

    split = df["closed_by_raw"].apply(_split_closed_by)
    df["closed_by_date"] = split.apply(lambda t: t[0])
    df["closed_by_item_ids"] = split.apply(lambda t: t[1])

    df["status"] = df["status"].str.strip()
    df["is_open"] = ~df["status"].str.lower().eq("closed")
    return df.drop(columns=["closed_by_raw"])


if __name__ == "__main__":
    import sys

    requests_df = load_requests(sys.argv[1] if len(sys.argv) > 1 else "data/raw/report_request_log_2022-2026.xlsx")
    print(f"{len(requests_df)} report requests")
    print(requests_df["status"].value_counts())
    print(f"is_open: {requests_df['is_open'].sum()} open / {(~requests_df['is_open']).sum()} closed")
    print(f"{requests_df['closed_by_item_ids'].apply(len).gt(0).sum()} requests closed by a follow-up item number")
