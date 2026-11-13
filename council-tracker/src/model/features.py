"""
Feature engineering for the outcome predictor (idea #5).

Only uses information available BEFORE a vote happens:
  - committee, motion_type, term (known the moment the item is scheduled)
  - each committee's / motion type's historical carry rate, computed on
    an *expanding, shifted* window so a given vote never sees its own
    outcome or any future outcome (no leakage).

Deliberately excludes n_recorded_votes / yes_count / no_count / margin --
those are only known AFTER the vote, so they're outcome leakage, not
predictors. They're still useful for descriptive analysis, just not here.
"""
from __future__ import annotations

import pandas as pd

FEATURE_COLUMNS = ["committee", "motion_type", "term", "committee_prior_carry_rate", "motion_type_prior_carry_rate"]
TARGET_COLUMN = "target"


def build_feature_table(vote_events: pd.DataFrame) -> pd.DataFrame:
    df = vote_events.sort_values("vote_datetime").reset_index(drop=True).copy()
    df[TARGET_COLUMN] = (df["outcome"] == "carried").astype(int)

    overall_prior = df[TARGET_COLUMN].shift().expanding().mean()

    for col, prior_col in [("committee", "committee_prior_carry_rate"), ("motion_type", "motion_type_prior_carry_rate")]:
        df[prior_col] = df.groupby(col)[TARGET_COLUMN].transform(lambda s: s.shift().expanding().mean())
        df[prior_col] = df[prior_col].fillna(overall_prior)

    # First vote in the whole dataset has no prior at all -- fall back to
    # a neutral 0.5 rather than leaving a NaN the model can't use.
    df[FEATURE_COLUMNS[-2:]] = df[FEATURE_COLUMNS[-2:]].fillna(0.5)
    return df


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from src.pipeline.load_voting_record import load_vote_events

    events = load_vote_events(sys.argv[1] if len(sys.argv) > 1 else "data/raw/voting_record_2022-2026.csv")
    features = build_feature_table(events)
    print(features[FEATURE_COLUMNS + [TARGET_COLUMN]].head(10).to_string())
