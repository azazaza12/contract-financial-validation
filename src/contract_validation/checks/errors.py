class CheckInputError(Exception):
    pass


class MissingRequiredFieldError(CheckInputError):
    def __init__(self, label: str, param_name: str, field_type: str):
        super().__init__(
            f"{label}: missing required field for '{param_name}' {field_type}"
        )
        self.label = label
        self.param_name = param_name
        self.field_type = field_type


class MultiplyRequiredFieldError(CheckInputError):
    def __init__(self, label: str, param_name: str, field_type: str, count: int):
        super().__init__(
            f"{label}: collision for '{param_name}' ({field_type}), count={count}"
        )
        self.label = label
        self.param_name = param_name
        self.field_type = field_type
        self.count = count


class InvalidCheckSignatureError(Exception):
    pass
