# contract-validation

Доменная библиотека финансовых проверок для документов закупки: контроль
сумм, НДС, авансов, спецификаций и верхних границ цены.

Библиотека не зависит от веб-фреймворка, брокера сообщений и базы данных —
только стандартная библиотека Python. Интеграция делается через порты
(`ports/`), которые реализует вызывающее приложение.

## Задача

В закупочном документе одни и те же суммы повторяются в разных местах:
итог договора, спецификация, график платежей, авансы, строки НДС, сумма
прописью. Эти значения часто расходятся: округления, разные базы НДС
(«в том числе» против «кроме того»), проценты аванса, не совпадающие с
фактическими суммами.

Библиотека формализует такие расхождения как набор независимых проверок,
каждая из которых возвращает структурированные ошибки с указанием места
в документе, а не текстовое сообщение.

## Устройство

```
src/contract_validation/
├── entities/        финансовые модели: Money, Vat, Payment, TotalAmount,
│                    Specification, поля с привязкой к источникам
├── checks/          проверки + механизм объявления зависимостей
├── merge/           слияние значений из нескольких документов
└── ports/           интерфейсы к внешним сервисам
```

### Финансовые модели

`Money`, `Vat`, `Payment` и `TotalAmount` — неизменяемые датаклассы с
арифметикой на `Decimal`. `Payment` знает собственный режим НДС
(`VatInclusion`: `INCLUDED`, `EXCLUDED`, `UNSPECIFIED`, `MIXED`), поэтому
суммы с разной базой приводятся к общему виду до сравнения, а не
складываются напрямую.

`AmountRelation` задаёт отношение сравнения (`EXACT`, `AT_MOST`) и
возвращает `ComparisonResult` — тип, который по конструкции не может
содержать расхождение при успешном статусе:

```python
@dataclass(frozen=True, kw_only=True)
class ComparisonResult[TDiscrepancy]:
    status: ComparisonStatus
    discrepancy: TDiscrepancy | None = None

    def __post_init__(self) -> None:
        has_discrepancy = self.discrepancy is not None
        if (self.status is ComparisonStatus.NOT_OK) != has_discrepancy:
            msg = "only a NOT_OK comparison may contain a discrepancy"
            raise ValueError(msg)
```

### Объявление зависимостей проверки

Проверка объявляет нужные поля декларативно. `Requires` требует ровно одно
поле данного типа, `OptionalDep` допускает отсутствие:

```python
class CheckTotalAmountsValidation(BaseCheck):
    total_amount_field = Requires(TotalAmountField)
    advance_payments_field = OptionalDep(AdvancePaymentsField)
```

`prepare()` разрешает эти объявления по набору извлечённых полей. Если
обязательного поля нет или их несколько, поднимается
`MissingRequiredFieldError` или `MultiplyRequiredFieldError` с указанием
имени параметра и типа — вызывающий код отличает «нет данных для проверки»
от «проверка не прошла».

Поддерживается и `list[Field]`: объявление `Requires(list[TaxField])`
собирает все подходящие поля.

### Ошибки с привязкой к месту в документе

Каждое поле хранит `sources` — список документов и заголовков, откуда
значение извлечено. Ошибка несёт `FieldLocation` с именем поля и путём
внутри него, поэтому расхождение можно показать пользователю в контексте:

```python
@dataclass(frozen=True, kw_only=True)
class FieldLocation:
    field_name: str
    path: str
    sources: tuple[Source, ...]
```

Иерархия ошибок типизирована: `BaseAmountDiscrepancyError` несёт значение,
эталон и разницу; `BaseNormalizedAmountDiscrepancyError` дополнительно —
операнды и целевой режим НДС, то есть сохраняет, из чего именно сложилась
сумма и к какой базе её приводили.

### Слияние значений из нескольких документов

Когда одно поле встречается в нескольких документах, `MergeRegistry`
выбирает обработчик по типу значения: скаляр, строка, список, датаклассы —
рекурсивно по полям. Расхождения собираются в `ValuesDiscrepancyError` с
точным путём (`value.vat.rate`), а не теряются.

Сравнение `Decimal` идёт с допуском, строки нормализуются (регистр,
пробелы, `ё`/`е`), для платежей действуют специальные обработчики, которые
учитывают режим НДС.

## Состав проверок

| Проверка | Что контролирует |
| --- | --- |
| `CheckTotalAmountsValidation` | сумма строк НДС и авансов против итога договора |
| `CheckPriceValidation` | расчёт стоимости позиций и их сумма против итога |
| `CheckVatCalculation` | НДС по формуле для указанной ставки и базы |
| `CheckTotalAmountUpperBoundVatCalculation` | то же для предельной цены |
| `CheckTaxRatesValidation` | согласованность ставок НДС между платежами |
| `CheckPaymentPercentValidation` | проценты авансов и их суммы |
| `CheckValuesValidation` | положительность сумм, ставок и сумм НДС |
| `CheckTotalAmountUpperBound` | итог договора против предельной цены |
| `CheckNumberTranscriptionRub` | сумма прописью против числового значения |

## Пример

```python
from decimal import Decimal

from contract_validation.checks.check_price_validation import CheckPriceValidation
from contract_validation.entities import FieldCollector

check = CheckPriceValidation(tolerance=Decimal("1"))
check.prepare(FieldCollector([spec_positions_field, total_amount_field]))
result = await check.execute()

for error in result.errors:
    print(error.error_type, error.location)
```

## Разработка

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy src
```

Требуется Python 3.14. 263 теста, `mypy --strict` без замечаний.

## Происхождение кода и авторство

Код выделен из закрытого проекта автоматизации проверки закупочной
документации. Перенесена история коммитов только тех файлов, которые
относятся к этому модулю, поэтому в `git log` присутствуют и другие
участники проекта — их авторство сохранено как есть, коммиты не переписаны.

Это командный код, не единоличный. По `git blame` на текущем срезе:

| Автор | Строк | Доля |
| --- | --- | --- |
| Azaliya Khakimullina (владелец репозитория) | 6141 | 73,7% |
| Contributor A | 1544 | 18,5% |
| Contributor B | 218 | 2,6% |
| Contributor C | 9 | 0,1% |
| выделение в библиотеку (без коммита) | 421 | 5,1% |

Моя часть — финансовые модели и арифметика с режимами НДС
(`entities/contract_fields.py`, 93%), механизм объявления зависимостей
проверок (`checks/deps.py`, 83%), большинство самих проверок и их тестов,
обработчики слияния платежей.

Написано преимущественно коллегами и включено здесь только потому, что без
него модуль не работает: `entities/field.py` (базовое поле и коллектор),
`entities/errors/base.py`, `entities/errors/merge.py`, `checks/errors.py`,
`entities/validation.py`, `checks/services.py`, `ports/`. Модуль `merge/`
и `entities/errors/checks.py` — совместная работа примерно пополам.

При выделении удалены привязки к инфраструктуре исходного приложения
(pipeline, репозитории, брокер сообщений, корпоративное логирование),
тестовая обвязка переписана на прямой вызов проверок, данные в тестах
заменены синтетическими.

## Условия использования

Репозиторий опубликован как демонстрация инженерных решений и подхода к
проектированию, а не как библиотека для повторного использования.

Файл лицензии отсутствует намеренно: исключительные права на исходный
проект принадлежат заказчику, часть строк написана другими участниками
команды. Разрешение на копирование, изменение и распространение этого кода
не предоставляется.
