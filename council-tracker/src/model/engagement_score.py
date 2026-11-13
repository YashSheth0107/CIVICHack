"""
Turn a predicted P(carried) into a resident-facing "engagement priority":
close calls rank highest, landslides rank lowest, regardless of which
side is predicted to win -- a resident's input matters most when the
outcome is genuinely uncertain, not when their side is already winning
or already losing big.
"""
from __future__ import annotations

import pandas as pd


def priority_score(p_carried: float) -> float:
    """0.0 (certain outcome) .. 1.0 (dead-even, 50/50)."""
    return 1 - abs(p_carried - 0.5) * 2


def priority_label(score: float) -> str:
    if score >= 0.7:
        return "High - this is a close call, your voice could tip it"
    if score >= 0.35:
        return "Medium - leaning one way, but not locked in"
    return "Low - likely already decided either way"


def add_engagement_priority(df: pd.DataFrame, proba_col: str = "p_carried") -> pd.DataFrame:
    df = df.copy()
    df["engagement_priority_score"] = df[proba_col].apply(priority_score)
    df["engagement_priority_label"] = df["engagement_priority_score"].apply(priority_label)
    return df


if __name__ == "__main__":
    demo = pd.DataFrame({"p_carried": [0.95, 0.5, 0.52, 0.1, 0.63]})
    print(add_engagement_priority(demo))
