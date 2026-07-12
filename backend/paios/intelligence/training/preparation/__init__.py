"""Dataset preparation pipeline — validate, split, and format training data.

Transforms raw collected/synthetic examples into task-specific datasets
ready for micro-model training.
"""

from paios.intelligence.training.preparation.validator import DatasetValidator as DatasetValidator
from paios.intelligence.training.preparation.splitter import DatasetSplitter as DatasetSplitter
from paios.intelligence.training.preparation.formatter import DatasetFormatter as DatasetFormatter
