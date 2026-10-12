import functools
from typing import Any, Callable

from logging_config import setup_logging

logger = setup_logging()


def log_action(action: str, verbose: bool = False) -> Callable:
    """Декоратор логирования доменных операций (BUY, SELL).

    Логирует контекст и результат (OK/ERROR) на уровне INFO. Не подавляет
    исключения.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            from core.usecases import get_session

            # Разбор аргументов: (user_id, currency, amount) или (currency, amount)
            if len(args) >= 3:
                user_ident = args[0]
                currency = args[1]
                amount = args[2]
            elif len(args) == 2:
                user_ident = get_session() or "anonymous"
                currency = args[0]
                amount = args[1]
            else:
                user_ident = (
                    kwargs.get("user_id") or get_session() or "anonymous"
                )
                currency = (
                    kwargs.get("currency")
                    or kwargs.get("currency_code")
                    or "UNKNOWN"
                )
                amount = kwargs.get("amount", 0.0)

            prec = 4 if str(currency).upper() in ["BTC", "ETH"] else 2
            formatted_amount = (
                f"{float(amount):.{prec}f}"
                if isinstance(amount, (int, float))
                else str(amount)
            )

            try:
                result = func(*args, **kwargs)

                rate = result.get("rate")
                rate_str = (
                    f" rate={rate:.2f} base='USD'" if rate is not None else ""
                )

                details_str = ""
                if (
                    verbose
                    and "old_balance" in result
                    and "new_balance" in result
                ):
                    old_b = result["old_balance"]
                    new_b = result["new_balance"]
                    details_str = (
                        f" details='balance: {old_b:.{prec}f} -> {new_b:.{prec}f}'"
                    )

                msg = (
                    f"{action.upper()} user='{user_ident}' currency='{currency}' "
                    f"amount={formatted_amount}{rate_str} result=OK{details_str}"
                )
                logger.info(msg)
                return result

            except Exception as exc:
                err_type = type(exc).__name__
                err_msg = str(exc).replace("'", '"')
                msg = (
                    f"{action.upper()} user='{user_ident}' currency='{currency}' "
                    f"amount={formatted_amount} result=ERROR "
                    f"error_type={err_type} error_message='{err_msg}'"
                )
                logger.info(msg)
                raise exc

        return wrapper

    return decorator