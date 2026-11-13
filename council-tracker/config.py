"""
Central config: dataset identifiers for the City of Toronto Open Data
CKAN portal. Verified live against the API on 2026-11-12 — see
docs/data_dictionary.md for the full resource listing and column notes.
"""

CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca"

# https://open.toronto.ca/dataset/report-request-log/
REPORT_REQUEST_LOG_PACKAGE = "report-request-log-city-council-and-its-committees"

# https://open.toronto.ca/dataset/members-of-toronto-city-council-voting-record/
VOTING_RECORD_PACKAGE = "members-of-toronto-city-council-voting-record"

# Only the current council term matters for a "what's happening now" tracker.
# Both datasets publish one file per term; bump these if the term rolls over.
CURRENT_TERM = "2022-2026"

RAW_DATA_DIR = "data/raw"
INTERIM_DATA_DIR = "data/interim"
PROCESSED_DATA_DIR = "data/processed"
