from dataclasses import dataclass
from decimal import Decimal

from pydantic import TypeAdapter

from app.domain.entities.errors.base import BaseContractError


@dataclass
class BaseCheckError(BaseContractError):
    pass


@dataclass
class AmountNotFoundError(BaseCheckError):
    pass


@dataclass
class AmountNotPositiveError(BaseCheckError):
    value: Decimal


@dataclass
class VatAmountNotPositiveError(BaseCheckError):
    value: Decimal


@dataclass
class VatRateNotPositiveError(BaseCheckError):
    value: Decimal


@dataclass
class PaymentVatRateNotFoundError(BaseCheckError):
    pass


@dataclass
class PaymentVatRatesDifferError(BaseCheckError):
    index: int | None
    rate_one: Decimal | None
    rate_two: Decimal | None


@dataclass
class PaymentAmountPercentDiscrepancyError(BaseCheckError):
    amount: Decimal
    expected_amount: Decimal
    percent: Decimal
    contract_total_amount: Decimal


@dataclass
class VatAmountDiscrepancyError(BaseCheckError):
    value: Decimal
    reference_value: Decimal
    difference: Decimal


@dataclass
class VatAmountCalculationDiscrepancyError(BaseCheckError):
    expected_vat_amount: Decimal
    vat_amount: Decimal
    difference: Decimal


@dataclass
class PaymentPercentSumDiscrepancyError(BaseCheckError):
    total_percent: Decimal


@dataclass
class PositionCostDiscrepancyError(BaseCheckError):
    count: int
    position_name: str | None
    cost: Decimal
    calculated_cost: Decimal
    difference_sum: Decimal


@dataclass
class AmountDiscrepancyError(BaseCheckError):
    reference_value: Decimal
    value: Decimal
    difference: Decimal


@dataclass
class PositionsComplianceError(BaseCheckError):
    message: str


@dataclass
class NumberTranscriptionError(BaseCheckError):
    index: int
    value: Decimal
    transcription: str
    expected_transcription: str


_CHECK_ERROR_BY_TYPE: dict[str, type[BaseCheckError]] = {
    "AmountNotFoundError": AmountNotFoundError,
    "AmountNotPositiveError": AmountNotPositiveError,
    "VatAmountNotPositiveError": VatAmountNotPositiveError,
    "VatRateNotPositiveError": VatRateNotPositiveError,
    "PaymentVatRateNotFoundError": PaymentVatRateNotFoundError,
    "PaymentVatRatesDifferError": PaymentVatRatesDifferError,
    "PaymentAmountPercentDiscrepancyError": PaymentAmountPercentDiscrepancyError,
    "VatAmountDiscrepancyError": VatAmountDiscrepancyError,
    "VatAmountCalculationDiscrepancyError": VatAmountCalculationDiscrepancyError,
    "PaymentPercentSumDiscrepancyError": PaymentPercentSumDiscrepancyError,
    "PositionCostDiscrepancyError": PositionCostDiscrepancyError,
    "AmountDiscrepancyError": AmountDiscrepancyError,
    "PositionsComplianceError": PositionsComplianceError,
    "NumberTranscriptionError": NumberTranscriptionError,
}


def check_error_from_dict(data: dict) -> BaseCheckError:
    error_type = data.get("error_type")
    if error_type not in _CHECK_ERROR_BY_TYPE:
        msg = f"Unknown check error type: {error_type!r}"
        raise ValueError(msg)
    cls = _CHECK_ERROR_BY_TYPE[error_type]
    return TypeAdapter(cls).validate_python(data)
