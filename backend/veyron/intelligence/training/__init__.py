"""Veyron training data pipeline — collect, score, export, and train micro-models.

This package builds training datasets from real agent execution history so
Veyron can train its own micro-models on actual usage patterns.
"""

from veyron.intelligence.training.collector import TrainingDataCollector as TrainingDataCollector
from veyron.intelligence.training.collector import get_collector as get_collector
from veyron.intelligence.training.collector import reset_collector as reset_collector
from veyron.intelligence.training.dataset import TrainingDataset as TrainingDataset
from veyron.intelligence.training.evaluation import IntentEvalReport as IntentEvalReport
from veyron.intelligence.training.evaluation import IntentEvaluator as IntentEvaluator
from veyron.intelligence.training.evaluation import ModelComparison as ModelComparison
from veyron.intelligence.training.evaluation import ToolSelectorEvalReport as ToolSelectorEvalReport
from veyron.intelligence.training.evaluation import ToolSelectorEvaluator as ToolSelectorEvaluator
from veyron.intelligence.training.exporter import TrainingExporter as TrainingExporter
from veyron.intelligence.training.exporter import get_exporter as get_exporter
from veyron.intelligence.training.exporter import reset_exporter as reset_exporter
from veyron.intelligence.training.quality import QualityScorer as QualityScorer
from veyron.intelligence.training.trainer_v2 import TrainingPipelineV2 as TrainingPipelineV2
