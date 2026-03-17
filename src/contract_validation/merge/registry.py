import logging
from dataclasses import is_dataclass
from typing import TYPE_CHECKING, Callable

from app.domain.entities.errors import MergeFieldMessage
from app.domain.entities.merge_types import ValueCandidate
from app.domain.exceptions import UnknownHandlerTypeError
from app.domain.merge.handlers import (
    is_scalar,
    merge_dataclass_default,
    merge_list_strict,
    merge_scalar_strict,
)


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    pass


class MergeRegistry:
    def __init__(self, name: str = "default"):
        self.name = name
        self.handlers: dict[type, Callable] = {}

        self.scalar_handler: Callable = merge_scalar_strict
        self.list_handler: Callable = merge_list_strict
        self.dataclass_handler: Callable = merge_dataclass_default

    def register_type(self, type_: type, handler: Callable) -> None:
        self.handlers[type_] = handler

    def merge(
        self,
        candidates: list[ValueCandidate],
        path: str,
        errors: list[MergeFieldMessage],
    ) -> ValueCandidate | None:
        all_sources = []
        seen = set()
        for c in candidates:
            for s in c.sources:
                s_id = id(s.document)
                if s_id not in seen:
                    all_sources.append(s)
                    seen.add(s_id)

        defined_candidates = [c for c in candidates if c.value is not None]

        if not defined_candidates:
            return ValueCandidate(value=None, sources=all_sources)

        value = defined_candidates[0].value
        value_type = type(value)

        handler = self._get_handler(value_type)
        if handler is None:
            error_msg = f"No handler for type {value_type} in registry '{self.name}'"
            logger.info(f"Merge failed for path='{path}': {error_msg}")
            raise UnknownHandlerTypeError(error_msg)

        result = handler(defined_candidates, path, self, errors)

        if result is not None:
            return ValueCandidate(value=result.value, sources=all_sources)

        logger.info(f"Merge returned None for path='{path}'")
        return result

    def _get_handler(self, value_type: type) -> Callable | None:
        if value_type in self.handlers:
            return self.handlers[value_type]

        if is_dataclass(value_type):
            return self.dataclass_handler

        if value_type is list or (
            isinstance(value_type, type) and issubclass(value_type, list)
        ):
            return self.list_handler

        if is_scalar(value_type):
            return self.scalar_handler

        return None
