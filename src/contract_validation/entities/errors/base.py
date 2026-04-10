from dataclasses import dataclass
from typing import ClassVar, Literal


@dataclass(kw_only=True)
class BaseContractError:
    kind: ClassVar[Literal["check", "merge"]]
    source: str = ""

    @property
    def error_type(self) -> str:
        return type(self).__name__
