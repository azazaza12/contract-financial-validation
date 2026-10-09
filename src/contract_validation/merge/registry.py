import logging
from dataclasses import is_dataclass
from enum import Enum
from typing import TYPE_CHECKING

from contract_validation.entities.errors.merge import BaseMergeError
from contract_validation.entities.merge_types import ValueCandidate
from contract_validation.exceptions import UnknownHandlerTypeError

from .handlers import (
    combine_sources,
    is_scalar,
    merge_dataclass_default,
    merge_list_strict,
    merge_scalar_strict,
    merge_scalar_strict_str,
)


if TYPE_CHECKING:
    from .handlers import MergeHandler

logger = logging.getLogger(__name__)


class MergeRegistry:
    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.handlers: dict[type, MergeHandler] = {}

        self.scalar_handler: MergeHandler = merge_scalar_strict
        self.scalar_handler_str: MergeHandler = merge_scalar_strict_str
        self.list_handler: MergeHandler = merge_list_strict
        self.dataclass_handler: MergeHandler = merge_dataclass_default

    def register_type(self, type_: type, handler: MergeHandler) -> None:
        self.handlers[type_] = handler

    def merge(
        self,
        candidates: list[ValueCandidate],
        path: str,
        errors: list[BaseMergeError],
    ) -> ValueCandidate | None:
        all_sources = combine_sources(candidates)

        defined_candidates = [c for c in candidates if c.value is not None]

        if not defined_candidates:
            return ValueCandidate(value=None, sources=all_sources)

        value = defined_candidates[0].value
        value_type = type(value)

        handler = self._get_handler(value_type)
        if handler is None:
            error_msg = f"No handler for type {value_type} in registry '{self.name}'"
            logger.warning("merge failed at %s: %s", path, error_msg)
            raise UnknownHandlerTypeError(error_msg)

        result = handler(defined_candidates, path, errors, self)

        if result is not None:
            return ValueCandidate(value=result.value, sources=all_sources)

        logger.info("merge returned no value at %s", path)
        return result

    def _get_handler(self, value_type: type) -> MergeHandler | None:
        if value_type in self.handlers:
            return self.handlers[value_type]

        if is_dataclass(value_type):
            return self.dataclass_handler

        if value_type is list or (
            isinstance(value_type, type) and issubclass(value_type, list)
        ):
            return self.list_handler

        if value_type is str:
            return self.scalar_handler_str

        if (isinstance(value_type, type) and issubclass(value_type, Enum)) or is_scalar(
            value_type
        ):
            return self.scalar_handler

        return None
