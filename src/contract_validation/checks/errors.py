class CheckInputError(Exception):
    pass


class MissingRequiredFieldError(CheckInputError):
    def __init__(self, label: str, param_name: str, field_type: str) -> None:
        super().__init__(
            f"{label}: missing required field for '{param_name}' {field_type}"
        )
        self.label = label
        self.param_name = param_name
        self.field_type = field_type


class MultiplyRequiredFieldError(CheckInputError):
    def __init__(
        self, label: str, param_name: str, field_type: str, count: int
    ) -> None:
        super().__init__(
            f"{label}: collision for '{param_name}' ({field_type}), count={count}"
        )
        self.label = label
        self.param_name = param_name
        self.field_type = field_type
        self.count = count


class InsufficientCheckDataError(CheckInputError):
    def __init__(self, label: str, reason: str) -> None:
        super().__init__(f"{label}: insufficient data — {reason}")
        self.label = label
        self.reason = reason


class InvalidCheckSignatureError(Exception):
    pass
