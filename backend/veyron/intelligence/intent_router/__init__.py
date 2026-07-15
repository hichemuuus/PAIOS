"""Intent router — predicts mode, domain, and intent category from user requests.

Provides:
  - IntentRouterModel: multi-output TF-IDF + LogisticRegression model
  - train_intent_router(): training pipeline
  - route_request(): inference API with per-field confidence fallback
  - IntentRouterEvaluator: accuracy, per-class P/R/F1, confusion matrix
  - IntentRouterDataset: dataset container + synthetic builder

Follows the same conventions as ``memory_retrieval``: singleton inference,
pickle persistence, graceful empty fallback.
"""

from veyron.intelligence.intent_router.dataset import IntentRouterDataset as IntentRouterDataset
from veyron.intelligence.intent_router.evaluation import (
    IntentRouterEvaluator as IntentRouterEvaluator,
)
from veyron.intelligence.intent_router.inference import reset_model as reset_intent_router_model
from veyron.intelligence.intent_router.inference import route_request as route_request
from veyron.intelligence.intent_router.model import IntentRouterModel as IntentRouterModel
from veyron.intelligence.intent_router.schema import IntentRouterExample as IntentRouterExample
from veyron.intelligence.intent_router.schema import IntentRouterPrediction as IntentRouterPrediction
from veyron.intelligence.intent_router.trainer import train_intent_router as train_intent_router
