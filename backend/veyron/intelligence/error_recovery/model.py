from __future__ import annotations

import logging
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from veyron.intelligence.error_recovery.schema import RECOVERY_ACTIONS, RecoveryAction

logger = logging.getLogger(__name__)


class ErrorRecoveryModel:
    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None
        self.fitted: bool = False

    def fit(self, texts: list[str], labels: list[str]) -> None:
        self._pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                sublinear_tf=True,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                random_state=42,
            )),
        ])
        self._pipeline.fit(texts, labels)
        self.fitted = True
        logger.info(
            "error recovery model fitted on %d texts (%d classes)",
            len(texts), len(set(labels)),
        )

    def predict(self, text: str) -> str:
        if not self.fitted or self._pipeline is None:
            return RecoveryAction.FALLBACK_LLM.value
        return self._pipeline.predict([text])[0]

    def predict_with_confidence(self, text: str) -> tuple[str, float]:
        if not self.fitted or self._pipeline is None:
            return RecoveryAction.FALLBACK_LLM.value, 0.0
        probs = self._pipeline.predict_proba([text])[0]
        classes = self._pipeline.classes_.tolist()
        best_idx = int(probs.argmax())
        return str(classes[best_idx]), float(probs[best_idx])

    def predict_proba(self, text: str) -> dict[str, float]:
        if not self.fitted or self._pipeline is None:
            return {a: 0.0 for a in RECOVERY_ACTIONS}
        probs = self._pipeline.predict_proba([text])[0]
        classes = self._pipeline.classes_.tolist()
        return {str(c): float(p) for c, p in zip(classes, probs)}

    def save(self, path: str) -> None:
        import pathlib
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "pipeline": self._pipeline,
                "fitted": self.fitted,
            }, f)
        logger.info("error recovery model saved to %s", path)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._pipeline = data["pipeline"]
        self.fitted = data["fitted"]
        logger.info("error recovery model loaded from %s", path)
