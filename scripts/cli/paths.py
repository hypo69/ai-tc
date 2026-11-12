# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli - Paths
# =============================================================================
# Description:
#   Кроссплатформенная система управления путями для Windows, Linux и macOS.
#
# Usage Examples:
#   Python API:
#     from scripts.cli.paths import CrossPlatformPaths
#
#     service = CrossPlatformPaths()
#
# File: paths.py
# Project: ai-windows-admin
# Package: scripts.cli
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:14:00
# =============================================================================

"""Кроссплатформенная система управления путями.

Автоматически определяет корректные системные директории для Windows, Linux и macOS
с учетом переменных окружения и config.json.
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import platformdirs
    HAS_PLATFORMDIRS = True
except ImportError:
    HAS_PLATFORMDIRS = False


class CrossPlatformPaths:
    """Централизованная система путей для всех платформ.

    Использует:
    - Windows: %LOCALAPPDATA%, %APPDATA%, %USERPROFILE%
    - Linux/macOS: ~/.local/share, ~/.config, ~/.cache
    """

    def __init__(self, app_name: Optional[str] = None, app_author: str = 'hypo69'):
        """Инициализирует кроссплатформенные пути.

        Args:
            app_name: Название приложения (по умолчанию определяется из APP_NAME или config.json).
            app_author: Автор приложения.
        """
        self._project_root = self._find_project_root()
        if not app_name:
            app_name = self._resolve_app_name()
        self.app_name = app_name
        self.app_author = app_author
        self._cache = {}

    def _resolve_app_name(self) -> str:
        """Определяет название приложения из окружения или config.json."""
        env_name = os.environ.get('APP_NAME')
        if env_name:
            return env_name
        cfg_file = self._project_root / 'config.json'
        if cfg_file.is_file():
            try:
                import json
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    name = (
                        cfg.get('app_name')
                        or (cfg.get('app', {}).get('app_name') if isinstance(cfg.get('app'), dict) else None)
                        or (cfg.get('app', {}).get('name') if isinstance(cfg.get('app'), dict) else None)
                    )
                    if name:
                        return str(name)
            except Exception:
                pass
        return self._project_root.name or 'AI-Assistant'

    @staticmethod
    def _find_project_root() -> Path:
        """Находит корень проекта по наличию main.py или config.json.

        Returns:
            Путь к корню проекта.
        """
        current = Path(__file__).parent
        for _ in range(10):
            if (current / 'main.py').exists() or (current / 'config.json').exists():
                return current
            current = current.parent
        return Path(
            os.environ.get(
                'AITC_DIR',
                os.environ.get('AI_TC_DIR', os.environ.get('AIWINDOWSADMIN_DIR', os.getcwd())),
            )
        )

    @property
    def project_root(self) -> Path:
        """Корневой каталог проекта."""
        return self._project_root

    @property
    def data_dir(self) -> Path:
        """Каталог данных приложения.

        Windows: %LOCALAPPDATA%\\<app_name>
        Linux: ~/.local/share/<app_name>
        macOS: ~/Library/Application Support/<app_name>
        """
        if HAS_PLATFORMDIRS:
            return Path(platformdirs.user_data_dir(self.app_name, self.app_author))
        if sys.platform == 'win32':
            base = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
            candidate = Path(base) / self.app_name / 'data'
            if candidate.exists():
                return candidate
            return Path(base) / self.app_name
        elif sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Application Support' / self.app_name
        else:
            return Path.home() / '.local' / 'share' / self.app_name

    @property
    def internal_data_dir(self) -> Path:
        """Внутренняя директория data в корне проекта или %LOCALAPPDATA%\\<app_name>\\data."""
        root_data = self.project_root / 'data'
        if root_data.exists():
            return root_data
        return self.data_dir / 'data'

    @property
    def logs_dir(self) -> Path:
        """Директория логов в %APPDATA%\\<app_name>\\logs."""
        if sys.platform == 'win32':
            base = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
            return Path(base) / self.app_name / 'logs'
        return self.data_dir / 'logs'

    @property
    def tmp_dir(self) -> Path:
        """Директория временных файлов в %APPDATA%\\<app_name>\\tmp."""
        if sys.platform == 'win32':
            base = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
            return Path(base) / self.app_name / 'tmp'
        return self.data_dir / 'tmp'

    @property
    def config_dir(self) -> Path:
        """Каталог конфигурации."""
        if HAS_PLATFORMDIRS:
            return Path(platformdirs.user_config_dir(self.app_name, self.app_author))
        if sys.platform == 'win32':
            return self.data_dir / 'config'
        elif sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Preferences' / self.app_name
        else:
            return Path.home() / '.config' / self.app_name

    @property
    def cache_dir(self) -> Path:
        """Каталог кэша."""
        if HAS_PLATFORMDIRS:
            return Path(platformdirs.user_cache_dir(self.app_name, self.app_author))
        if sys.platform == 'win32':
            return self.data_dir / 'Cache'
        elif sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Caches' / self.app_name
        else:
            return Path.home() / '.cache' / self.app_name

    @property
    def certs_dir(self) -> Path:
        """Каталог SSL-сертификатов."""
        if sys.platform == 'win32':
            return Path.home() / '.certs'
        elif sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Certs'
        else:
            return Path.home() / '.local' / 'share' / 'ca-certificates'

    @property
    def certs_user_dir(self) -> Path:
        """Альтернативный пользовательский каталог сертификатов."""
        return Path.home() / '.certs'

    @property
    def bin_dir(self) -> Path:
        """Каталог исполняемых файлов."""
        return Path.home() / '.local' / 'bin'

    @property
    def venv_dir(self) -> Path:
        """Каталог виртуального окружения Python."""
        return self.project_root / 'venv'

    @property
    def venv_python(self) -> Path:
        """Интерпретатор Python в виртуальном окружении."""
        if sys.platform == 'win32':
            return self.venv_dir / 'Scripts' / 'python.exe'
        else:
            return self.venv_dir / 'bin' / 'python'

    @property
    def secrets_dir(self) -> Path:
        """Каталог секретов и API-ключей."""
        return self.project_root / 'src' / 'secrets'

    @property
    def env_file(self) -> Path:
        """Путь к файлу .env."""
        return self.project_root / '.env'

    @property
    def config_file(self) -> Path:
        """Путь к файлу config.json."""
        return self.project_root / 'config.json'

    @property
    def requirements_main(self) -> Path:
        """Основной файл requirements.txt."""
        return self.project_root / 'requirements.txt'

    @property
    def requirements_core(self) -> Path:
        """Базовый файл зависимостей."""
        return self.project_root / 'install' / 'req' / 'requirements-core.txt'

    @property
    def requirements_ai(self) -> Path:
        """Файл AI-зависимостей."""
        return self.project_root / 'install' / 'req' / 'requirements-ai.txt'

    @property
    def requirements_test(self) -> Path:
        """Файл тестовых зависимостей."""
        return self.project_root / 'install' / 'req' / 'requirements-test.txt'

    @property
    def requirements_docs(self) -> Path:
        """Файл зависимостей документации."""
        return self.project_root / 'install' / 'req' / 'requirements-docs.txt'

    def get_env_vars(self) -> dict:
        """Возвращает словарь необходимых переменных окружения."""
        return {
            'AITC_DIR': str(self.project_root),
            'AIWINDOWSADMIN_DIR': str(self.project_root),
            'ASSIST_DIR': str(self.project_root),
            'PYTHONUTF8': '1',
            'PYTHONPATH': f"{self.project_root}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
        }

    def setup_env(self) -> None:
        """Устанавливает переменные окружения."""
        for key, value in self.get_env_vars().items():
            if value:
                os.environ[key] = value

    def ensure_dirs(self) -> None:
        """Создает необходимые рабочие директории."""
        dirs = [
            self.data_dir,
            self.internal_data_dir,
            self.logs_dir,
            self.tmp_dir,
            self.config_dir,
            self.cache_dir,
            self.certs_dir,
            self.certs_user_dir,
            self.bin_dir,
            self.secrets_dir,
        ]
        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)


_paths_instance: Optional[CrossPlatformPaths] = None


def get_paths() -> CrossPlatformPaths:
    """Возвращает глобальный экземпляр CrossPlatformPaths."""
    global _paths_instance
    if _paths_instance is None:
        _paths_instance = CrossPlatformPaths()
    return _paths_instance


def init_paths() -> CrossPlatformPaths:
    """Инициализирует пути и переменные окружения."""
    paths = get_paths()
    paths.setup_env()
    paths.ensure_dirs()
    return paths
