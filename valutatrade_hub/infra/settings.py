import os
from typing import Any


class SettingsLoader:
    """
    Singleton для централизованного хранения конфигурации и путей проекта.
    Гарантирует существование строго одного объекта в памяти приложения.
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # Выделение памяти под единственный экземпляр
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Защита от повторной перезаписи при каждом вызове SettingsLoader()
        if self._initialized:
            return

        self._settings: dict[str, Any] = {}
        self.reload()
        self._initialized = True

    def reload(self) -> None:
        """Загружает или сбрасывает настройки до базовых конфигурационных значений."""
        # Вычисление абсолютного корня проекта 
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        data_dir = os.path.join(project_root, "data")

        os.makedirs(data_dir, exist_ok=True)

        self._settings = {
            "project_root": project_root,
            "data_dir": data_dir,
            "users_file": os.path.join(data_dir, "users.json"),
            "portfolios_file": os.path.join(data_dir, "portfolios.json"),
            "rates_file": os.path.join(data_dir, "rates.json"),
            "session_file": os.path.join(data_dir, "session.json"),
            "rates_ttl_seconds": 300,
            "default_base_currency": "USD",
            "log_file": os.path.join(project_root, "valutatrade.log"),
            "log_format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Возвращает значение параметра по ключу.
        Если ключ отсутствует, возвращает default.
        """
        return self._settings.get(key, default)