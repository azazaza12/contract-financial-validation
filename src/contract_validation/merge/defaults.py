from .handlers import (
    merge_dataclass_default,
    merge_list_concat,
    merge_list_flexible,
    merge_list_strict,
    merge_scalar_pick_first,
    merge_scalar_strict,
    merge_scalar_strict_str,
)
from .registry import MergeRegistry


STRICT_REGISTRY = MergeRegistry("strict")
STRICT_REGISTRY.scalar_handler = merge_scalar_strict
STRICT_REGISTRY.scalar_handler_str = merge_scalar_strict_str
STRICT_REGISTRY.list_handler = merge_list_strict
STRICT_REGISTRY.dataclass_handler = merge_dataclass_default

FLEXIBLE_REGISTRY = MergeRegistry("flexible")
FLEXIBLE_REGISTRY.scalar_handler = merge_scalar_pick_first
FLEXIBLE_REGISTRY.list_handler = merge_list_flexible
FLEXIBLE_REGISTRY.dataclass_handler = merge_dataclass_default

CONCAT_REGISTRY = MergeRegistry("concat")
CONCAT_REGISTRY.scalar_handler = merge_scalar_pick_first
CONCAT_REGISTRY.list_handler = merge_list_concat
CONCAT_REGISTRY.dataclass_handler = merge_dataclass_default

DEFAULT_REGISTRY = STRICT_REGISTRY
