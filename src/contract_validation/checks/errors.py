class CheckInputError(Exception):
    pass


class MissingRequiredFieldError(CheckInputError):
    def __init__(self, check_name: str, param_name: str, field_type: str) -> None:
        super().__init__(
            f"{check_name}: missing required field for '{param_name}' {field_type}",
        )
        self.check_name = check_name
        self.param_name = param_name
        self.field_type = field_type


class MultiplyRequiredFieldError(CheckInputError):
    def __init__(
        self, check_name: str, param_name: str, field_type: str, count: int
    ) -> None:
        super().__init__(
            f"{check_name}: collision for '{param_name}' ({field_type}), count={count}",
        )
        self.check_name = check_name
        self.param_name = param_name
        self.field_type = field_type
        self.count = count


class InvalidCheckSignatureError(Exception):
    pass
