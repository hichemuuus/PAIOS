"""Parameter extraction — predicts tool parameters from user requests.

This package provides:
  - ParameterExtractionModel: multi-tool, multi-parameter classifier
  - train_parameter_extraction(): training pipeline
  - predict_parameters() / predict_parameters_multitool(): inference API
"""

from paios.intelligence.parameter_extraction.model import ParameterExtractionModel as ParameterExtractionModel
from paios.intelligence.parameter_extraction.trainer import train_parameter_extraction as train_parameter_extraction
from paios.intelligence.parameter_extraction.inference import predict_parameters as predict_parameters
from paios.intelligence.parameter_extraction.inference import predict_parameters_multitool as predict_parameters_multitool
from paios.intelligence.parameter_extraction.inference import reset_model as reset_parameter_model
from paios.intelligence.parameter_extraction.dataset import ParameterExtractionDataset as ParameterExtractionDataset
from paios.intelligence.parameter_extraction.schema import ParameterExample as ParameterExample
from paios.intelligence.parameter_extraction.schema import ParameterPrediction as ParameterPrediction
from paios.intelligence.parameter_extraction.schema import TOOL_PARAMETER_SCHEMAS as TOOL_PARAMETER_SCHEMAS
