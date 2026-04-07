from pydantic import BaseModel, computed_field


class BaseContractError(BaseModel):
    source: str = ""

    @computed_field
    @property
    def error_type(self) -> str:
        return type(self).__name__
