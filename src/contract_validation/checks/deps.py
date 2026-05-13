from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, get_args, get_origin

from app.domain.checks.errors import (
    InvalidCheckSignatureError,
    MissingRequiredFieldError,
    MultiplyRequiredFieldError,
)
from app.domain.entities.single_supplier_fields import BaseField
from app.domain.service.checker import (
    IPositionsComplianceService,
    ITranscriptionComplianceService,
)


@dataclass(frozen=True, slots=True)
class Requires[T]:
    field_type: type[T]

    def resolve(self, attr_name: str, fields: Iterable[BaseField], label: str) -> Any:
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
            return matches[0]
        if get_origin(element_type) is list:
            args = get_args(element_type)
            if len(args) != 1:
                msg = (
                    f"{label}.{attr_name}: Requires list[T] needs 1 arg, "
                    f"got {len(args)}"
                )
                raise InvalidCheckSignatureError(msg)
            field_type = args[0]
            matches = [f for f in fields if isinstance(f, field_type)]
            if len(matches) == 0:
                raise MissingRequiredFieldError(
                    label=label,
                    param_name=attr_name,
                    field_type=field_type.__name__,
                )
            return matches
        msg = (
            f"{label}.{attr_name}: Requires wants Field|list[Field], "
            f"got {element_type!r}"
        )
        raise InvalidCheckSignatureError(msg)


@dataclass(frozen=True, slots=True)
class OptionalDep[T]:
    field_type: type[T]

    def resolve(self, attr_name: str, fields: Iterable[BaseField], label: str) -> Any:
        element_type = self.field_type
        if isinstance(element_type, type):
            field_type = element_type
            matches = [f for f in fields if isinstance(f, field_type)]
            if len(matches) == 0:
                return None
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise MultiplyRequiredFieldError(
                    label, attr_name, field_type.__name__, count=len(matches)
                )
        elif get_origin(element_type) is list:
            args = get_args(element_type)
            if len(args) != 1:
                msg = (
                    f"{label}.{attr_name}: OptionalDep list[T] needs 1 arg, "
                    f"got {len(args)}"
                )
                raise InvalidCheckSignatureError(msg)
            field_type = args[0]
            matches = [f for f in fields if isinstance(f, field_type)]
            if len(matches) == 0:
                return []
            if len(matches) >= 1:
                return matches
        else:
            msg = (
                f"{label}.{attr_name}: OptionalDep wants Field|list[Field], "
                f"got {element_type!r}"
            )
            raise InvalidCheckSignatureError(msg)
        return None


class CheckServices(Protocol):
    check_position_compliance_service: IPositionsComplianceService
    check_transcription_compliance_service: ITranscriptionComplianceService


@dataclass(kw_only=True)
class PipelineCheckServices:
    check_position_compliance_service: IPositionsComplianceService
    check_transcription_compliance_service: ITranscriptionComplianceService
