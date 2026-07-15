"""Dataset preparation pipeline — validate, split, and format training data.

Transforms raw collected/synthetic examples into task-specific datasets
ready for micro-model training.
"""

from veyron.intelligence.training.preparation.formatter import DatasetFormatter as DatasetFormatter
from veyron.intelligence.training.preparation.splitter import DatasetSplitter as DatasetSplitter
from veyron.intelligence.training.preparation.validator import DatasetValidator as DatasetValidator
