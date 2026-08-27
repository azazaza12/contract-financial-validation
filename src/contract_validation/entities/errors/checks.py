from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from warnings import deprecated

from app.domain.entities.amount_comparison import AmountOperand
from app.domain.entities.vat_inclusion import VatInclusion

from .base import BaseContractError


@dataclass
class BaseCheckError(BaseContractError):
    kind = "check"


@dataclass
class AmountNotFoundError(BaseCheckError):
    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("AmountNotFoundError", error)
        return self.source == other.source


@dataclass
class AmountNotPositiveError(BaseCheckError):
    value: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("AmountNotPositiveError", error)
        return self.source == other.source and self.value == other.value


@dataclass
class VatAmountNotPositiveError(BaseCheckError):
    value: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("VatAmountNotPositiveError", error)
        return self.source == other.source and self.value == other.value


@dataclass
class VatRateNotPositiveError(BaseCheckError):
    value: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("VatRateNotPositiveError", error)
        return self.source == other.source and self.value == other.value


@dataclass
class PaymentVatRateNotFoundError(BaseCheckError):
    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PaymentVatRateNotFoundError", error)
        return self.source == other.source


@dataclass
class PaymentVatRatesDifferError(BaseCheckError):
    index: int | None
    rate_one: Decimal | None
    rate_two: Decimal | None

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PaymentVatRatesDifferError", error)
        return (
            self.source == other.source
            and self.index == other.index
            and self.rate_one == other.rate_one
            and self.rate_two == other.rate_two
        )


@dataclass
class PaymentAmountPercentDiscrepancyError(BaseCheckError):
    amount: Decimal
    expected_amount: Decimal
    percent: Decimal
    contract_total_amount: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PaymentAmountPercentDiscrepancyError", error)
        return (
            self.source == other.source
            and self.amount == other.amount
            and self.expected_amount == other.expected_amount
            and self.percent == other.percent
            and self.contract_total_amount == other.contract_total_amount
        )


@dataclass
class BaseAmountDiscrepancyError(BaseCheckError):
    value: Decimal
    reference_value: Decimal
    difference: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("BaseAmountDiscrepancyError", error)
        return (
            self.source == other.source
            and self.value == other.value
            and self.reference_value == other.reference_value
            and self.difference == other.difference
        )


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

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("VatAmountCalculationDiscrepancyError", error)
        return (
            self.source == other.source
            and self.amount == other.amount
            and self.rate == other.rate
            and self.include_vat == other.include_vat
            and self.expected_vat_amount == other.expected_vat_amount
            and self.vat_amount == other.vat_amount
            and self.difference == other.difference
        )


@dataclass
class PaymentPercentSumDiscrepancyError(BaseCheckError):
    total_percent: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PaymentPercentSumDiscrepancyError", error)
        return self.source == other.source and self.total_percent == other.total_percent


@dataclass
class PositionCostDiscrepancyError(BaseCheckError):
    count: int
    position_name: str | None
    quantity: Decimal
    unit_price: Decimal
    cost: Decimal
    calculated_cost: Decimal
    difference_sum: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PositionCostDiscrepancyError", error)
        return (
            self.source == other.source
            and self.count == other.count
            and self.position_name == other.position_name
            and self.quantity == other.quantity
            and self.unit_price == other.unit_price
            and self.cost == other.cost
            and self.calculated_cost == other.calculated_cost
            and self.difference_sum == other.difference_sum
        )


@dataclass
class PositionsAmountDiscrepancyError(BaseAmountDiscrepancyError):
    pass


@dataclass
class BaseNormalizedAmountDiscrepancyError(BaseAmountDiscrepancyError):
    target_inclusion: VatInclusion
    operands: tuple[AmountOperand, ...]
    reference_operand: AmountOperand

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("BaseNormalizedAmountDiscrepancyError", error)
        return (
            super()._compare_same_type(error)
            and self.target_inclusion == other.target_inclusion
            and self.operands == other.operands
            and self.reference_operand == other.reference_operand
        )


@dataclass
class BoundAmountError(BaseCheckError, ABC):
    value: Decimal
    bound_value: Decimal
    violation_value: Decimal

    def _compare_bound_amount_error(self, error: BaseContractError) -> bool:
        other = cast("BoundAmountError", error)
        return (
            self.source == other.source
            and self.value == other.value
            and self.bound_value == other.bound_value
            and self.violation_value == other.violation_value
        )

    @abstractmethod
    def _compare_same_type(self, error: BaseContractError) -> bool: ...


@dataclass
class UpperBoundAmountError(BoundAmountError):
    target_inclusion: VatInclusion | None
    operands: tuple[AmountOperand, ...]
    reference_operand: AmountOperand | None

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("UpperBoundAmountError", error)
        return (
            self._compare_bound_amount_error(error)
            and self.target_inclusion == other.target_inclusion
            and self.operands == other.operands
            and self.reference_operand == other.reference_operand
        )


@dataclass
class UpperBoundVatAmountError(BoundAmountError):
    def _compare_same_type(self, error: BaseContractError) -> bool:
        return self._compare_bound_amount_error(error)

class TaxesAmountDiscrepancyError(BaseNormalizedAmountDiscrepancyError):
    pass


@dataclass
class AdvanceAmountDiscrepancyError(BaseNormalizedAmountDiscrepancyError):
    pass


@dataclass
class PositionsComplianceError(BaseCheckError):
    message: str

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PositionsComplianceError", error)
        return self.source == other.source and self.message == other.message


@dataclass
class NumberTranscriptionError(BaseCheckError):
    index: int
    value: Decimal
    transcription: str
    expected_transcription: str

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("NumberTranscriptionError", error)
        return (
            self.source == other.source
            and self.index == other.index
            and self.value == other.value
            and self.transcription == other.transcription
            and self.expected_transcription == other.expected_transcription
        )
