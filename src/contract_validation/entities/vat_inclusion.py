from enum import StrEnum


class VatInclusion(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNSPECIFIED = "unspecified"
    MIXED = "mixed"
