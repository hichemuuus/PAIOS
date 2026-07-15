"""Intent classification — route user requests to the correct handler.

Exports:
  - IntentModel: model interface (can be trained with sklearn)
  - IntentDataset: dataset generation and loading
  - train_model: training pipeline
  - classify_intent: inference entrypoint
"""

from veyron.intelligence.intent.dataset import IntentDataset
from veyron.intelligence.intent.inference import ClassifierResult, classify_intent
from veyron.intelligence.intent.model import IntentModel
from veyron.intelligence.intent.trainer import train_model
