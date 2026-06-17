import os
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Europe/Moscow")
AMOUNT_TOLERANCE = Decimal(os.getenv("VALIDATION_AMOUNT_TOLERANCE", "1"))
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
