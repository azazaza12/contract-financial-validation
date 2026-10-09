import os
from decimal import Decimal


# Documents round amounts differently, so comparisons allow a small absolute
# difference. One currency unit matches the rounding used in procurement forms.
AMOUNT_TOLERANCE = Decimal(os.getenv("VALIDATION_AMOUNT_TOLERANCE", "1"))
