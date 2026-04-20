class UnknownHandlerTypeError(Exception):
    pass


class PipelineIsNoneError(Exception):
    pass


class ExcelExtractionError(Exception):
    pass


class ExcelAnchorAmountNotFoundError(ExcelExtractionError):
    pass


class ExcelInitialMaxContractPriceNotFoundError(ExcelExtractionError):
    pass
