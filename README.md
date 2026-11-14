# Council Tracker

**🔗 Live app: [council-tracker.streamlit.app](https://council-tracker.streamlit.app/)**

**📄 Municipal Readiness Report: [Google Drive](https://drive.google.com/file/d/1q6HS9bPb2pJd94zckKVveEuaBQ3RvDoV/view?usp=drive_link)**

[![Tests](https://github.com/YashSheth0107/CIVICHack/actions/workflows/tests.yml/badge.svg)](https://github.com/YashSheth0107/CIVICHack/actions/workflows/tests.yml)

**Challenge**: How might we help residents understand a proposed municipal decision, how it could affect them, and when they can have a say?

Council Tracker answers this with two combined pieces, built on City of Toronto Open Data:

1. **Decision Lifecycle Tracker** — traces a municipal decision from the moment a report is requested, through the report coming back, to the council vote that settles it, and tags its current stage.
2. **Outcome Predictor + Engagement Priority Score** — for decisions headed to a recorded vote, predicts how likely it is to pass and surfaces that as a priority signal: close calls rank higher than landslides, because that's when a resident's voice matters most.

## Data sources
Both published by the City of Toronto under the [Open Government Licence - Toronto](https://open.toronto.ca/open-data-license/):
- [Report Request Log](https://open.toronto.ca/dataset/report-request-log/) — tracks staff report requests made by Council and its committees.
- [Members of Toronto City Council - Voting Record](https://open.toronto.ca/dataset/members-of-toronto-city-council-voting-record/) — recorded votes at Council and committee meetings.

Full column-by-column notes (including a couple of surprising quirks in the raw files) are in [docs/data_dictionary.md](docs/data_dictionary.md) — worth reading before touching the loaders. For a full walkthrough of how every module connects, including a real worked example traced end-to-end, see [docs/architecture.md](docs/architecture.md).

## Architecture

```
Report Request Log (XLSX)  ──┐
                              ├──> join on item number ──> stage classification ──> decisions table
Voting Record (CSV)        ──┘                                                            │
                              │                                                           │
                              └──> vote events ──> feature engineering ──> outcome model ──> engagement priority
```

| Stage | Module |
|---|---|
| Download raw files | `src/ingest/toronto_open_data.py`, `src/ingest/fetch_datasets.py` |
| Clean/parse each dataset | `src/pipeline/load_report_request_log.py`, `src/pipeline/load_voting_record.py` |
| Join + lifecycle stage | `src/pipeline/join_decisions.py`, `src/pipeline/stage.py` |
| Outcome model | `src/model/features.py`, `src/model/train_outcome_model.py` |
| Engagement priority | `src/model/engagement_score.py`, `src/model/predict.py` |

## Setup

```bash
pip install -r requirements.txt
python -m src.ingest.fetch_datasets        # downloads into data/raw/
python -m src.pipeline.stage                # lifecycle stage for every report request
python -m src.model.train_outcome_model data/raw/voting_record_2022-2026.csv
python -m src.model.predict                  # demo: predicted P(carried) + priority label
```

Every module above also runs standalone with `python -m <module>` and prints a sanity-check summary — useful for confirming a change didn't break anything without wiring up the full pipeline.

## Dashboard

Hosted version: **https://council-tracker.streamlit.app/** — or run it locally:

```bash
streamlit run app.py
```

Three tabs, all reading live off the pipeline/model code above (no separate API or database):
- **Decision Lifecycle** — filterable/searchable table of every report request and its current stage.
- **Vote Outcomes & Priority** — recorded votes ranked by engagement priority (close calls first), with the model's predicted probability next to the real outcome.
- **Try the Model** — pick a committee/motion type/term and see the predicted P(carried) and priority score live.

If `data/raw/` or `models/outcome_model.joblib` are missing, the dashboard auto-downloads/auto-trains on first run rather than requiring a manual step (useful on a host with an ephemeral filesystem, e.g. Streamlit Community Cloud).

**Deploying**: `runtime.txt` pins Python 3.12 — pandas 2.2.2 (and some other pinned deps) have no prebuilt wheel for newer Pythons like 3.14, which forces a from-source build that fails on a newer compiler. If a host ignores `runtime.txt`, set the Python version explicitly in its settings instead.

## What's real vs. what's next

**Working now**, verified against live data (not stubbed):
- Downloads the current-term XLSX/CSV directly from Toronto's CKAN API.
- Parses every one of the 252 distinct `Result` value formats in the Voting Record.
- Joins 2,065 report requests to their follow-up vote outcomes (207 currently resolve to a recorded vote).
- Classifies every request into one of 6 lifecycle stages (`requested`, `report_delivered`, `decided_carried`, `decided_not_carried`, `closed_without_item`, `ambiguous_multi_item`).
- Trains a real outcome model (logistic regression, time-split train/test, AUC ≈ 0.81 on the current term) and converts its probability into a close-call-first engagement priority score.

**Deliberately left as roadmap** (see `docs/data_dictionary.md` → "Known gaps"):
- Plain-language summarization of the `directive` text.
- A pre-filter for "will this item even get a recorded vote" — most council business doesn't, and the current model only applies to the contested subset.
- Deputation deadline / next-meeting-date extraction from agenda data (needs a third dataset not yet wired in).
- Ward/geography mapping (needs a councillor-to-ward lookup; geocoding free text item titles is explicitly out of scope for now).

## Known data quirks worth knowing before extending this
- The Voting Record only contains **recorded votes** — most routine business passes on a no-vote consent agenda and never appears there at all. Absence ≠ undecided.
- The Report Request Log's `Status` field is `NCF`/`closed` (three different casings), not `Open`/`Closed` as you'd guess.
- Its `Closed by` field is overloaded: sometimes a date, sometimes one-or-more follow-up item numbers.
