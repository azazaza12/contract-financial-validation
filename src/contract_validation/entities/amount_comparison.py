from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .vat_inclusion import VatInclusion


class ComparisonStatus(StrEnum):
    OK = "ok"
    NOT_OK = "not_ok"
    UNKNOWN = "unknown"


@dataclass(frozen=True, kw_only=True)
class ComparisonResult[TDiscrepancy]:
    status: ComparisonStatus
    discrepancy: TDiscrepancy | None = None

    def __post_init__(self) -> None:
        has_discrepancy = self.discrepancy is not None
        if (self.status is ComparisonStatus.NOT_OK) != has_discrepancy:
            msg = "only a NOT_OK comparison may contain a discrepancy"
            raise ValueError(msg)


@dataclass(frozen=True, kw_only=True)
class AmountOperand:
    value: Decimal
    vat_amount: Decimal | None
    vat_rate: Decimal | None
    vat_inclusion: VatInclusion


@dataclass(frozen=True, kw_only=True)
class AmountDiscrepancy:
    value: Decimal
    reference_value: Decimal
    difference: Decimal


class AmountRelation(StrEnum):
    EXACT = "exact"
    AT_MOST = "at_most"

    def compare(
        self,
        actual_value: Decimal | None,
        reference_value: Decimal | None,
        *,
        tolerance: Decimal,
    ) -> ComparisonResult[AmountDiscrepancy]:
        if actual_value is None or reference_value is None:
            return ComparisonResult(status=ComparisonStatus.UNKNOWN)

        raw_difference = actual_value - reference_value
        match self:
            case AmountRelation.EXACT:
                difference = abs(raw_difference)
            case AmountRelation.AT_MOST:
                difference = raw_difference

        if difference <= tolerance:
            return ComparisonResult(status=ComparisonStatus.OK)

        return ComparisonResult(
            status=ComparisonStatus.NOT_OK,
            discrepancy=AmountDiscrepancy(
                value=actual_value,
                reference_value=reference_value,
                difference=difference,
            ),
        )


@dataclass(frozen=True, kw_only=True)
class NormalizedAmountDiscrepancy(AmountDiscrepancy):
    target_inclusion: VatInclusion
    operands: tuple[AmountOperand, ...]
    reference_operand: AmountOperand


@dataclass(frozen=True, kw_only=True)
class PaymentComparison:
    amount: ComparisonResult[NormalizedAmountDiscrepancy]
    vat_amount: ComparisonResult[AmountDiscrepancy]

    @classmethod
    def unknown(cls) -> PaymentComparison:
        return cls(
            amount=ComparisonResult(status=ComparisonStatus.UNKNOWN),
            vat_amount=ComparisonResult(status=ComparisonStatus.UNKNOWN),
        )
