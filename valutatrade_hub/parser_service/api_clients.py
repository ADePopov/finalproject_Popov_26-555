from abc import ABC, abstractmethod

import requests
from core.exceptions import ApiRequestError
from parser_service.config import ParserConfig

config = ParserConfig()


class BaseApiClient(ABC):
    """Абстрактный класс для работы с внешними API курсов валют."""
    source_name: str

    @abstractmethod
    def fetch_rates(self) -> dict:
        """Получает курсы и приводит их к стандартизированному формату."""
        pass


class CoinGeckoClient(BaseApiClient):
    """Клиент для получения курсов криптовалют из CoinGecko API."""
    source_name = "CoinGecko"

    def fetch_rates(self) -> dict:
        ids = ",".join(config.CRYPTO_ID_MAP.values())
        vs_curr = config.BASE_CURRENCY.lower()
        url = f"{config.COINGECKO_URL}?ids={ids}&vs_currencies={vs_curr}"
        
        try:
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            result = {}
            id_to_ticker = {v: k for k, v in config.CRYPTO_ID_MAP.items()}
            
            for crypto_id, rates in data.items():
                if crypto_id in id_to_ticker:
                    ticker = id_to_ticker[crypto_id]
                    pair_key = f"{ticker}_{config.BASE_CURRENCY}"
                    result[pair_key] = float(rates.get(vs_curr, 0.0))
                    
            return result
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Network error: {e}")


class ExchangeRateApiClient(BaseApiClient):
    """Клиент для получения курсов фиатных валют из ExchangeRate-API."""
    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> dict:
        if not config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                "Не задан ключ EXCHANGERATE_API_KEY\n"
                "в переменных окружения"
            )
            
        url = (f"{config.EXCHANGERATE_API_URL}/"
               f"{config.EXCHANGERATE_API_KEY}/"
               f"latest/{config.BASE_CURRENCY}")
        
        try:
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            result = {}
            rates = data.get("conversion_rates", data.get("rates", {}))
            
            for fiat in config.FIAT_CURRENCIES:
                if fiat in rates:
                    pair_key = f"{fiat}_{config.BASE_CURRENCY}"
                    result[pair_key] = float(rates[fiat])
                    
            return result
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"Network error: {e}")