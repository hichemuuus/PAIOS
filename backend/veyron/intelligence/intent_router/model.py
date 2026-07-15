"""Intent router model — multi-output TF-IDF + LogisticRegression.

Predicts three fields from a user request:
  1. mode (react/plan)   — binary classifier
  2. domain (5 classes)  — multi-class classifier
  3. intent_category     — multi-class classifier

Uses a single shared TF-IDF vectorizer with three independent LogisticRegression
heads, matching the existing micro-model stack conventions.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_DOMAIN_CLASSES = ["system", "filesystem", "project", "terminal", "general"]


class IntentRouterModel:
    """Multi-output TF-IDF + LogisticRegression model for intent routing.

    Conventions match the other micro-models: ``fitted`` property, ``fit``,
    ``predict``, ``save``, and ``load``. State is pickled as a dict for
    backward compatibility.
    """

    def __init__(self) -> None:
        self._vectorizer: Any = None
        self._mode_clf: Any = None
        self._domain_clf: Any = None
        self._intent_clf: Any = None
        self._mode_classes: list[str] = ["react", "plan"]
        self._domain_classes: list[str] = list(_DOMAIN_CLASSES)
        self._intent_classes: list[str] = []
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    @property
    def intent_classes(self) -> list[str]:
        return list(self._intent_classes)

    def fit(
        self,
        texts: list[str],
        modes: list[str],
        domains: list[str],
        intents: list[str],
    ) -> None:
        """Fit the three classifiers on aligned lists of labels.

        Args:
            texts: Input request texts.
            modes: Ground-truth mode labels ("react" | "plan").
            domains: Ground-truth domain labels.
            intents: Ground-truth intent category labels.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        cleaned = [t for t in texts if isinstance(t, str) and t.strip()]
        if not cleaned:
            self._fitted = False
            return

        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            sublinear_tf=True,
            stop_words="english",
        )
        X = self._vectorizer.fit_transform(cleaned)

        self._mode_clf = LogisticRegression(max_iter=1000)
        self._mode_clf.fit(X, modes[:len(cleaned)])
        self._mode_classes = list(self._mode_clf.classes_)

        self._domain_clf = LogisticRegression(max_iter=1000)
        self._domain_clf.fit(X, domains[:len(cleaned)])
        self._domain_classes = list(self._domain_clf.classes_)

        self._intent_clf = LogisticRegression(max_iter=1000)
        self._intent_clf.fit(X, intents[:len(cleaned)])
        self._intent_classes = list(self._intent_clf.classes_)

        self._fitted = True
        logger.info(
            "intent router fitted on %d texts (mode=%d, domain=%d, intent=%d classes)",
            len(cleaned),
            len(self._mode_classes),
            len(self._domain_classes),
            len(self._intent_classes),
        )

    def predict(self, text: str) -> tuple[str, str, str]:
        """Return (mode, domain, intent_category) for a single request."""
        if not self._fitted:
            raise RuntimeError("model not fitted")
        X = self._vectorizer.transform([text])
        mode = str(self._mode_clf.predict(X)[0])
        domain = str(self._domain_clf.predict(X)[0])
        intent = str(self._intent_clf.predict(X)[0])
        return mode, domain, intent

    def predict_with_confidence(self, text: str) -> dict[str, tuple[str, float]]:
        """Return {(field): (prediction, confidence)} for all three fields."""
        if not self._fitted:
            raise RuntimeError("model not fitted")
        X = self._vectorizer.transform([text])
        result: dict[str, tuple[str, float]] = {}

        mode_probs = self._mode_clf.predict_proba(X)[0]
        mode_idx = int(self._mode_clf.predict(X)[0] == self._mode_classes[1]) if len(self._mode_classes) > 1 else 0
        mode_pred = str(self._mode_clf.predict(X)[0])
        mode_conf = round(float(max(mode_probs)), 4)
        result["mode"] = (mode_pred, mode_conf)

        domain_probs = self._domain_clf.predict_proba(X)[0]
        domain_pred = str(self._domain_clf.predict(X)[0])
        domain_conf = round(float(max(domain_probs)), 4)
        result["domain"] = (domain_pred, domain_conf)

        intent_probs = self._intent_clf.predict_proba(X)[0]
        intent_pred = str(self._intent_clf.predict(X)[0])
        intent_conf = round(float(max(intent_probs)), 4)
        result["intent_category"] = (intent_pred, intent_conf)

        return result

    def predict_proba(self, text: str) -> dict[str, dict[str, float]]:
        """Return {field: {class: probability}} for all three heads."""
        if not self._fitted:
            raise RuntimeError("model not fitted")
        X = self._vectorizer.transform([text])
        result: dict[str, dict[str, float]] = {}

        mode_probs = self._mode_clf.predict_proba(X)[0]
        result["mode"] = dict(zip(self._mode_classes, (round(float(p), 4) for p in mode_probs)))

        domain_probs = self._domain_clf.predict_proba(X)[0]
        result["domain"] = dict(zip(self._domain_classes, (round(float(p), 4) for p in domain_probs)))

        intent_probs = self._intent_clf.predict_proba(X)[0]
        result["intent_category"] = dict(zip(self._intent_classes, (round(float(p), 4) for p in intent_probs)))

        return result

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "vectorizer": self._vectorizer,
            "mode_clf": self._mode_clf,
            "domain_clf": self._domain_clf,
            "intent_clf": self._intent_clf,
            "mode_classes": self._mode_classes,
            "domain_classes": self._domain_classes,
            "intent_classes": self._intent_classes,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("intent router model saved to %s", path)

    def load(self, path: str | Path) -> None:
        path = Path(path)
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._vectorizer = data.get("vectorizer")
        self._mode_clf = data.get("mode_clf")
        self._domain_clf = data.get("domain_clf")
        self._intent_clf = data.get("intent_clf")
        self._mode_classes = data.get("mode_classes", ["react", "plan"])
        self._domain_classes = data.get("domain_classes", _DOMAIN_CLASSES)
        self._intent_classes = data.get("intent_classes", [])
        self._fitted = all(
            x is not None
            for x in [self._vectorizer, self._mode_clf, self._domain_clf, self._intent_clf]
        )
        logger.info("intent router model loaded from %s", path)
