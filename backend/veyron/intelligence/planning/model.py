from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from veyron.intelligence.planning.schema import (
    PLANNING_STEP_CATEGORIES,
    STEP_BINS,
    bin_center,
    step_count_to_bin,
)

logger = logging.getLogger(__name__)


class PlanningModel:
    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._plan_clf: LogisticRegression | None = None
        self._steps_clf: LogisticRegression | None = None
        self._cat_indices: list[int] = []
        self._cat_clfs: list[LogisticRegression] = []
        self._active_categories: list[str] = []
        self.fitted: bool = False

    def fit(
        self,
        texts: list[str],
        plan_labels: list[bool],
        steps_labels: list[str],
        categories_matrix: list[list[int]],
    ) -> None:
        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        X = self._vectorizer.fit_transform(texts)

        self._plan_clf = LogisticRegression(max_iter=1000, random_state=42)
        self._plan_clf.fit(X, plan_labels)

        step_bins = [step_count_to_bin(s) if isinstance(s, int) else s for s in steps_labels]
        self._steps_clf = LogisticRegression(max_iter=1000, random_state=42)
        self._steps_clf.fit(X, step_bins)

        cat_arr = np.array(categories_matrix, dtype=float)
        self._cat_indices = []
        self._cat_clfs = []
        self._active_categories = []
        for i, cat in enumerate(PLANNING_STEP_CATEGORIES):
            col = cat_arr[:, i]
            unique = set(col)
            if len(unique) < 2:
                continue
            self._cat_indices.append(i)
            self._active_categories.append(cat)
            clf = LogisticRegression(max_iter=1000, random_state=42)
            clf.fit(X, col)
            self._cat_clfs.append(clf)

        self.fitted = True
        logger.info(
            "planning model fitted on %d texts (%d plan classes, %d step bins, %d/%d categories active)",
            len(texts),
            len(set(plan_labels)),
            len(set(step_bins)),
            len(self._active_categories),
            len(PLANNING_STEP_CATEGORIES),
        )

    def predict_plan(self, text: str) -> bool:
        if not self._fitted_all():
            return False
        X = self._vectorizer.transform([text])
        return bool(self._plan_clf.predict(X)[0])

    def predict_step_bin(self, text: str) -> str:
        if not self._fitted_all():
            return "none"
        X = self._vectorizer.transform([text])
        return str(self._steps_clf.predict(X)[0])

    def predict_categories(self, text: str) -> list[str]:
        if not self._fitted_all():
            return []
        X = self._vectorizer.transform([text])
        result: list[str] = []
        for clf, cat in zip(self._cat_clfs, self._active_categories):
            if int(clf.predict(X)[0]) > 0:
                result.append(cat)
        return result

    def predict_plan_proba(self, text: str) -> float:
        if not self._fitted_all():
            return 0.0
        X = self._vectorizer.transform([text])
        probs = self._plan_clf.predict_proba(X)[0]
        return float(max(probs))

    def predict_step_proba(self, text: str) -> dict[str, float]:
        if not self._fitted_all():
            return {b: 0.0 for b in STEP_BINS}
        X = self._vectorizer.transform([text])
        probs = self._steps_clf.predict_proba(X)[0]
        classes = self._steps_clf.classes_.tolist()
        return {str(c): float(p) for c, p in zip(classes, probs)}

    def predict_categories_proba(self, text: str) -> dict[str, float]:
        result: dict[str, float] = {c: 0.0 for c in PLANNING_STEP_CATEGORIES}
        if not self._fitted_all():
            return result
        X = self._vectorizer.transform([text])
        for clf, cat in zip(self._cat_clfs, self._active_categories):
            probs = clf.predict_proba(X)[0]
            result[cat] = float(max(probs))
        return result

    def predict(self, text: str) -> tuple[bool, int, list[str], float, float, float]:
        plan = self.predict_plan(text)
        bin_name = self.predict_step_bin(text)
        steps = bin_center(bin_name)
        cats = self.predict_categories(text)
        plan_conf = self.predict_plan_proba(text)
        step_probs = self.predict_step_proba(text)
        steps_conf = max(step_probs.values()) if step_probs else 0.0
        overall_conf = (plan_conf + steps_conf) / 2.0
        return plan, steps, cats, plan_conf, steps_conf, overall_conf

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "vectorizer": self._vectorizer,
                "plan_clf": self._plan_clf,
                "steps_clf": self._steps_clf,
                "cat_clfs": self._cat_clfs,
                "active_categories": self._active_categories,
                "cat_indices": self._cat_indices,
                "fitted": self.fitted,
            }, f)
        logger.info("planning model saved to %s", path)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._vectorizer = data["vectorizer"]
        self._plan_clf = data["plan_clf"]
        self._steps_clf = data["steps_clf"]
        self._cat_clfs = data.get("cat_clfs", [])
        self._active_categories = data.get("active_categories", [])
        self._cat_indices = data.get("cat_indices", [])
        self.fitted = data["fitted"]
        logger.info("planning model loaded from %s", path)

    def _fitted_all(self) -> bool:
        return (
            self.fitted
            and self._vectorizer is not None
            and self._plan_clf is not None
            and self._steps_clf is not None
        )
