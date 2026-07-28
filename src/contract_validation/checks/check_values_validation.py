from decimal import Decimal
from .base import BaseCheck, BaseCheckError
from .deps import Requires, OptionalDep
from app.domain.entities.single_supplier_fields import TotalAmountField, AdvancePaymentsField



class CheckValuesValidation:
    total_amount_field: Requires[TotalAmountField]
    def __init__(self, tolerance: Decimal):
        self.tolerance = tolerance