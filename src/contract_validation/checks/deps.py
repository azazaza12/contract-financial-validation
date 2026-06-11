from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, cast, get_args, get_origin

from app.domain.entities.field import BaseField
from app.domain.ports.checker import (
    IPositionsComplianceService,
    ITranscriptionComplianceService,
)

from .errors import (
    InvalidCheckSignatureError,
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)


@dataclass(frozen=True, slots=True)
class Requires[T]:
    field_type: type[T]

    def resolve(self, attr_name: str, fields: Iterable[BaseField], label: str) -> T:
        element_type = self.field_type
        if isinstance(element_type, type):
            field_type = element_type
            matches = [f for f in fields if isinstance(f, field_type)]
            if len(matches) == 0:
                raise MissingRequiredFieldError(
                    label=label,
                    param_name=attr_name,
                    field_type=field_type.__name__,
                )
            if len(matches) > 1:
                raise MultiplyRequiredFieldError(
                    label=label,
                    param_name=attr_name,
                    field_type=field_type.__name__,
                    count=len(matches),
                )
            return cast("T", matches[0])

        if get_origin(element_type) is not list:
            msg = (
                f"{label}.{attr_name}: Requires wants Field|list[Field], "
                f"got {element_type!r}"
            )
            raise InvalidCheckSignatureError(msg)
        args = get_args(element_type)
        if len(args) != 1:
            msg = f"{label}.{attr_name}: Requires list[T] needs 1 arg, got {len(args)}"
            raise InvalidCheckSignatureError(msg)
        field_type = args[0]
        matches = [f for f in fields if isinstance(f, field_type)]
        if len(matches) == 0:
            raise MissingRequiredFieldError(
                label=label,
                param_name=attr_name,
                field_type=field_type.__name__,
            )
        return cast("T", matches)


@dataclass(frozen=True, slots=True)
class OptionalDep[T]:
    field_type: type[T]

    def resolve(
        self, attr_name: str, fields: Iterable[BaseField], label: str
    ) -> T | None:
        element_type = self.field_type
        if isinstance(element_type, type):
            field_type = element_type
            matches = [f for f in fields if isinstance(f, field_type)]
            if len(matches) == 0:
                return None
            if len(matches) == 1:
                return cast("T", matches[0])
            raise MultiplyRequiredFieldError(
                label=label,
                param_name=attr_name,
                field_type=field_type.__name__,
                count=len(matches),
            )

        if get_origin(element_type) is not list:
            msg = (
                f"{label}.{attr_name}: OptionalDep wants Field|list[Field], "
                f"got {element_type!r}"
            )
            raise InvalidCheckSignatureError(msg)
        args = get_args(element_type)
        if len(args) != 1:
            msg = (
                f"{label}.{attr_name}: OptionalDep list[T] needs 1 arg, got {len(args)}"
            )
            raise InvalidCheckSignatureError(msg)
        field_type = args[0]
        matches = [f for f in fields if isinstance(f, field_type)]
        if len(matches) == 0:
            return cast("T", [])
        return cast("T", matches)


class CheckServices(Protocol):
    check_position_compliance_service: IPositionsComplianceService
    check_transcription_compliance_service: ITranscriptionComplianceService
