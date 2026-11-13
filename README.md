# Council Tracker

**Challenge**: How might we help residents understand a proposed municipal decision, how it could affect them, and when they can have a say?

Council Tracker answers this with two combined pieces, built on City of Toronto Open Data:

1. **Decision Lifecycle Tracker** — traces a municipal decision from the moment a report is requested, through the report coming back, to the council vote that settles it, and tags its current stage.
2. **Outcome Predictor + Engagement Priority Score** — for decisions headed to a recorded vote, predicts how likely it is to pass and surfaces that as a priority signal: close calls rank higher than landslides, because that's when a resident's voice matters most.

## Data sources
Both published by the City of Toronto under the [Open Government Licence - Toronto](https://open.toronto.ca/open-data-license/):
- [Report Request Log](https://open.toronto.ca/dataset/report-request-log/) — tracks staff report requests made by Council and its committees.
- [Members of Toronto City Council - Voting Record](https://open.toronto.ca/dataset/members-of-toronto-city-council-voting-record/) — recorded votes at Council and committee meetings.

Full column-by-column notes (including a couple of surprising quirks in the raw files) are in [docs/data_dictionary.md](docs/data_dictionary.md) — worth reading before touching the loaders.

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

## What's real vs. what's next

**Working now**, verified against live data (not stubbed):
- Downloads the current-term XLSX/CSV directly from Toronto's CKAN API.
- Parses every one of the 252 distinct `Result` value formats in the Voting Record.
- Joins 2,065 report requests to their follow-up vote outcomes (207 currently resolve to a recorded vote).
- Classifies every request into one of 6 lifecycle stages (`requested`, `report_delivered`, `decided_carried`, `decided_not_carried`, `closed_without_item`, `ambiguous_multi_item`).
- Trains a real outcome model (logistic regression, time-split train/test, AUC ≈ 0.80 on the current term) and converts its probability into a close-call-first engagement priority score.

**Deliberately left as roadmap** (see `docs/data_dictionary.md` → "Known gaps"):
- Plain-language summarization of the `directive` text.
- A pre-filter for "will this item even get a recorded vote" — most council business doesn't, and the current model only applies to the contested subset.
- Deputation deadline / next-meeting-date extraction from agenda data (needs a third dataset not yet wired in).
- Ward/geography mapping (needs a councillor-to-ward lookup; geocoding free text item titles is explicitly out of scope for now).

## Known data quirks worth knowing before you extend this
- The Voting Record only contains **recorded votes** — most routine business passes on a no-vote consent agenda and never appears there at all. Absence ≠ undecided.
- The Report Request Log's `Status` field is `NCF`/`closed` (three different casings), not `Open`/`Closed` as you'd guess.
- Its `Closed by` field is overloaded: sometimes a date, sometimes one-or-more follow-up item numbers.
