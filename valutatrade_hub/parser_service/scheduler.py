import time
import logging
from parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from parser_service.storage import Storage
from parser_service.updater import RatesUpdater
from parser_service.config import ParserConfig

logger = logging.getLogger("actions_logger")


def run_scheduler(interval_seconds: int = 3600):
    """
    Бесконечный цикл для автоматического обновления курсов.
    По умолчанию запускается раз в час (3600 секунд).
    """
    config = ParserConfig()
    storage = Storage(config)
    clients = [CoinGeckoClient(), ExchangeRateApiClient()]
    updater = RatesUpdater(clients, storage)

    print(f"Запуск планировщика обновлений (интервал: {interval_seconds} сек). Для остановки нажмите Ctrl+C.")
    logger.info(f"Scheduler started with interval {interval_seconds}s")

    try:
        while True:
            updated, last_refresh, has_errors = updater.run_update()
            
            if has_errors:
                print(f"[{last_refresh}] Обновление завершено с ошибками. Следующий запуск через {interval_seconds} сек.")
            else:
                print(f"[{last_refresh}] Успешно обновлено {updated} курсов. Следующий запуск через {interval_seconds} сек.")
                
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        print("\nОстановка планировщика...")
        logger.info("Scheduler stopped by user.")