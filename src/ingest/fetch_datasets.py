"""
Download the current-term Report Request Log and Council Voting Record
into data/raw/.

Usage:
    python -m src.ingest.fetch_datasets
"""
from __future__ import annotations

import os
import sys

# Allow running as `python -m src.ingest.fetch_datasets` from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import CURRENT_TERM, RAW_DATA_DIR, REPORT_REQUEST_LOG_PACKAGE, VOTING_RECORD_PACKAGE
from src.ingest.toronto_open_data import download_resource, find_resource


def main() -> None:
    # Report Request Log ships as XLSX (+ a PDF we don't need).
    rrl_resource = find_resource(REPORT_REQUEST_LOG_PACKAGE, name_contains=f"reportrequestlog{CURRENT_TERM}.xlsx")
    rrl_path = download_resource(rrl_resource, f"{RAW_DATA_DIR}/report_request_log_{CURRENT_TERM}.xlsx")
    print(f"Saved Report Request Log -> {rrl_path}")

    # Voting Record ships one CSV per council term.
    vr_resource = find_resource(VOTING_RECORD_PACKAGE, name_contains=f"member-voting-record-{CURRENT_TERM}.csv")
    vr_path = download_resource(vr_resource, f"{RAW_DATA_DIR}/voting_record_{CURRENT_TERM}.csv")
    print(f"Saved Voting Record -> {vr_path}")


if __name__ == "__main__":
    main()
