import logging
from datetime import datetime, timezone
from typing import List

from core.exceptions import ApiRequestError
from parser_service.api_clients import BaseApiClient
from parser_service.storage import Storage

logger = logging.getLogger("actions_logger")


class RatesUpdater:
    """Модуль координации сбора и обновления котировок."""
    
    def __init__(self, clients: List[BaseApiClient], storage: Storage):
        self.clients = clients
        self.storage = storage

    def run_update(self, target_source: str = None) -> tuple[int, str, bool]:
        """Последовательно опрашивает API, формирует данные и сохраняет их."""
        print("INFO: Starting rates update...")
        logger.info("Starting rates update...")
        
        snapshot = self.storage.read_rates()
        pairs = snapshot.get("pairs", {})
        
        history_records = []
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        total_updated = 0
        has_errors = False
        
        for client in self.clients:
            # Фильтрация по флагу --source из CLI
            if target_source and target_source.lower() not in client.source_name.lower():
                continue
                
            try:
                rates = client.fetch_rates()
                count = len(rates)
                
                print(f"INFO: Fetching from {client.source_name}... OK ({count} rates)")
                logger.info(f"Fetching from {client.source_name}... OK ({count} rates)")
                
                for pair_key, rate in rates.items():
                    # Формат для rates.json
                    pairs[pair_key] = {
                        "rate": rate,
                        "updated_at": now_iso,
                        "source": client.source_name
                    }
                    
                    # Формат для exchange_rates.json
                    from_curr, to_curr = pair_key.split("_")
                    history_records.append({
                        "id": f"{from_curr}_{to_curr}_{now_iso}",
                        "from_currency": from_curr,
                        "to_currency": to_curr,
                        "rate": rate,
                        "timestamp": now_iso,
                        "source": client.source_name,
                        "meta": {}
                    })
                    total_updated += 1
                    
            except ApiRequestError as e:
                # Отказоустойчивость: продолжаем работу с другими клиентами
                print(f"ERROR: Failed to fetch from {client.source_name}: {e.reason}")
                logger.error(f"Failed to fetch from {client.source_name}: {e.reason}")
                has_errors = True
                
        snapshot["pairs"] = pairs
        snapshot["last_refresh"] = now_iso
        
        if total_updated > 0:
            print(f"INFO: Writing {total_updated} rates to {self.storage.rates_path}...")
            logger.info(f"Writing {total_updated} rates to {self.storage.rates_path}...")
            self.storage.save_rates(snapshot, history_records)
            
        return total_updated, now_iso, has_errors