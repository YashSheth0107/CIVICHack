# Data dictionary

Verified against the live City of Toronto Open Data CKAN API on 2026-11-12.
Both datasets are published under the [Open Government Licence - Toronto](https://open.toronto.ca/open-data-license/)
— attribution to the City of Toronto is required in anything built from them.

## Report Request Log
- Portal page: https://open.toronto.ca/dataset/report-request-log/
- CKAN package slug: `report-request-log-city-council-and-its-committees`
- Format: **XLSX** (+ a PDF of the same content, not used here)
- Two files, one per council term: `reportrequestlog2018-2022.xlsx`, `reportrequestlog2022-2026.xlsx`
- 2,065 rows in the current (2022-2026) term file

| Column (raw)     | Loaded as             | Notes |
|---|---|---|
| `Status`         | `status`, `is_open`   | **Not** a clean Open/Closed pair. Real values: `NCF` (~66% of rows — the pending/not-yet-reported-back state) and `closed`/`Closed`/`CLOSED` (three casings). `is_open` = anything not a "closed" variant. |
| `Req.\nBody`     | `requesting_body`     | e.g. `CC`, `PH`, `TE` — which council body asked for the report. |
| `Meeting \nDate` | `meeting_date`        | Date the request was made. |
| `Item Number`    | `item_id`              | **Join key.** e.g. `2023.CC1.2` — same format as Voting Record's `Agenda Item #`. |
| `Agenda title`   | `agenda_title`         | |
| `Directive`      | `directive`           | Full text of what was requested — the raw material for a plain-language summarizer later. |
| `Rpt \nto:`      | `report_to`           | Committee the report is due back to. |
| `Report Back Timing` | `report_back_timing` | Free text, e.g. "Not indicated", or a date. |
| `Assigned to`    | `assigned_to`          | Staff role assigned. |
| `Closed \nby`    | split into `closed_by_date`, `closed_by_item_ids` | **Trap field.** Despite the name, holds EITHER a date OR one-or-more follow-up item numbers (sometimes several, separated by newlines/spaces). We split these apart — see `src/pipeline/load_report_request_log.py`. |
| `Date for Order` | `date_for_order`       | |

## Members of Toronto City Council - Voting Record
- Portal page: https://open.toronto.ca/dataset/members-of-toronto-city-council-voting-record/
- CKAN package slug: `members-of-toronto-city-council-voting-record`
- Format: CSV (also XML/JSON/TXT; CSV used here)
- One file per council term, back to 2006: `member-voting-record-2006-2010.csv` ... `-2022-2026.csv`
- 46,815 rows (one per councillor per vote) in the current term file

**Critical caveat, from the dataset's own description**: *"Votes generated in the report are recorded votes only."* Most routine council business passes on a no-vote consent agenda and never appears in this dataset at all. Absence from this file does **not** mean an item is undecided — it usually means it was uncontested. Any "will this pass" model trained on this data is implicitly scoped to *contested* business only.

| Column (raw)        | Loaded as          | Notes |
|---|---|---|
| `Term`               | `term`             | e.g. `2022-2026` |
| `First Name`/`Last Name` | (kept in raw loader, dropped by `load_vote_events`) | Per-councillor — collapsed when we aggregate to one row per vote event. |
| `Committee`          | `committee`        | 1,717/2,181 (79%) of current-term vote events are `City Council` itself, not a sub-committee. |
| `Date/Time`          | `vote_datetime`    | Mixed string formats in the source (parsed with `format="mixed"`). |
| `Agenda Item #`      | `agenda_item_id`   | **Join key** — same format as Report Request Log's `Item Number`. |
| `Agenda Item Title`  | `agenda_item_title`| |
| `Motion Type`        | `motion_type`      | e.g. `Adopt Item`, `Amend Item`, `Defer Item` — a strong predictor of outcome. |
| `Vote`               | collapsed into `n_yes_recorded`/`n_no_recorded`/`n_absent_recorded` | Per-councillor Yes/No/Absent(+variants). |
| `Result`             | parsed into `outcome` (`carried`/`not_carried`), `is_tie`, `yes_count`, `no_count` | Format validated against **all 252** distinct values in the current-term file — see the regex in `load_voting_record.py`. |
| `Vote Description`   | `vote_description` | Free text, sometimes names the mover/seconder. |

## Known gaps / things a future pass should fix
- **Report Request Log only goes back to the 2018-2022 term** (started 2019) — the Voting Record goes back to 2006. Historical model training can use all 5 terms of voting data; the lifecycle tracker is limited to the 2 terms that have a Report Request Log.
- **`closed_by_item_ids` with more than one entry** (54 of 2,065 current-term rows) can't be resolved to a single follow-up vote automatically — flagged as `ambiguous_multi_item` in `stage.py` rather than guessed.
- **No ward/geography field in either dataset.** Mapping decisions to "does this affect my ward" (the original idea #3) needs a third source — Councillor-to-ward lookup is straightforward; geocoding free-text item titles/directives is not, and is intentionally out of scope for this pass.
