import argparse
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from core.usecases import (
    buy,
    get_rate,
    get_session,
    get_user_portfolio_data,
    login,
    logout,
    register,
    sell,
    show_rates_data 
)


def main():
    parser = argparse.ArgumentParser(description="ValutaTrade Hub CLI")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # register
    reg_parser = subparsers.add_parser("register", help="Регистрация нового пользователя")
    reg_parser.add_argument("--username", required=True, help="Имя пользователя")
    reg_parser.add_argument("--password", required=True, help="Пароль")

    # login
    log_parser = subparsers.add_parser("login", help="Вход в систему")
    log_parser.add_argument("--username", required=True, help="Имя пользователя")
    log_parser.add_argument("--password", required=True, help="Пароль")

    # logout
    subparsers.add_parser("logout", help="Выход из системы")

    # show-portfolio
    port_parser = subparsers.add_parser("show-portfolio", help="Просмотр портфеля")
    port_parser.add_argument(
        "--base",
        default="USD",
        help="Базовая валюта для отображения (по умолчанию USD)",
    )

    # buy
    buy_parser = subparsers.add_parser("buy", help="Купить валюту")
    buy_parser.add_argument("--currency", required=True, help="Код покупаемой валюты (например, BTC)")
    buy_parser.add_argument("--amount", required=True, type=float, help="Количество валюты")

    # sell
    sell_parser = subparsers.add_parser("sell", help="Продать валюту")
    sell_parser.add_argument("--currency", required=True, help="Код продаваемой валюты")
    sell_parser.add_argument("--amount", required=True, type=float, help="Количество валюты")

    # get-rate
    rate_parser = subparsers.add_parser("get-rate", help="Получить курс валюты")
    rate_parser.add_argument("--from", dest="from_curr", required=True, help="Исходная валюта")
    rate_parser.add_argument("--to", dest="to_curr", required=True, help="Целевая валюта")

    # update-rates
    upd_parser = subparsers.add_parser("update-rates", help="Запустить немедленное обновление курсов")
    upd_parser.add_argument("--source", choices=["coingecko", "exchangerate"], help="Обновить данные только из указанного источника")

    # show-rates
    show_parser = subparsers.add_parser("show-rates", help="Показать список актуальных курсов из локального кеша")
    show_parser.add_argument("--currency", help="Показать курс только для указанной валюты")
    show_parser.add_argument("--top", type=int, help="Показать N самых дорогих криптовалют")
    show_parser.add_argument("--base", help="Показать все курсы относительно указанной базы")

    # scheduler
    sched_parser = subparsers.add_parser("scheduler", help="Запустить фоновое автообновление курсов")
    sched_parser.add_argument("--interval", type=int, default=3600, help="Интервал обновления в секундах (по умолчанию 3600)")


    args = parser.parse_args()

    if args.command == "register":
        try:
            print(register(args.username, args.password))
        except ValueError as e:
            print(e)

    elif args.command == "login":
        try:
            print(login(args.username, args.password))
        except ValueError as e:
            print(e)

    elif args.command == "logout":
        logout()
        print("Вы вышли из системы.")

    elif args.command == "show-portfolio":
        current_user = get_session()
        if not current_user:
            print("Сначала выполните login")
            return

        try:
            data = get_user_portfolio_data(current_user, base_currency=args.base)
            base = data["base_currency"]
            print(f"Портфель пользователя '{current_user}' (база: {base}):")

            if not data["wallets"]:
                print("У вас пока нет кошельков.")
            else:
                for w in data["wallets"]:
                    prec = 4 if w["currency"] in ["BTC", "ETH"] else 2
                    print(f"- {w['currency']}: {w['balance']:.{prec}f}  → {w['value_in_base']:.2f} {base}")
                print("---------------------------------")
                print(f"ИТОГО: {data['total_value']:,.2f} {base}")

        except CurrencyNotFoundError as e:
            print(f"Неизвестная базовая валюта '{args.base}'")
        except ValueError as e:
            print(e)

    elif args.command == "buy":
        try:
            res = buy(args.currency, args.amount)
            prec = 4 if res["currency"] in ["BTC", "ETH"] else 2
            print(f"Покупка выполнена: {res['amount']:.{prec}f} {res['currency']} по курсу {res['rate']:.2f} USD/{res['currency']}")
            print("Изменения в портфеле:")
            print(f"- {res['currency']}: было {res['old_balance']:.{prec}f} → стало {res['new_balance']:.{prec}f}")
            print(f"Оценочная стоимость покупки: {res['estimated_cost']:,.2f} USD")
        except CurrencyNotFoundError as e:
            print(e)
            print("Поддерживаемые валюты: USD, EUR, RUB, BTC, ETH.")
        except ValueError as e:
            print(e)

    elif args.command == "sell":
        try:
            res = sell(args.currency, args.amount)
            prec = 4 if res["currency"] in ["BTC", "ETH"] else 2
            print(f"Продажа выполнена: {res['amount']:.{prec}f} {res['currency']} по курсу {res['rate']:.2f} USD/{res['currency']}")
            print("Изменения в портфеле:")
            print(f"- {res['currency']}: было {res['old_balance']:.{prec}f} → стало {res['new_balance']:.{prec}f}")
            print(f"Оценочная выручка: {res['estimated_revenue']:,.2f} USD")
        except InsufficientFundsError as e:
            print(e)
        except CurrencyNotFoundError as e:
            print(e)
            print("Поддерживаемые валюты: USD, EUR, RUB, BTC, ETH.")
        except ValueError as e:
            print(e)

    elif args.command == "get-rate":
        try:
            res = get_rate(args.from_curr, args.to_curr)
            rate_str = f"{res['rate']:.8f}" if res["rate"] < 1 else f"{res['rate']:.4f}"
            rev_str = f"{res['reverse_rate']:.2f}" if res["reverse_rate"] >= 1 else f"{res['reverse_rate']:.8f}"
            print(f"Курс {res['from']}→{res['to']}: {rate_str} (обновлено: {res['updated_at']})")
            print(f"Обратный курс {res['to']}→{res['from']}: {rev_str}")
        except CurrencyNotFoundError:
            print(f"Курс {args.from_curr.upper()}→{args.to_curr.upper()} недоступен. Повторите попытку позже.")
        except ApiRequestError as e:
            print(e)
            print("Повторите попытку позже или проверьте сетевое подключение.")
        except ValueError as e:
            print(e)

    elif args.command == "update-rates":
        from parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
        from parser_service.storage import Storage
        from parser_service.updater import RatesUpdater
        from parser_service.config import ParserConfig
        
        config = ParserConfig()
        storage = Storage(config)
        clients = [CoinGeckoClient(), ExchangeRateApiClient()]
        updater = RatesUpdater(clients, storage)
        
        updated, last_refresh, has_errors = updater.run_update(target_source=args.source)
        
        if has_errors:
            print("Update completed with errors. Check logs/actions.log for details.")
        else:
            print(f"Update successful. Total rates updated: {updated}. Last refresh: {last_refresh}")

    elif args.command == "show-rates":
        try:
            data = show_rates_data(currency=args.currency, top=args.top, base=args.base)
            
            print(f"Rates from cache (updated at {data['last_refresh']}):")
            for pair, info in data["pairs"].items():
                print(f"- {pair}: {info['rate']:.5f}")
        except ValueError as e:
            print(e)

    elif args.command == "scheduler":
        from parser_service.scheduler import run_scheduler
        run_scheduler(interval_seconds=args.interval)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()