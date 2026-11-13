"""
Apply the trained outcome model to the decisions table from
src/pipeline/stage.py, so every open or in-progress item gets a
predicted P(carried) and an engagement-priority label.

Note: this only applies to items that *will get a recorded vote* --
most items pass on a no-vote consent agenda, which this model can't
see coming (see load_voting_record.py's caveat). Treat items with no
historical recorded-vote pattern on their committee/motion type as
likely-routine rather than running them through the model at all --
that's a TODO for whoever builds the "will this even be contested"
pre-filter on top of this.

Usage:
    python -m src.model.predict
"""
from __future__ import annotations

import sys

import joblib
import pandas as pd

sys.path.insert(0, ".")
from src.model.engagement_score import add_engagement_priority
from src.model.train_outcome_model import CATEGORICAL, NUMERIC


def predict_proba(model, rows: pd.DataFrame) -> pd.Series:
    """rows must have columns: committee, motion_type, term,
    committee_prior_carry_rate, motion_type_prior_carry_rate."""
    return pd.Series(model.predict_proba(rows[CATEGORICAL + NUMERIC])[:, 1], index=rows.index)


if __name__ == "__main__":
    model = joblib.load("models/outcome_model.joblib")

    # Toy example -- swap in real upcoming items once the lifecycle
    # tracker surfaces items that are scheduled but not yet voted on.
    example = pd.DataFrame(
        [
            {"committee": "City Council", "motion_type": "Adopt Item as Amended", "term": "2022-2026",
             "committee_prior_carry_rate": 0.85, "motion_type_prior_carry_rate": 0.9},
            {"committee": "Planning and Housing Committee", "motion_type": "Amend Item", "term": "2022-2026",
             "committee_prior_carry_rate": 0.55, "motion_type_prior_carry_rate": 0.5},
        ]
    )
    example["p_carried"] = predict_proba(model, example)
    print(add_engagement_priority(example)[["committee", "motion_type", "p_carried", "engagement_priority_label"]])
