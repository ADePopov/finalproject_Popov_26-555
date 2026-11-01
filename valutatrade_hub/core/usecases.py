import hashlib
import json
import os
from datetime import datetime
from typing import Any

from core.currencies import get_currency
from core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
)
from core.models import Portfolio, Wallet
from decorators import log_action
from infra.settings import SettingsLoader

settings = SettingsLoader()

users_filepath = settings.get("users_file")
portfolios_filepath = settings.get("portfolios_file")
session_filepath = settings.get("session_file")
rates_filepath = settings.get("rates_file")

# Базовые курсы (используются для расчётов и первичной инициализации кэша)
DEFAULT_RATES = {
    "USD": 1.0,
    "EUR": 1.07,
    "BTC": 59300.0,
    "ETH": 3720.0,
    "RUB": 0.01016,
}



# Безопасное хранилище JSON (чтение/запись)

def _read_json(filepath: str, default: Any = None) -> Any:
    """Безопасно считывает данные из JSON-файла.

    Args:
        filepath: Абсолютный или относительный путь к файлу.
        default: Значение по умолчанию, если файл не найден или повреждён.

    Returns:
        Десериализованные данные (list, dict) или значение default.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []


def _write_json(filepath: str, data: Any) -> None:
    """Атомарно записывает данные в JSON-файл через временный буфер.

    Исключает повреждение файла при аварийном завершении процесса.

    Args:
        filepath: Путь к целевому файлу.
        data: Сериализуемые данные.
    """
    temp_filepath = f"{filepath}.tmp"
    with open(temp_filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_filepath, filepath)



# Управление сессией и авторизацией

def hash_password(password: str, salt: str) -> str:
    """Вычисляет односторонний SHA-256 хэш пароля с солью.

    Args:
        password: Сырой пароль пользователя.
        salt: Уникальная случайная соль в шестнадцатеричном формате.

    Returns:
        Строка шестнадцатеричного хэша.
    """
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def save_session(username: str) -> None:
    """Фиксирует имя текущего авторизованного пользователя в сессионном файле.

    Args:
        username: Имя пользователя для сохранения.
    """
    _write_json(session_filepath, {"current_user": username})


def get_session() -> str | None:
    """Получает имя текущего активного пользователя из файла сессии.

    Returns:
        Имя пользователя (str) или None, если сессия отсутствует или повреждена.
    """
    data = _read_json(session_filepath, default={})
    return data.get("current_user")


def logout() -> None:
    """Завершает текущую сессию пользователя, удаляя файл session.json."""
    if os.path.exists(session_filepath):
        os.remove(session_filepath)


def _get_user_by_username(username: str) -> dict:
    """Находит запись пользователя в users.json по его логину.

    Args:
        username: Имя пользователя.

    Returns:
        Словарь с данными пользователя (user_id, salt, hashed_password и др.).

    Raises:
        ValueError: Если пользователь с таким именем отсутствует в базе.
    """
    users = _read_json(users_filepath, default=[])
    user = next((u for u in users if u.get("username") == username), None)
    if not user:
        raise ValueError(f"Пользователь '{username}' не найден")
    return user


def _get_user_by_id(user_id: int) -> dict:
    """Находит запись пользователя в users.json по числовому идентификатору.

    Args:
        user_id: Уникальный ID пользователя.

    Returns:
        Словарь с данными пользователя.

    Raises:
        ValueError: Если пользователь с указанным ID отсутствует.
    """
    users = _read_json(users_filepath, default=[])
    user = next((u for u in users if u.get("user_id") == user_id), None)
    if not user:
        raise ValueError(f"Пользователь с id={user_id} не найден")
    return user


def register(username: str, password: str) -> str:
    """Регистрирует нового пользователя и создаёт для него пустой портфель.

    Args:
        username: Уникальное имя пользователя (не пустое).
        password: Сырой пароль (длина не менее 4 символов).

    Returns:
        Текстовое сообщение об успешной регистрации с указанием назначенного ID.

    Raises:
        ValueError: Если имя пустое, пароль короче 4 символов или имя уже занято.
    """
    if not username:
        raise ValueError("Имя пользователя не может быть пустым")
    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    users = _read_json(users_filepath, default=[])
    for user in users:
        if user.get("username") == username:
            raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = max([u.get("user_id", 0) for u in users], default=0) + 1
    salt = os.urandom(16).hex()
    hash_pass = hash_password(password, salt)

    users.append({
        "user_id": user_id,
        "username": username,
        "hashed_password": hash_pass,
        "salt": salt,
        "registration_date": datetime.now().isoformat(),
    })
    _write_json(users_filepath, users)

    portfolios = _read_json(portfolios_filepath, default=[])
    portfolios.append({"user_id": user_id, "wallets": {}})
    _write_json(portfolios_filepath, portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован (id={user_id}).\n"
        f"Войдите: login --username {username} --password ****"
    )


def login(username: str, password: str) -> str:
    """Аутентифицирует пользователя по паролю и открывает новую сессию.

    Args:
        username: Имя пользователя.
        password: Введённый пароль.

    Returns:
        Текстовое подтверждение успешного входа.

    Raises:
        ValueError: Если логин/пароль пусты, пользователь не найден или пароль неверен.
    """
    if not username:
        raise ValueError("Имя пользователя не может быть пустым")
    if not password:
        raise ValueError("Пароль не может быть пустым")

    user = _get_user_by_username(username)
    salt = user.get("salt", "")
    if hash_password(password, salt) != user.get("hashed_password"):
        raise ValueError("Неверный пароль")

    save_session(username)
    return f"Вы вошли как '{username}'"



# Работа с курсами и проверка TTL

def _get_rates_cache() -> dict:
    """Возвращает кэшированные курсы валют из rates.json.

    Если файл не найден, инициализирует его первичными значениями.

    Returns:
        Словарь со структурой кэша котировок и метаданными обновления.
    """
    rates_data = _read_json(rates_filepath, default=None)
    if rates_data is None:
        rates_data = _refresh_rates_cache()
    return rates_data


def _refresh_rates_cache() -> dict:
    """Перезаписывает rates.json свежими котировками и обновляет отметку времени.

    Returns:
        Обновлённый словарь котировок.
    """
    now_iso = datetime.now().isoformat()
    new_cache = {
        "EUR_USD": {"rate": DEFAULT_RATES["EUR"], "updated_at": now_iso},
        "BTC_USD": {"rate": DEFAULT_RATES["BTC"], "updated_at": now_iso},
        "RUB_USD": {"rate": DEFAULT_RATES["RUB"], "updated_at": now_iso},
        "ETH_USD": {"rate": DEFAULT_RATES["ETH"], "updated_at": now_iso},
        "source": "LocalCacheStub",
        "last_refresh": now_iso,
    }
    _write_json(rates_filepath, new_cache)
    return new_cache


def _is_rate_fresh(updated_at_str: str) -> bool:
    """Проверяет актуальность метки времени по отношению к порогу rates_ttl_seconds.

    Args:
        updated_at_str: Метка времени в формате ISO.

    Returns:
        True, если возраст записи не превышает лимит TTL, иначе False.
    """
    try:
        updated_time = datetime.fromisoformat(updated_at_str)
        elapsed_seconds = (datetime.now() - updated_time).total_seconds()
        ttl = settings.get("rates_ttl_seconds", 300)
        return elapsed_seconds <= ttl
    except (ValueError, TypeError):
        return False



# Доменные операции: buy, sell, get_rate, portfolio

def get_user_portfolio_data(username: str, base_currency: str = "USD") -> dict:
    """Собирает данные портфеля пользователя и пересчитывает балансы в базовую валюту.

    Args:
        username: Имя пользователя, чей портфель запрашивается.
        base_currency: Тикер базовой валюты для оценки (по умолчанию 'USD').

    Returns:
        Словарь с детализацией по кошелькам (список detailed_wallets),
        общей стоимостью (total_value) и кодом базы (base_currency).

    Raises:
        CurrencyNotFoundError: Если указана неизвестная базовая валюта.
        ValueError: Если пользователь не найден в системе.
    """
    base_obj = get_currency(base_currency)
    base = base_obj.code

    user = _get_user_by_username(username)
    user_id = user["user_id"]

    portfolios = _read_json(portfolios_filepath, default=[])
    user_portfolio = next((p for p in portfolios if p.get("user_id") == user_id), None)
    if not user_portfolio or not user_portfolio.get("wallets"):
        return {"wallets": [], "total_value": 0.0, "base_currency": base}

    wallets_dict = {}
    for code, w_data in user_portfolio["wallets"].items():
        wallets_dict[code] = Wallet(
            currency_code=code, balance=w_data.get("balance", 0.0)
        )

    portfolio = Portfolio(user_id=user_id, wallets=wallets_dict)

    if base not in DEFAULT_RATES:
        raise CurrencyNotFoundError(base)

    base_rate = DEFAULT_RATES[base]
    detailed_wallets = []
    total_value = 0.0

    for code, wallet in portfolio.wallets.items():
        if code not in DEFAULT_RATES:
            raise CurrencyNotFoundError(code)

        rate = DEFAULT_RATES[code]
        val_in_base = (wallet.balance * rate) / base_rate
        total_value += val_in_base

        detailed_wallets.append({
            "currency": code,
            "balance": wallet.balance,
            "value_in_base": val_in_base,
        })

    return {
        "wallets": detailed_wallets,
        "total_value": total_value,
        "base_currency": base,
    }


@log_action(action="BUY", verbose=True)
def buy(arg1: Any, arg2: Any, arg3: float | None = None) -> dict:
    """Выполняет покупку валюты с пополнением баланса кошелька.

    Поддерживает две сигнатуры вызова:
      1. buy(currency_code, amount) — вызов из интерфейса CLI 
      (пользователь берётся из сессии).
      2. buy(user_id, currency_code, amount) — вызов программно или из автотестов.

    Args:
        arg1: Тикер валюты (str) при 2 аргументах, 
        либо user_id (int) при 3 аргументах.
        arg2: Сумма покупки (float) при 2 аргументах, 
        либо тикер валюты (str) при 3 аргументах.
        arg3: Сумма покупки (float) при вызове с 3 аргументами, иначе None.

    Returns:
        Словарь с параметрами сделки: currency, amount, rate, old_balance,
        new_balance, estimated_cost и display_info.

    Raises:
        ValueError: Если пользователь не авторизован или сумма неположительна.
        CurrencyNotFoundError: Если передан неизвестный тикер валюты.
    """
    if arg3 is not None:
        user_id = int(arg1)
        currency_code = str(arg2)
        amount = float(arg3)
    else:
        currency_code = str(arg1)
        amount = float(arg2)
        username = get_session()
        if not username:
            raise ValueError("Сначала выполните login")
        user = _get_user_by_username(username)
        user_id = user["user_id"]

    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    # Валидация валюты через иерархию (бросает CurrencyNotFoundError)
    curr_obj = get_currency(currency_code)
    code = curr_obj.code

    if code not in DEFAULT_RATES:
        raise CurrencyNotFoundError(code)

    portfolios = _read_json(portfolios_filepath, default=[])
    user_portfolio = next((p for p in portfolios if p.get("user_id") == user_id), None)
    if not user_portfolio:
        user_portfolio = {"user_id": user_id, "wallets": {}}
        portfolios.append(user_portfolio)

    wallets_data = user_portfolio.setdefault("wallets", {})

    # Автосоздание кошелька и пополнение через метод Wallet.deposit()
    curr_wallet_data = wallets_data.get(code, {})
    wallet = Wallet(currency_code=code, balance=curr_wallet_data.get("balance", 0.0))
    old_balance = wallet.balance

    wallet.deposit(amount)
    wallets_data[code] = {"balance": wallet.balance}

    _write_json(portfolios_filepath, portfolios)

    rate = DEFAULT_RATES[code]
    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "estimated_cost": amount * rate,
        "display_info": curr_obj.get_display_info(),
    }


@log_action(action="SELL", verbose=True)
def sell(arg1: Any, arg2: Any, arg3: float | None = None) -> dict:
    """Выполняет продажу валюты со списанием средств с кошелька.

    Поддерживает две сигнатуры вызова:
      1. sell(currency_code, amount) — вызов из интерфейса CLI 
      (пользователь берётся из сессии).
      2. sell(user_id, currency_code, amount) — вызов программно или из автотестов.

    Args:
        arg1: Тикер валюты (str) при 2 аргументах, 
        либо user_id (int) при 3 аргументах.
        arg2: Сумма продажи (float) при 2 аргументах, 
        либо тикер валюты (str) при 3 аргументах.
        arg3: Сумма продажи (float) при вызове с 3 аргументами, иначе None.

    Returns:
        Словарь с параметрами сделки: currency, amount, rate, old_balance,
        new_balance, estimated_revenue и display_info.

    Raises:
        ValueError: Если пользователь не авторизован, 
        сумма неположительна или кошелёк не существует.
        InsufficientFundsError: Если запрашиваемая сумма превышает доступный остаток.
        CurrencyNotFoundError: Если передан неизвестный тикер валюты.
    """
    if arg3 is not None:
        user_id = int(arg1)
        currency_code = str(arg2)
        amount = float(arg3)
    else:
        currency_code = str(arg1)
        amount = float(arg2)
        username = get_session()
        if not username:
            raise ValueError("Сначала выполните login")
        user = _get_user_by_username(username)
        user_id = user["user_id"]

    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    # Валидация валюты через иерархию (бросает CurrencyNotFoundError)
    curr_obj = get_currency(currency_code)
    code = curr_obj.code

    if code not in DEFAULT_RATES:
        raise CurrencyNotFoundError(code)

    portfolios = _read_json(portfolios_filepath, default=[])
    user_portfolio = next((p for p in portfolios if p.get("user_id") == user_id), None)
    wallets_data = user_portfolio.get("wallets", {}) if user_portfolio else {}

    if code not in wallets_data:
        raise ValueError(
            f"У вас нет кошелька '{code}'.\n"
            "Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    # Списание через метод Wallet.withdraw()(InsufficientFundsError при нехватке)
    wallet = Wallet(currency_code=code, balance=wallets_data[code].get("balance", 0.0))
    old_balance = wallet.balance

    wallet.withdraw(amount)
    wallets_data[code]["balance"] = wallet.balance

    _write_json(portfolios_filepath, portfolios)

    rate = DEFAULT_RATES[code]
    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "old_balance": old_balance,
        "new_balance": wallet.balance,
        "estimated_revenue": amount * rate,
        "display_info": curr_obj.get_display_info(),
    }


def get_rate(from_code: str, to_code: str) -> dict:
    """Вычисляет прямой и обратный курс между двумя валютами.

    Проверяет валидность валют через иерархию и контролирует актуальность кэша (TTL).

    Args:
        from_code: Код исходной валюты.
        to_code: Код целевой валюты.

    Returns:
        Словарь с курсами: from, to, rate, reverse_rate, updated_at, from_info, to_info.

    Raises:
        CurrencyNotFoundError: Если хотя бы одна валюта неизвестна реестру.
        ApiRequestError: Если кэш устарел и при попытке его обновления произошла ошибка.
    """
    from_obj = get_currency(from_code)
    to_obj = get_currency(to_code)
    c_from = from_obj.code
    c_to = to_obj.code

    if c_from not in DEFAULT_RATES or c_to not in DEFAULT_RATES:
        raise CurrencyNotFoundError(f"{c_from}→{c_to}")

    rates_cache = _get_rates_cache()
    last_refresh = rates_cache.get("last_refresh")

    # если кэш устарел, пробуем обновить
    if not last_refresh or not _is_rate_fresh(last_refresh):
        try:
            rates_cache = _refresh_rates_cache()
        except Exception as exc:
            raise ApiRequestError(f"Не удалось обновить кэш котировок: {exc}")

    rate = DEFAULT_RATES[c_from] / DEFAULT_RATES[c_to]
    reverse_rate = DEFAULT_RATES[c_to] / DEFAULT_RATES[c_from]
    updated_at = rates_cache.get(
        "last_refresh", datetime.now().isoformat()
    ).replace("T", " ")

    return {
        "from": c_from,
        "to": c_to,
        "rate": rate,
        "reverse_rate": reverse_rate,
        "updated_at": updated_at,
        "from_info": from_obj.get_display_info(),
        "to_info": to_obj.get_display_info(),
    }

def show_rates_data(currency: str = None, top: int = None, base: str = None) -> dict:
    """Собирает и фильтрует курсы валют из локального кэша."""
    rates_cache = _read_json(rates_filepath, default={})
    pairs = rates_cache.get("pairs", {})
    last_refresh = rates_cache.get("last_refresh", "")

    if not pairs:
        raise ValueError(
            "Локальный кеш курсов пуст.\n" 
            "Выполните 'update-rates', чтобы загрузить данные."
        )

    if currency:
        currency = currency.upper().strip()
        pairs = {k: v for k, v in pairs.items() if k.startswith(f"{currency}_")}
        if not pairs:
            raise ValueError(f"Курс для '{currency}' не найден в кеше.")

    if base:
        base = base.upper().strip()
        base_pair = f"{base}_USD"
        if base != "USD":
            if base_pair not in rates_cache.get("pairs", {}):
                raise ValueError(f"Базовая валюта '{base}' не найдена в кеше.")
            base_rate_to_usd = rates_cache["pairs"][base_pair]["rate"]
            
            new_pairs = {}
            for k, v in pairs.items():
                c_from, c_to = k.split("_")
                if c_to == "USD" and c_from != base:
                    recalc_rate = v["rate"] / base_rate_to_usd
                    new_pairs[f"{c_from}_{base}"] = {
                        "rate": recalc_rate, 
                        "updated_at": v["updated_at"]
                    }
            pairs = new_pairs

    if top:
        sorted_items = sorted(pairs.items(), key=lambda x: x[1]["rate"], reverse=True)
        pairs = dict(sorted_items[:top])
    else:
        pairs = dict(sorted(pairs.items()))

    return {
        "last_refresh": last_refresh,
        "pairs": pairs
    }