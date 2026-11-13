"""
Train the outcome predictor: given committee / motion type / historical
carry rates, predict P(this vote carries).

Split by TIME, not randomly -- train on the earlier portion of the term,
test on the later portion, since that's the realistic forecasting setup
(predict next votes from past ones), and a random split would leak
future committee carry-rate information into training.

Usage:
    python -m src.model.train_outcome_model data/raw/voting_record_2022-2026.csv
"""
from __future__ import annotations

import sys

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

sys.path.insert(0, ".")
from src.model.features import FEATURE_COLUMNS, TARGET_COLUMN, build_feature_table
from src.pipeline.load_voting_record import load_vote_events

CATEGORICAL = ["committee", "motion_type", "term"]
NUMERIC = ["committee_prior_carry_rate", "motion_type_prior_carry_rate"]


def build_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)],
        remainder="passthrough",  # numeric prior-rate columns pass through as-is
    )
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])


def train(csv_paths: list[str], test_frac: float = 0.2) -> Pipeline:
    events = pd.concat([load_vote_events(p) for p in csv_paths], ignore_index=True)
    features = build_feature_table(events)

    split_idx = int(len(features) * (1 - test_frac))
    train_df, test_df = features.iloc[:split_idx], features.iloc[split_idx:]

    # Column order must match CATEGORICAL + NUMERIC for the ColumnTransformer above.
    X_train, y_train = train_df[CATEGORICAL + NUMERIC], train_df[TARGET_COLUMN]
    X_test, y_test = test_df[CATEGORICAL + NUMERIC], test_df[TARGET_COLUMN]

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    proba = pipeline.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    majority_baseline = max(y_test.mean(), 1 - y_test.mean())
    print(f"Train: {len(train_df)} votes | Test: {len(test_df)} votes")
    print(f"Majority-class baseline accuracy: {majority_baseline:.3f}")
    print(f"Model accuracy @0.5 threshold:     {accuracy_score(y_test, preds):.3f}  "
          f"(class_weight='balanced' trades this away on purpose -- see AUC)")
    print(f"ROC AUC (the metric that matters): {roc_auc_score(y_test, proba):.3f}")
    print(f"Log loss:                          {log_loss(y_test, proba):.3f}")
    print(f"Brier score:                       {brier_score_loss(y_test, proba):.3f}")

    return pipeline


if __name__ == "__main__":
    paths = sys.argv[1:] or ["data/raw/voting_record_2022-2026.csv"]
    model = train(paths)
    joblib.dump(model, "models/outcome_model.joblib")
    print("Saved -> models/outcome_model.joblib")
