"""Data loading, cleaning and feature preparation for the market-value model.

Every decision here is documented in the AI Subsystem Report, Section 1.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "fifa_players.csv"
CLEAN_PATH = ROOT / "data" / "processed" / "players_clean.csv"

TARGET = "value_euro"

# Columns removed from the feature set, with the reason.
LEAKY = ["release_clause_euro", "wage_euro"]  # money columns set from market value
SPARSE = ["national_team", "national_rating", "national_team_position", "national_jersey_number"]  # 95% missing
DISPLAY_ONLY = ["name", "full_name", "birth_date", "nationality", "positions"]
COSMETIC = ["body_type"]  # game cosmetic; some rows carry a star's own name

SKILLS = [
    "crossing", "finishing", "heading_accuracy", "short_passing", "volleys", "dribbling", "curve",
    "freekick_accuracy", "long_passing", "ball_control", "acceleration", "sprint_speed", "agility",
    "reactions", "balance", "shot_power", "jumping", "stamina", "strength", "long_shots", "aggression",
    "interceptions", "positioning", "vision", "penalties", "composure", "marking", "standing_tackle",
    "sliding_tackle",
]
NUMERIC_FEATURES = [
    "age", "height_cm", "weight_kgs", "overall_rating", "potential", "potential_gap",
    "international_reputation(1-5)", "weak_foot(1-5)", "skill_moves(1-5)",
] + SKILLS
CATEGORICAL_FEATURES = ["position_group", "preferred_foot"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# The source turned 5'10" and 5'11" into 5'0" and 5'1" (see report, Section 1).
HEIGHT_FIX = {152.40: 177.80, 154.94: 180.34}

POSITION_GROUP = {
    "GK": "GK",
    "CB": "DEF", "LB": "DEF", "RB": "DEF", "LWB": "DEF", "RWB": "DEF",
    "CDM": "MID", "CM": "MID", "CAM": "MID", "LM": "MID", "RM": "MID",
    "LW": "FWD", "RW": "FWD", "ST": "FWD", "CF": "FWD",
}


def load_raw(path=RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.insert(0, "player_id", np.arange(1, len(df) + 1))  # the dataset has no ID column
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["height_cm"] = df["height_cm"].round(2).replace(HEIGHT_FIX)
    df["primary_position"] = df["positions"].str.split(",").str[0].str.strip()
    df["position_group"] = df["primary_position"].map(POSITION_GROUP).fillna("MID")
    df["potential_gap"] = df["potential"] - df["overall_rating"]  # room to grow
    return df


def model_frame(df: pd.DataFrame):
    """Rows with a recorded value, the feature matrix X and the log-scale target y."""
    train = df[df[TARGET].notna()].reset_index(drop=True)
    X = train[FEATURES]
    y = np.log(train[TARGET])  # log(euros): see report, Section 2
    return train, X, y


def export_clean(df: pd.DataFrame, path=CLEAN_PATH) -> pd.DataFrame:
    """Save the cleaned dataset: every player, display fields + model features + target.

    Excluded columns (leaky, sparse, cosmetic) are left out. Players with no recorded
    value are kept (has_value = False) so the dashboard can still show them.
    """
    cols = (["player_id"] + DISPLAY_ONLY + ["primary_position"] + FEATURES + [TARGET])
    out = df[cols].copy()
    out["has_value"] = out[TARGET].notna()
    out["log_value"] = np.log(out[TARGET])
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out


if __name__ == "__main__":
    d = clean(load_raw())
    t, X, y = model_frame(d)
    out = export_clean(d)
    print(f"{len(d)} players loaded, {len(t)} with a recorded value, {X.shape[1]} features")
    print(f"saved {CLEAN_PATH.relative_to(ROOT)}: {out.shape[0]} rows x {out.shape[1]} columns")
