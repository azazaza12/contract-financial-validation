from abc import ABC
from dataclasses import dataclass

from app.domain.entities.document import BaseDocument


@dataclass
class BaseField(ABC):
    value: str
    document: BaseDocument
