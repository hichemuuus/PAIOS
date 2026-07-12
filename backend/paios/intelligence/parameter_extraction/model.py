"""Parameter extraction model — predicts tool parameters from request text.

For each tool, trains a pipeline that vectorizes text and predicts all
parameter values. Uses TF-IDF vectorization + per-parameter classifiers
with automatic handling of single-class parameters.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _make_classifier(num_classes: int) -> Any:
    """Return a classifier appropriate for the number of target classes.

    For single-class outputs, uses DummyClassifier (always predicts the
    only available class). For multi-class, uses LogisticRegression.
    """
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression

    if num_classes < 2:
        return DummyClassifier(strategy="constant", constant=0)
    return LogisticRegression(max_iter=2000, C=1.5)


class ParameterExtractionModel:
    """Multi-tool, multi-parameter classifier for parameter extraction.

    For each tool, maintains a TfidfVectorizer + per-parameter classifier.
    Predicts parameter values as categorical labels from the training set.
    Automatically handles parameters with only one unique value.
    """

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}
        self._vectorizers: dict[str, Any] = {}
        self._param_names: dict[str, list[str]] = {}
        self._param_values: dict[str, dict[str, list[str]]] = {}
        self._single_value_params: dict[str, set[str]] = {}
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    @property
    def tools(self) -> list[str]:
        return sorted(self._models.keys())

    def fit(self, data: list[tuple[str, str, dict[str, str]]]) -> None:
        """Fit per-tool parameter extraction models.

        Args:
            data: List of (request_text, tool_name, {param: value}) tuples.
        """
        from collections import defaultdict
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline

        by_tool: dict[str, list[tuple[str, dict[str, str]]]] = defaultdict(list)
        for request, tool_name, params in data:
            by_tool[tool_name].append((request, params))

        for tool_name, examples in by_tool.items():
            X = [ex[0] for ex in examples]
            param_dicts = [ex[1] for ex in examples]

            all_param_names = sorted({k for d in param_dicts for k in d})
            self._param_names[tool_name] = all_param_names

            values: dict[str, list[str]] = {}
            for p in all_param_names:
                vals = sorted({str(d.get(p, "")) for d in param_dicts})
                values[p] = vals
            self._param_values[tool_name] = values

            svp: set[str] = set()
            y = []
            for d in param_dicts:
                row = []
                for p in all_param_names:
                    val = str(d.get(p, ""))
                    idx = values[p].index(val) if val in values[p] else -1
                    row.append(idx)
                y.append(row)

            vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 3), sublinear_tf=True)
            X_vec = vec.fit_transform(X)

            classifiers: list[Any] = []
            for i, p in enumerate(all_param_names):
                n_classes = len(values[p])
                clf = _make_classifier(n_classes)
                y_col = [row[i] for row in y]
                clf.fit(X_vec, y_col)
                classifiers.append(clf)
                if n_classes < 2:
                    svp.add(p)

            self._vectorizers[tool_name] = vec
            self._models[tool_name] = classifiers
            self._single_value_params[tool_name] = svp

        self._fitted = bool(self._models)

    def predict(self, text: str, tool_name: str) -> dict[str, str]:
        """Predict parameter values for a given tool."""
        if not self._fitted:
            raise RuntimeError("model not fitted")
        if tool_name not in self._models:
            return {}

        vec = self._vectorizers[tool_name]
        classifiers = self._models[tool_name]
        param_names = self._param_names[tool_name]
        values = self._param_values[tool_name]

        X_vec = vec.transform([text])
        result: dict[str, str] = {}
        for i, p in enumerate(param_names):
            if i < len(classifiers):
                idx = int(classifiers[i].predict(X_vec)[0])
                if 0 <= idx < len(values[p]):
                    result[p] = values[p][idx]
                else:
                    result[p] = ""
        return result

    def predict_with_proba(self, text: str, tool_name: str) -> dict[str, list[tuple[str, float]]]:
        """Predict parameters with per-value confidence scores."""
        if not self._fitted:
            raise RuntimeError("model not fitted")
        if tool_name not in self._models:
            return {}

        vec = self._vectorizers[tool_name]
        classifiers = self._models[tool_name]
        param_names = self._param_names[tool_name]
        values = self._param_values[tool_name]

        X_vec = vec.transform([text])
        result: dict[str, list[tuple[str, float]]] = {}
        for i, p in enumerate(param_names):
            if i < len(classifiers):
                try:
                    probs = classifiers[i].predict_proba(X_vec)[0]
                    candidates = [(values[p][j], float(probs[j])) for j in range(len(values[p]))]
                except AttributeError:
                    candidates = []
                candidates.sort(key=lambda x: x[1], reverse=True)
                result[p] = candidates
        return result

    def save(self, path: str | Path) -> None:
        """Serialise the fitted model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "models": self._models,
            "vectorizers": self._vectorizers,
            "param_names": self._param_names,
            "param_values": self._param_values,
            "single_value_params": self._single_value_params,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("parameter extraction model saved to %s", path)

    def load(self, path: str | Path) -> None:
        """Load a previously saved model from disk."""
        path = Path(path)
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._models = data["models"]
        self._vectorizers = data.get("vectorizers", {})
        self._param_names = data["param_names"]
        self._param_values = data["param_values"]
        self._single_value_params = data.get("single_value_params", set())
        self._fitted = True
        logger.info("parameter extraction model loaded from %s", path)
