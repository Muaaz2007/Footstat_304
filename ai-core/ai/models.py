"""The two candidate AI techniques, built as scikit-learn pipelines."""
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures, StandardScaler

from preprocessing import CATEGORICAL_FEATURES, NUMERIC_FEATURES

SEED = 42


def linear_regression() -> Pipeline:
    """Technique 1: regularised multiple linear regression (ridge) on log(value).

    Age also enters squared because value rises then falls with age.
    Numeric features are standardised so the ridge penalty treats them equally.
    """
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("age2", Pipeline([("sq", PolynomialFeatures(2, include_bias=False)), ("sc", StandardScaler())]), ["age"]),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("pre", pre), ("model", RidgeCV(alphas=[0.01, 0.1, 1, 10, 100]))])


def random_forest() -> Pipeline:
    """Technique 2: random forest regression on log(value).

    Trees need no scaling and capture non-linear effects and interactions
    (e.g. age x potential) without hand-made terms.
    max_features=1.0 was chosen by tune_parameters.py: every split may use all
    features, which cut the validation median error from 3.50% (0.5) to 2.78%.
    """
    pre = ColumnTransformer([
        ("num", "passthrough", NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, max_features=1.0,
                               n_jobs=-1, random_state=SEED)
    return Pipeline([("pre", pre), ("model", rf)])


CANDIDATES = {"Linear regression (ridge)": linear_regression, "Random forest": random_forest}
