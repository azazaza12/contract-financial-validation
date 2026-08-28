from dataclasses import dataclass

from .merge_types import Source


@dataclass(frozen=True, kw_only=True)
class FieldLocation:
    field_name: str
    path: str
    sources: tuple[Source, ...]

    @property
    def full_path(self) -> str:
        return f"{self.field_name}.{self.path}"
