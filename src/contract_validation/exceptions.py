class UnknownHandlerTypeError(Exception):
    pass


class IMCPExtractionError(Exception):
    pass


class IMCPNotFoundError(IMCPExtractionError):
    pass


class UnsupportedSheetResultError(IMCPExtractionError):
    pass
