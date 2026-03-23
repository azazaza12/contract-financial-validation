import logging

from app.domain.entities.validation_errors import NumberTranscriptionErrorCheckResult
from app.domain.checks.base import BaseCheck
from app.domain.entities.validation import CheckExecutionResult, BaseResultChecker
from app.domain.entities.single_supplier import (
    AdvancePaymentsField,
    Amount,
    Payment,
    TotalAmountField,
)
from app.domain.pipeline.task import Context


logger = logging.getLogger(__name__)


class CheckNumberTranscriptionRub(BaseCheck):
    def __init__(self, ctx: Context):
        super().__init__()
        self.ctx = ctx

    @staticmethod
    def _amounts_from_payment(payment: Payment) -> list[Amount]:
        out: list[Amount] = []
        if payment.amount is not None:
            out.append(payment.amount)
        if payment.vat.amount is not None:
            out.append(payment.vat.amount)
        return out

    def _extract_amounts_from_fields(
        self,
        fields: list[TotalAmountField | AdvancePaymentsField],
    ) -> list[Amount]:
        amounts: list[Amount] = []
        for field in fields:
            if isinstance(field, TotalAmountField):
                total_amount = field.value
                amounts.extend(self._amounts_from_payment(total_amount.total))
                if total_amount.taxes is not None:
                    for tax_payment in total_amount.taxes:
                        amounts.extend(self._amounts_from_payment(tax_payment))
            elif isinstance(field, AdvancePaymentsField):
                for adv in field.value:
                    if adv.total is not None:
                        amounts.extend(self._amounts_from_payment(adv.total))
                    if adv.payments is not None:
                        for p in adv.payments:
                            amounts.extend(self._amounts_from_payment(p))
        return amounts

    async def execute(
        self,
        total_amount_field: TotalAmountField | None,
        advance_payments_field: AdvancePaymentsField | None,
    ) -> CheckExecutionResult:
        errors: list[BaseResultChecker] = []
        extracted_pairs = self._extract_amounts_from_fields(
            [f for f in (total_amount_field, advance_payments_field) if f is not None]
        )
        result = await self.ctx.check_transcription_compliance_service.evaluate(
            extracted_pairs
        )
        for issue in result.issues:
            errors.append(
                NumberTranscriptionErrorCheckResult.model_validate(
                    issue, from_attributes=True
                )
            )
        return self._result(errors)
