from app.domain.entities.merge_types import ValueCandidate, Source
from app.domain.merge.registry import MergeRegistry
from app.domain.merge.defaults import (
    STRICT_REGISTRY,
    FLEXIBLE_REGISTRY,
    CONCAT_REGISTRY,
)

__all__ = [
    "ValueCandidate",
    "Source",
    "MergeRegistry",
    "STRICT_REGISTRY",
    "FLEXIBLE_REGISTRY",
    "CONCAT_REGISTRY",
]
