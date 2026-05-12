from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Requires[T]:
    field_type: type[T]


@dataclass(frozen=True, slots=True)
class OptionalDep[T]:
    field_type: type[T]
