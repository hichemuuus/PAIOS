"""PAIOS intelligence layer — Tier-1 micro-models for routing and reasoning.

Intended to handle high-confidence, narrow-domain tasks without invoking the
full LLM. Falls back gracefully when confidence is low.
"""

from paios.intelligence.intent.inference import classify_intent as classify_intent
from paios.intelligence.intent.model import IntentModel as IntentModel
from paios.intelligence.intent.dataset import IntentDataset as IntentDataset
from paios.intelligence.tool_selector.model import ToolSelectorModel as ToolSelectorModel
from paios.intelligence.models.registry import ModelRegistry as ModelRegistry
from paios.intelligence.models.registry import get_registry as get_registry
from paios.intelligence.models.registry import reset_registry as reset_registry
from paios.intelligence.models.schema import ModelMetadata as ModelMetadata
from paios.intelligence.models.schema import STATUS_CANDIDATE as STATUS_CANDIDATE
from paios.intelligence.models.schema import STATUS_DEPRECATED as STATUS_DEPRECATED
from paios.intelligence.models.schema import STATUS_PRODUCTION as STATUS_PRODUCTION
from paios.intelligence.training.feedback import TrainingFeedbackLoop as TrainingFeedbackLoop
from paios.intelligence.training.retrain import RetrainingOrchestrator as RetrainingOrchestrator
from paios.intelligence.training.retrain import NewExampleTrigger as NewExampleTrigger
from paios.intelligence.training.retrain import BenchmarkComparator as BenchmarkComparator
from paios.intelligence.training.dataset import UserInteraction as UserInteraction
from paios.intelligence.training.dataset import save_user_interaction as save_user_interaction
from paios.intelligence.training.dataset import load_user_interactions as load_user_interactions
from paios.intelligence.training.dataset import user_interactions_to_dataset as user_interactions_to_dataset
from paios.intelligence.scheduler import IntelligenceScheduler as IntelligenceScheduler
