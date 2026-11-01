import hashlib
import os
from datetime import datetime

from core.exceptions import InsufficientFundsError


class User:
    """
    пользователь системы
    """
    _user_id: int
    _username: str
    _hashed_password: str
    _salt: str
    _registration_date: datetime

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime
    ):
        self._user_id = user_id
        self.username = username 
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not value:
            raise ValueError('Имя не может быть пустым')
        self._username = value

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    @property
    def password(self):
        raise AttributeError('Пароль нельзя прочитать')

    @password.setter
    def password(self, raw_pass: str) -> None:
        if len(raw_pass) < 4:
            raise ValueError('Пароль должен состоять из 4+ символов')
        self.change_password(raw_pass)


    def get_user_info(self) -> dict:
        """
        Выводит информацию о пользователе
        """
        return {
            'user_id': self._user_id,
            'username': self._username,
            'registration_date': self._registration_date.isoformat()
        }


    def change_password(self, new_password: str) -> None:
        """
        Изменяет пароль пользователя и хэширует его с новой солью.
        """
        self._salt = os.urandom(16).hex()
        password_bytes = (new_password + self._salt).encode('utf-8')
        self._hashed_password = hashlib.sha256(password_bytes).hexdigest()

    def verify_password(self, password: str) -> bool:
        """
        Проверяет введенный пароль
        """
        password_byt = (password + self._salt).encode('utf-8')
        hash_pass = hashlib.sha256(password_byt).hexdigest()
        return hash_pass == self._hashed_password

class Wallet:
    """
    кошелёк пользователя для одной конкретной валюты
    """
    currency_code: str
    _balance: float

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise ValueError('Необходимый тип данных - число (float)')
        
        if value < 0:
            raise InsufficientFundsError(
                available=self.balance,
                required=abs(value), 
                code=self.currency_code
            )
        
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """
        Зачисляет денежные средства на баланс
        """
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError('Сумма пополнения должна быть положительным числом')
        
        self.balance = self.balance + amount
        
    def get_balance_info(self) -> float:
        return self._balance

    def withdraw(self, amount: float) -> None:
        """Списание денежных средств с баланса."""
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Сумма снятия должна быть положительным числом")

        if self.balance - amount < 0:
            raise InsufficientFundsError(
                available=self.balance,
                required=amount,
                code=self.currency_code
            )
        self.balance = self.balance - amount

class Portfolio:
    """
    управление всеми кошельками одного пользователя
    """
    _user_id: int
    _wallets: dict[str, Wallet]

    exchange_rates = {
        "USD": 1.0,
        "BTC": 60000.0,
        "EUR": 1.1
    }

    def __init__(self, user_id: int, wallets: dict[str, Wallet]):
        self._user_id = user_id
        self._wallets = wallets.copy() if wallets else {}

    @property
    def user(self) -> int:
        """
        Возвращает объект пользователя 
        """
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """
        Возвращает копию словаря кошельков 
        (чтобы нельзя было изменить извне)
        """
        return self._wallets.copy()
    
    def add_currency(self, currency_code: str) -> None:
        """
        Создает новый кошелек и добавляет его в портфель.
        """
        if currency_code in self._wallets:
            raise ValueError(f"Кошелек {currency_code} уже существует в портфеле")
        self._wallets[currency_code] = Wallet(currency_code, 0.0)

    def get_wallet(self, currency_code: str) -> Wallet:
        """
        Возвращает объект Wallet по коду валюты.
        """
        if currency_code not in self._wallets:
            raise ValueError(f"Кошелек {currency_code} не найден в портфеле")
        return self._wallets[currency_code]

    def get_total_value(self, base_currency: str = 'USD') -> float:
        """
        Возвращает общую стоимость всех валют пользователя в указанной базовой валюте.
        """
        if base_currency not in self.exchange_rates:
            raise ValueError(f"Нет курса для базовой валюты {base_currency}")

        total_value = 0.0
        base_rate = self.exchange_rates[base_currency]

        for currency, wallet in self._wallets.items():
            if currency not in self.exchange_rates:
                raise ValueError(f"Нет курса для валюты {currency}")
            
            currency_rate = self.exchange_rates[currency]
            
            wallet_value_in_base = (wallet.balance * currency_rate) / base_rate
            
            total_value += wallet_value_in_base
            
        return total_value

