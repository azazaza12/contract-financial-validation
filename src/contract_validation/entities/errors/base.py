from dataclasses import dataclass
from typing import ClassVar, Literal


@dataclass(kw_only=True)
class BaseContractError:
    kind: ClassVar[Literal["check", "merge"]]
    source: str = ""

    @property
    def error_type(self) -> str:
        return type(self).__name__

    def compare(self, error: BaseContractError) -> bool:
        if type(self) is not type(error):
            return False

        if self.kind != error.kind:
            return False

        return self._compare_same_type(error)

    def _compare_same_type(self, error: BaseContractError) -> bool:
        msg = f"{type(self).__name__} must implement _compare_same_type"
        raise NotImplementedError(msg)
