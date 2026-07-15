"""Veyron intelligence layer — Tier-1 micro-models for routing and reasoning.

Intended to handle high-confidence, narrow-domain tasks without invoking the
full LLM. Falls back gracefully when confidence is low.
"""

from veyron.intelligence.intent.dataset import IntentDataset as IntentDataset
from veyron.intelligence.intent.inference import classify_intent as classify_intent
from veyron.intelligence.intent.model import IntentModel as IntentModel
from veyron.intelligence.models.registry import ModelRegistry as ModelRegistry
from veyron.intelligence.models.registry import get_registry as get_registry
from veyron.intelligence.models.registry import reset_registry as reset_registry
from veyron.intelligence.models.schema import STATUS_CANDIDATE as STATUS_CANDIDATE
from veyron.intelligence.models.schema import STATUS_DEPRECATED as STATUS_DEPRECATED
from veyron.intelligence.models.schema import STATUS_PRODUCTION as STATUS_PRODUCTION
from veyron.intelligence.models.schema import ModelMetadata as ModelMetadata
from veyron.intelligence.scheduler import IntelligenceScheduler as IntelligenceScheduler
from veyron.intelligence.tool_selector.model import ToolSelectorModel as ToolSelectorModel
from veyron.intelligence.training.dataset import UserInteraction as UserInteraction
from veyron.intelligence.training.dataset import load_user_interactions as load_user_interactions
from veyron.intelligence.training.dataset import save_user_interaction as save_user_interaction
from veyron.intelligence.training.dataset import (
    user_interactions_to_dataset as user_interactions_to_dataset,
)
from veyron.intelligence.training.feedback import TrainingFeedbackLoop as TrainingFeedbackLoop
from veyron.intelligence.training.retrain import BenchmarkComparator as BenchmarkComparator
from veyron.intelligence.training.retrain import NewExampleTrigger as NewExampleTrigger
from veyron.intelligence.training.retrain import RetrainingOrchestrator as RetrainingOrchestrator
