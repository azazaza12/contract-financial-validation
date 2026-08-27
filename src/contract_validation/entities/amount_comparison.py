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
class NormalizedAmountContext:
    target_inclusion: VatInclusion
    operands: tuple[AmountOperand, ...]
    reference_operand: AmountOperand


@dataclass(frozen=True, kw_only=True)
class AmountDiscrepancy:
    value: Decimal
    reference_value: Decimal
    difference: Decimal


@dataclass(frozen=True, kw_only=True)
class NormalizedAmountDiscrepancy(AmountDiscrepancy):
    normalized_context: NormalizedAmountContext


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
