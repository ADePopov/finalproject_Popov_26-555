from abc import ABC, abstractmethod

from core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактный базовый класс валюты."""

    name: str
    code: str

    def __init__(self, name: str, code: str):
        # Валидация code: верхний регистр, 2-5 символов, без пробелов
        if (
            not isinstance(code, str)
            or not code.isupper()
            or not (2 <= len(code) <= 5)
            or " " in code
        ):
            raise ValueError(
                "Код валюты должен быть в верхнем регистре,\n"
                "содержать от 2 до 5 символов и не иметь пробелов"
            )

        # Валидация name: не пустая строка
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Имя валюты не может быть пустым")

        self.name = name.strip()
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для интерфейса и логов."""
        pass


class FiatCurrency(Currency):
    """Класс фиатной валюты."""

    issuing_country: str

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name=name, code=code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна/зона эмиссии не может быть пустой")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Класс криптовалюты."""

    algorithm: str
    market_cap: float

    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float = 0.0
    ):
        super().__init__(name=name, code=code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError(
                "Рыночная капитализация должна быть неотрицательным числом"
            )

        self.algorithm = algorithm.strip()
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        # Приведение к компактной экспоненциальной записи (например, 1.12e12)
        mcap_formatted = f"{self.market_cap:.2e}".replace("+0", "").replace("+", "")
        return (
            f"[CRYPTO] {self.code} — {self.name}\n"
            f"(Algo: {self.algorithm}, MCAP: {mcap_formatted})"
        )


# Базовый реестр валют платформы
_CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency(
        name="US Dollar",
        code="USD",
        issuing_country="United States"
    ),
    "EUR": FiatCurrency(
        name="Euro",
        code="EUR",
        issuing_country="Eurozone"
    ),
    "RUB": FiatCurrency(
        name="Russian Ruble",
        code="RUB",
        issuing_country="Russia"
    ),
    "BTC": CryptoCurrency(
        name="Bitcoin",
        code="BTC",
        algorithm="SHA-256",
        market_cap=1.12e12
    ),
    "ETH": CryptoCurrency(
        name="Ethereum",
        code="ETH",
        algorithm="Ethash",
        market_cap=4.50e11
    ),
}


def get_currency(code: str) -> Currency:
    """
    Фабричная функция для получения объекта валюты по её коду.
    Бросает CurrencyNotFoundError, если код не найден в реестре.
    """
    if not isinstance(code, str):
        raise CurrencyNotFoundError("Код валюты должен быть строкой")

    normalized_code = code.upper().strip()
    currency = _CURRENCY_REGISTRY.get(normalized_code)

    if not currency:
        raise CurrencyNotFoundError(normalized_code)

    return currency