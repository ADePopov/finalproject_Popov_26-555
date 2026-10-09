class ValutaTradeError(Exception):
    """Базовое исключение для проекта ValutaTrade Hub."""
    pass


class InsufficientFundsError(ValutaTradeError):
    """Выбрасывается при нехватке средств для списания или продажи."""

    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code.upper()
        prec = 4 if self.code in ["BTC", "ETH"] else 2
        super().__init__(
            f"Недостаточно средств: доступно {available:.{prec}f} {self.code}, требуется {required:.{prec}f} {self.code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    """Выбрасывается, если валюта не найдена в реестре или среди доступных котировок."""

    def __init__(self, code: str):
        self.code = str(code).upper()
        super().__init__(f"Неизвестная валюта '{self.code}'")


class ApiRequestError(ValutaTradeError):
    """Выбрасывается при сбое сетевого запроса или парсинга внешнего API."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")