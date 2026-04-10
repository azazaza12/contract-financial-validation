from app.domain.entities.merge_types import Source, ValueCandidate
from app.domain.merge.defaults import (
    CONCAT_REGISTRY,
    FLEXIBLE_REGISTRY,
    STRICT_REGISTRY,
)
from app.domain.merge.registry import MergeRegistry


__all__ = [
    "CONCAT_REGISTRY",
    "FLEXIBLE_REGISTRY",
    "STRICT_REGISTRY",
    "MergeRegistry",
    "Source",
    "ValueCandidate",
]
