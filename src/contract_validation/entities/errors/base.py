from dataclasses import dataclass


@dataclass(kw_only=True)
class BaseContractError:
    source: str = ""

    @property
    def error_type(self) -> str:
        return type(self).__name__
