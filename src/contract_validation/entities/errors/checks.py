from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from app.domain.entities.errors.base import BaseContractError


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
class VatAmountDiscrepancyError(BaseCheckError):
    value: Decimal
    reference_value: Decimal
    difference: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("VatAmountDiscrepancyError", error)
        return (
            self.source == other.source
            and self.value == other.value
            and self.reference_value == other.reference_value
            and self.difference == other.difference
        )


@dataclass
class VatAmountCalculationDiscrepancyError(BaseCheckError):
    expected_vat_amount: Decimal
    vat_amount: Decimal
    difference: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("VatAmountCalculationDiscrepancyError", error)
        return (
            self.source == other.source
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
    cost: Decimal
    calculated_cost: Decimal
    difference_sum: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("PositionCostDiscrepancyError", error)
        return (
            self.source == other.source
            and self.count == other.count
            and self.position_name == other.position_name
            and self.cost == other.cost
            and self.calculated_cost == other.calculated_cost
            and self.difference_sum == other.difference_sum
        )


@dataclass
class AmountDiscrepancyError(BaseCheckError):
    reference_value: Decimal
    value: Decimal
    difference: Decimal

    def _compare_same_type(self, error: BaseContractError) -> bool:
        other = cast("AmountDiscrepancyError", error)
        return (
            self.source == other.source
            and self.reference_value == other.reference_value
            and self.value == other.value
            and self.difference == other.difference
        )


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
