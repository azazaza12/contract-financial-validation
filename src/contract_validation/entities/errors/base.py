from dataclasses import dataclass
from typing import ClassVar


@dataclass(kw_only=True)
class BaseContractError:
    kind: ClassVar[str]
    source: str = ""

    @property
    def error_type(self) -> str:
        return type(self).__name__
