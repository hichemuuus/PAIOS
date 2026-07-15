"""Tool selection model — predicts required tools from user requests.

Exports:
  - ToolSelectorModel: trainable multi-label classifier
  - ToolSelectionDataset: training data management
  - ToolSelectionMetrics: evaluation metrics
  - train_tool_selector: training pipeline
  - predict_tools: inference API
  - predict_tool_names: inference API for string-only predictions
"""

from veyron.intelligence.tool_selector.dataset import ToolSelectionDataset
from veyron.intelligence.tool_selector.inference import (
    predict_tool_names,
    predict_tools,
)
from veyron.intelligence.tool_selector.inference import (
    reset_model as reset_ts_model,
)
from veyron.intelligence.tool_selector.metrics import ToolSelectionMetrics
from veyron.intelligence.tool_selector.model import ToolSelectorModel
from veyron.intelligence.tool_selector.schema import ToolPrediction, ToolSelectionExample
from veyron.intelligence.tool_selector.trainer import train_tool_selector
