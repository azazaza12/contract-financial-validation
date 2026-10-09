from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from warnings import deprecated

from contract_validation.entities.amount_comparison import AmountOperand
from contract_validation.entities.field_location import FieldLocation
from contract_validation.entities.vat_inclusion import VatInclusion

from .base import BaseContractError


@dataclass
class BaseCheckError(BaseContractError):
    kind = "check"


@dataclass(kw_only=True)
class LocatedCheckError(BaseCheckError):
    location: FieldLocation | None = None


@dataclass
class AmountNotFoundError(BaseCheckError):
    pass


@dataclass
class AmountNotPositiveError(LocatedCheckError):
    value: Decimal


@dataclass
class VatAmountNotPositiveError(LocatedCheckError):
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
class BaseAmountDiscrepancyError(BaseCheckError):
    value: Decimal
    reference_value: Decimal
    difference: Decimal


@deprecated(
    "Use a context-specific amount discrepancy error instead.",
    category=None,
)
@dataclass
class AmountDiscrepancyError(BaseAmountDiscrepancyError):
    pass


@deprecated(
    "Use a context-specific VAT amount discrepancy error instead.",
    category=None,
)
@dataclass
class VatAmountDiscrepancyError(BaseAmountDiscrepancyError):
    pass


@dataclass
class TaxesVatAmountDiscrepancyError(BaseAmountDiscrepancyError):
    pass


@dataclass
class AdvanceVatAmountDiscrepancyError(BaseAmountDiscrepancyError):
    pass


@dataclass
class VatAmountCalculationDiscrepancyError(BaseCheckError):
    amount: Decimal
    rate: Decimal
    include_vat: bool
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
    quantity: Decimal
    unit_price: Decimal
    cost: Decimal
    calculated_cost: Decimal
    difference_sum: Decimal


@dataclass
class PositionsAmountDiscrepancyError(BaseAmountDiscrepancyError):
    pass


@dataclass
class BaseNormalizedAmountDiscrepancyError(BaseAmountDiscrepancyError):
    target_inclusion: VatInclusion
    operands: tuple[AmountOperand, ...]
    reference_operand: AmountOperand


@dataclass
class BaseBoundAmountError(BaseCheckError, ABC):
    value: Decimal
    bound_value: Decimal
    violation_value: Decimal

    def _compare_bound_amount_error(self, error: BaseContractError) -> bool:
        other = cast("BaseBoundAmountError", error)
        return (
            self.source == other.source
            and self.value == other.value
            and self.bound_value == other.bound_value
            and self.violation_value == other.violation_value
        )

    @abstractmethod
    def _compare_same_type(self, error: BaseContractError) -> bool: ...


@dataclass
class UpperBoundAmountError(BaseBoundAmountError):
    target_inclusion: VatInclusion
    operands: tuple[AmountOperand, ...]
    reference_operand: AmountOperand

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("UpperBoundAmountError", error)
        return (
            self._compare_bound_amount_error(error)
            and self.target_inclusion == other.target_inclusion
            and self.operands == other.operands
            and self.reference_operand == other.reference_operand
        )


@dataclass
class UpperBoundVatAmountError(BaseBoundAmountError):
    def _compare_same_type(self, error: BaseContractError) -> bool:
        return self._compare_bound_amount_error(error)


@dataclass
class TaxesAmountDiscrepancyError(BaseNormalizedAmountDiscrepancyError):
    pass


@dataclass
class AdvanceAmountDiscrepancyError(BaseNormalizedAmountDiscrepancyError):
    pass


@dataclass
class PositionsComplianceError(BaseCheckError):
    message: str


@dataclass
class NumberTranscriptionError(LocatedCheckError):
    index: int
    value: Decimal
    transcription: str
    expected_transcription: str
