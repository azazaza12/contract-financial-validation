from app.domain.entities.errors.base import BaseContractError
from app.domain.entities.errors.benchmark_matcher import match_benchmark_errors
from app.domain.entities.errors.checks import (
    AmountDiscrepancyError,
    AmountNotFoundError,
    AmountNotPositiveError,
    BaseCheckError,
    NumberTranscriptionError,
    PaymentAmountPercentDiscrepancyError,
    PaymentPercentSumDiscrepancyError,
    PaymentVatRateNotFoundError,
    PaymentVatRatesDifferError,
    PositionCostDiscrepancyError,
    PositionsComplianceError,
    VatAmountCalculationDiscrepancyError,
    VatAmountDiscrepancyError,
    VatAmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.errors.match_result import BenchmarkMatchResult
from app.domain.entities.errors.merge import (
    BaseMergeError,
    ValueNotDefinedError,
    ValuesDiscrepancyError,
)


__all__ = [
    "AmountDiscrepancyError",
    "AmountNotFoundError",
    "AmountNotPositiveError",
    "BaseCheckError",
    "BaseContractError",
    "BaseMergeError",
    "BenchmarkMatchResult",
    "NumberTranscriptionError",
    "PaymentAmountPercentDiscrepancyError",
    "PaymentPercentSumDiscrepancyError",
    "PaymentVatRateNotFoundError",
    "PaymentVatRatesDifferError",
    "PositionCostDiscrepancyError",
    "PositionsComplianceError",
    "ValueNotDefinedError",
    "ValuesDiscrepancyError",
    "VatAmountCalculationDiscrepancyError",
    "VatAmountDiscrepancyError",
    "VatAmountNotPositiveError",
    "VatRateNotPositiveError",
    "match_benchmark_errors",
]
