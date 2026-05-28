import os
from decimal import Decimal
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Europe/Moscow")
AMOUNT_TOLERANCE = Decimal(os.getenv("VALIDATION_AMOUNT_TOLERANCE", "1"))
