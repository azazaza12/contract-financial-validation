class UnknownHandlerTypeError(Exception):
    pass


class IMCPExtractionError(Exception):
    pass


class AnchorAmountNotFoundError(IMCPExtractionError):
    pass


class IMCPNotFoundError(IMCPExtractionError):
    pass


class UnsupportedSheetResultError(IMCPExtractionError):
    pass
