import json
import os
from typing import Any

from parser_service.config import ParserConfig


class Storage:
    def __init__(self, config: ParserConfig):
        self.rates_path = config.RATES_FILE_PATH
        self.history_path = config.HISTORY_FILE_PATH
        
    def _write_atomic(self, filepath: str, data: Any) -> None:
        """Атомарная запись во временный файл с последующим переименованием."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        temp_filepath = f"{filepath}.tmp"
        with open(temp_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_filepath, filepath)

    def read_rates(self) -> dict:
        """Читает локальный кэш курсов."""
        try:
            with open(self.rates_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"pairs": {}, "last_refresh": ""}

    def save_rates(self, snapshot: dict, history_records: list) -> None:
        """Сохраняет актуальный срез и добавляет замеры в исторический журнал."""
        # 1. Сохранение rates.json
        self._write_atomic(self.rates_path, snapshot)
        
        # 2. Сохранение exchange_rates.json
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []
            
        history.extend(history_records)
        self._write_atomic(self.history_path, history)