from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class NomenclatureArticle:
    article: str
    probability: float


class INomenclatureClassifier(ABC):
    @abstractmethod
    async def classify(self, nomenclature: str) -> list[NomenclatureArticle]:
        raise NotImplementedError
