"""Memory retrieval — ranks candidate memories by relevance to a query.

This package provides:
  - MemoryRetrievalModel: TF-IDF + cosine-similarity ranker
  - train_memory_retrieval(): training pipeline
  - retrieve_memories(): inference API
  - MemoryRetrievalEvaluator: rank-aware evaluation (precision@k, recall@k, MRR)
  - MemoryRetrievalDataset: dataset container + synthetic generator

Follows the same conventions as ``parameter_extraction``: singleton inference,
pickle persistence, graceful empty fallback, and the ``evaluate_model(model,
test_cases)`` contract expected by the Phase 11.5 benchmark.
"""

from paios.intelligence.memory_retrieval.model import MemoryRetrievalModel as MemoryRetrievalModel
from paios.intelligence.memory_retrieval.trainer import train_memory_retrieval as train_memory_retrieval
from paios.intelligence.memory_retrieval.inference import retrieve_memories as retrieve_memories
from paios.intelligence.memory_retrieval.inference import reset_model as reset_memory_model
from paios.intelligence.memory_retrieval.dataset import MemoryRetrievalDataset as MemoryRetrievalDataset
from paios.intelligence.memory_retrieval.schema import MemoryRetrievalExample as MemoryRetrievalExample
from paios.intelligence.memory_retrieval.schema import MemoryRetrievalPrediction as MemoryRetrievalPrediction
from paios.intelligence.memory_retrieval.evaluation import MemoryRetrievalEvaluator as MemoryRetrievalEvaluator
