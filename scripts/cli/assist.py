# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli - Assist
# =============================================================================
# Description:
#   Cross-platform CLI assistant for AI Windows Admin project management.
#
# Usage Examples:
#   CLI:
#     python -m scripts.cli.assist
#   Python API:
#     from scripts.cli.assist import AssistCLI
#
#     service = AssistCLI()
#
# File: assist.py
# Project: ai-windows-admin
# Package: scripts.cli
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:32:00
# =============================================================================

"""Cross-platform CLI assistant for AI Windows Admin project management.

CLI assistant providing cross-platform project management utilities,
originally ported from PowerShell assist.ps1 for Windows, Linux, macOS.

Использование:
    assist start [service]          # Запустить сервис (run, unicorn, light, foundry)
    assist stop [service]           # Остановить сервис (server, foundry, all)
    assist restart                  # Перезапустить
    assist status                   # Показать status
    assist providers                # List провайдеров ИИ
    assist logs [lines]             # Показать логи
    assist config [show|get|set]    # Работа с config.json
    assist test                     # Запустить тесты"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.cli.paths import init_paths, get_paths
from scripts.cli.config import get_config_manager
from scripts.cli.utils import get_process_on_port, kill_process, ensure_in_path, run_command, which
C_RESET = '\x1b[0m'
C_BOLD = '\x1b[1m'
C_CYAN = '\x1b[96m'
C_GREEN = '\x1b[92m'
C_YELLOW = '\x1b[93m'
C_RED = '\x1b[91m'
C_GRAY = '\x1b[90m'
C_MAGENTA = '\x1b[95m'

class AssistCLI:
    """Главный CLI class для управления AI-Windows-Admin"""

    def __init__(self):
        self.paths = init_paths()
        self.config_mgr = get_config_manager()
        self._state_dir = self.paths.data_dir / 'assist_state'
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Creates директорию состояния"""
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_file(self, name: str) -> Path:
        """Получить путь до файла состояния"""
        return self._state_dir / f'{name}.json'

    def _load_state(self, name: str) -> dict:
        """Загрузить state из файла"""
        state_file = self._get_state_file(name)
        if not state_file.exists():
            return {}
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, name: str, data: dict) -> None:
        """Сохранить state в файл"""
        self._ensure_state_dir()
        state_file = self._get_state_file(name)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def cmd_start(self, service: str='run') -> int:
        """Запустить сервис"""
        service = service.lower()
        script_map = {'run': 'launchers/run.py', 'all': 'launchers/run.py', 'unicorn': 'launchers/run_unicorn.py', 'uvicorn': 'launchers/run_unicorn.py', 'light': 'launchers/run_light_server.py', 'foundry': 'launchers/run_foundry.py'}
        script_name = script_map.get(service)
        if not script_name:
            logger.console(f"{C_RED}❌ Неизвестный сервис: '{service}'{C_RESET}")
            logger.console(f'{C_GRAY}Доступные сервисы: run, unicorn, light, foundry, all{C_RESET}')
            return 1
        script_path = self.paths.project_root / script_name
        if not script_path.exists():
            logger.console(f'{C_RED}❌ Скрипт не найден: {script_path}{C_RESET}')
            return 1
        logger.console(f'{C_CYAN}🚀 Запуск: {script_name}...{C_RESET}')
        try:
            python_exe = str(self.paths.venv_python) if self.paths.venv_python.exists() else sys.executable
            result = subprocess.run([python_exe, str(script_path)], cwd=str(self.paths.project_root), check=False)
            return result.returncode
        except Exception as e:
            logger.console(f'{C_RED}❌ Error запуска: {e}{C_RESET}')
            return 1

    def cmd_stop(self, service: str='all') -> int:
        """Остановить сервис"""
        service = service.lower()
        config = self.config_mgr.load_config()
        server_cfg = config.get('server', {})
        port = int(server_cfg.get('port', 8000))
        stopped_any = False
        if service in ('server', 'all', 'unicorn', 'uvicorn', 'light'):
            proc_info = get_process_on_port(port)
            if proc_info:
                pid, proc_name = proc_info
                logger.console(f'{C_YELLOW}⏹ Остановка сервера на порту {port} (PID: {pid}, {proc_name})...{C_RESET}')
                if kill_process(pid, force=True):
                    logger.console(f'  {C_GREEN}✔ Процесс завершен{C_RESET}')
                    stopped_any = True
                else:
                    logger.console(f'  {C_RED}✖ Не удалось завершить процесс{C_RESET}')
            else:
                logger.console(f'{C_GRAY}Порт {port} свободен (сервер не запущен){C_RESET}')
        if service in ('foundry', 'all'):
            logger.console(f'{C_YELLOW}⏹ Остановка Foundry...{C_RESET}')
            stopped_any = True
        if not stopped_any:
            logger.console(f'{C_GREEN}Все сервисы уже остановлены.{C_RESET}')
        return 0

    def cmd_restart(self) -> int:
        """Перезапустить сервисы"""
        logger.console(f'{C_CYAN}🔄 Перезапуск сервисов...{C_RESET}')
        self.cmd_stop()
        return self.cmd_start()

    def cmd_status(self) -> int:
        """Показать status"""
        config = self.config_mgr.load_config()
        server_cfg = config.get('server', {})
        port = int(server_cfg.get('port', 8000))
        use_ssl = bool(server_cfg.get('use_ssl', False))
        mode = str(server_cfg.get('mode', 'DEV'))
        reload_on = bool(server_cfg.get('reload', True))
        proto = 'https' if use_ssl else 'http'
        local_url = f'{proto}://localhost:{port}/'
        logger.console(f'\n{C_BOLD}{C_CYAN}╔═══════════════════════════════════════════════════════════════╗{C_RESET}')
        logger.console(f'{C_BOLD}{C_CYAN}║             СТАТУС AI ASSISTANT СИСТЕМЫ                       ║{C_RESET}')
        logger.console(f'{C_BOLD}{C_CYAN}╚═══════════════════════════════════════════════════════════════╝{C_RESET}\n')
        proc_info = get_process_on_port(port)
        if proc_info:
            pid, proc_name = proc_info
            logger.console(f'  {C_BOLD}FastAPI Сервер:{C_RESET}     {C_GREEN}● РАБОТАЕТ{C_RESET}')
            logger.console(f'  {C_BOLD}URL:{C_RESET}                {C_CYAN}{local_url}{C_RESET}')
            logger.console(f'  {C_BOLD}PID процесса:{C_RESET}       {pid} ({proc_name})')
        else:
            logger.console(f'  {C_BOLD}FastAPI Сервер:{C_RESET}     {C_RED}○ ОСТАНОВЛЕН{C_RESET}')
            logger.console(f'  {C_BOLD}Ожидаемый порт:{C_RESET}     {port}')
        logger.console(f"  {C_BOLD}Режим / SSL:{C_RESET}        {mode} | SSL: {('ВКЛ' if use_ssl else 'ВЫКЛ')} | Autoreload: {('ВКЛ' if reload_on else 'ВЫКЛ')}")
        ai_cfg = config.get('ai_providers_and_models_configuration') or config.get('ai', {})
        providers = ai_cfg.get('providers', {})
        foundry_prov = providers.get('foundry', {})
        use_foundry = bool(foundry_prov.get('enabled', ai_cfg.get('use_foundry', False)))
        foundry_url = str(foundry_prov.get('base_url', ai_cfg.get('foundry_base_url', 'http://localhost:54837')))
        if use_foundry:
            logger.console(f'  {C_BOLD}AI Foundry:{C_RESET}         {C_YELLOW}○ ВКЛЮЧЕН В CONFIG (внешний сервис){C_RESET}')
            logger.console(f'  {C_BOLD}URL:{C_RESET}                {foundry_url}')
        else:
            logger.console(f'  {C_BOLD}AI Foundry:{C_RESET}         {C_GRAY}○ ОТКЛЮЧЕН В CONFIG{C_RESET}')
        gemini_keys = os.getenv('GEMINI_API_KEY_NAMES', '')
        key_count = len([k for k in gemini_keys.split(',') if k.strip()])
        logger.console(f'  {C_BOLD}Gemini API Keys:{C_RESET}    {C_GREEN}{key_count} в пуле ротации{C_RESET}')
        logger.console()
        return 0

    def cmd_providers(self) -> int:
        """Показать list провайдеров"""
        config = self.config_mgr.load_config()
        ai_cfg = config.get('ai_providers_and_models_configuration') or config.get('ai', {})
        providers = ai_cfg.get('providers', {})
        logger.console(f'\n{C_BOLD}{C_CYAN}╔═══════════════════════════════════════════════════════════════════════════════════════╗{C_RESET}')
        logger.console(f'{C_BOLD}{C_CYAN}║                     РЕЕСТР ПРОВАЙДЕРОВ И МОДЕЛЕЙ ИИ                                   ║{C_RESET}')
        logger.console(f'{C_BOLD}{C_CYAN}╚═══════════════════════════════════════════════════════════════════════════════════════╝{C_RESET}\n')
        gemini_keys = os.getenv('GEMINI_API_KEY_NAMES', '')
        keys = [k.strip() for k in gemini_keys.split(',') if k.strip()]
        has_gemini = len(keys) > 0
        def_gemini_mod = providers.get('gemini', {}).get('default_model') or 'gemini-3.5-flash-lite'
        logger.console(f'{C_BOLD}{C_GREEN}1. Google Gemini API (Cloud API){C_RESET}')
        logger.console(f"   Status:          {('✅ Активен' if has_gemini else '❌ Нет ключей')}")
        logger.console(f"   Пул ключей:      {len(keys)} шт. ({(', '.join(keys) if keys else 'пусто')})")
        logger.console(f'   Дефолтная модель: {def_gemini_mod}')
        logger.console()
        gemini_cli_prov = providers.get('gemini_cli', {})
        use_gemini_cli = bool(gemini_cli_prov.get('enabled', ai_cfg.get('use_gemini_cli', True)))
        gemini_cli_model = str(gemini_cli_prov.get('default_model', ai_cfg.get('gemini_cli_model_id', 'gemini-2.5-flash')))
        logger.console(f'{C_BOLD}{C_GREEN}2. Gemini CLI (Терминальный агент){C_RESET}')
        logger.console(f"   Status:          {('✅ Включен' if use_gemini_cli else '○ Отключен')}")
        logger.console(f'   Модель:          {gemini_cli_model}')
        logger.console()
        foundry_prov = providers.get('foundry', {})
        use_foundry = bool(foundry_prov.get('enabled', ai_cfg.get('use_foundry', False)))
        foundry_model = str(foundry_prov.get('default_model', ai_cfg.get('foundry_model_id', 'qwen2.5-1.5b')))
        foundry_url = str(foundry_prov.get('base_url', ai_cfg.get('foundry_base_url', 'http://localhost:54837')))
        logger.console(f'{C_BOLD}{C_GREEN}3. Microsoft AI Foundry (Локальная LLM){C_RESET}')
        logger.console(f"   Status:          {('✅ Включен' if use_foundry else '○ Отключен')}")
        logger.console(f'   Модель:          {foundry_model}')
        logger.console(f'   Endpoint:        {foundry_url}')
        logger.console()
        ollama_prov = providers.get('ollama', {})
        use_ollama = bool(ollama_prov.get('enabled', ai_cfg.get('use_ollama', False)))
        ollama_model = str(ollama_prov.get('default_model', ai_cfg.get('ollama_model_id', 'llama3.1')))
        ollama_url = str(ollama_prov.get('base_url', ai_cfg.get('ollama_base_url', 'http://localhost:11434')))
        logger.console(f'{C_BOLD}{C_GREEN}4. Ollama Local{C_RESET}')
        logger.console(f"   Status:          {('✅ Включен' if use_ollama else '○ Отключен')}")
        logger.console(f'   Модель:          {ollama_model}')
        logger.console(f'   Endpoint:        {ollama_url}')
        logger.console()
        openai_cfg = config.get('openai_compat', {}).get('providers', {})
        if openai_cfg:
            logger.console(f'{C_BOLD}{C_GREEN}5. OpenAI-Compatible Провайдеры{C_RESET}')
            for p_name, p_info in openai_cfg.items():
                base = p_info.get('base_url', '')
                models = ', '.join(p_info.get('models', [])) or 'авто'
                logger.console(f'   • {C_BOLD}{p_name}{C_RESET}: {base}')
                logger.console(f'     Модели: {models}')
            logger.console()
        return 0

    def cmd_logs(self, lines: int=40, name: str='fastapi') -> int:
        """Показать логи"""
        try:
            from logger import logger
            logs_dir = getattr(logger, 'log_files_path', None) or (self.paths.project_root / 'logs')
        except Exception:
            logs_dir = self.paths.project_root / 'logs'
        if not logs_dir.exists() and (self.paths.project_root / 'logs').exists():
            logs_dir = self.paths.project_root / 'logs'
        if not logs_dir.exists():
            logger.console(f'{C_YELLOW}Каталог logs/ пока пуст: {logs_dir}{C_RESET}')
            return 0
        target_file = None
        if name == 'fastapi':
            target_file = logs_dir / 'fastapi.log'
        elif name == 'info':
            target_file = logs_dir / 'info.log'
        elif name == 'error' or name == 'errors':
            target_file = logs_dir / 'errors.log'
        if not target_file or not target_file.exists():
            for cand in ['fastapi.log', 'info.log', 'errors.log']:
                if (logs_dir / cand).exists():
                    target_file = logs_dir / cand
                    break
        if not target_file or not target_file.exists():
            logger.console(f'{C_YELLOW}Лог-файл не найден в {logs_dir}{C_RESET}')
            return 0
        logger.console(f'\n{C_CYAN}📄 Последние {lines} строк: {target_file.name}{C_RESET}\n' + '-' * 70)
        try:
            with open(target_file, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                for line in all_lines[-int(lines):]:
                    logger.console(line.rstrip())
        except Exception as e:
            logger.console(f'{C_RED}Error чтения логов: {e}{C_RESET}')
        logger.console('-' * 70 + '\n')
        return 0

    def cmd_config(self, subcommand: str='show', key: str='', value: str='') -> int:
        """Работа с config.json"""
        config = self.config_mgr.load_config()
        if subcommand == 'show':
            logger.console(json.dumps(config, indent=2, ensure_ascii=False))
            return 0
        if subcommand == 'get':
            if not key:
                logger.console(f'{C_RED}Укажите ключ (например: server.port){C_RESET}')
                return 1
            parts = key.split('.')
            val = config
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p, {})
                else:
                    val = None
                    break
            logger.console(f'{key} = {json.dumps(val, ensure_ascii=False)}')
            return 0
        if subcommand == 'set':
            if not key or value == '':
                logger.console(f'{C_RED}Использование: assist config set <key> <value>{C_RESET}')
                return 1
            parsed_val = value
            if value.lower() in ('true', '1', 'yes'):
                parsed_val = True
            elif value.lower() in ('false', '0', 'no'):
                parsed_val = False
            elif value.isdigit():
                parsed_val = int(value)
            parts = key.split('.')
            curr = config
            for p in parts[:-1]:
                if p not in curr or not isinstance(curr[p], dict):
                    curr[p] = {}
                curr = curr[p]
            curr[parts[-1]] = parsed_val
            if self.config_mgr.save_config(config):
                logger.console(f'{C_GREEN}✔ Обновлено: {key} = {parsed_val}{C_RESET}')
                return 0
            else:
                logger.console(f'{C_RED}✗ Error сохранения конфигурации{C_RESET}')
                return 1
        return 0

    def cmd_test(self) -> int:
        """Запустить тесты"""
        logger.console(f'{C_CYAN}🧪 Запуск тестов pytest...{C_RESET}')
        venv_python = str(self.paths.venv_python)
        result = subprocess.run([venv_python, '-m', 'pytest', 'tests/'], cwd=str(self.paths.project_root), check=False)
        return result.returncode

def main():
    """Главная function"""
    parser = argparse.ArgumentParser(description='CLI ассистент для управления AI-Windows-Admin', formatter_class=argparse.RawDescriptionHelpFormatter, epilog='\nExamples:\n  assist start                  # Запустить основной сервер\n  assist start unicorn          # Запустить FastAPI через uvicorn\n  assist stop                   # Остановить все сервисы\n  assist status                 # Показать status\n  assist providers              # List провайдеров ИИ\n  assist logs 50                # Последние 50 строк логов\n  assist config get server.port # Получить значение\n  assist config set server.port 8080  # Установить значение\n  assist test                   # Запустить тесты\n        ')
    subparsers = parser.add_subparsers(dest='command', help='Команда')
    start_parser = subparsers.add_parser('start', help='Запустить сервис')
    start_parser.add_argument('service', nargs='?', default='run', help='Сервис (run, unicorn, light, foundry)')
    stop_parser = subparsers.add_parser('stop', help='Остановить сервис')
    stop_parser.add_argument('service', nargs='?', default='all', help='Сервис (server, foundry, all)')
    subparsers.add_parser('restart', help='Перезапустить')
    subparsers.add_parser('status', help='Показать status')
    subparsers.add_parser('providers', help='List провайдеров')
    logs_parser = subparsers.add_parser('logs', help='Показать логи')
    logs_parser.add_argument('lines', nargs='?', type=int, default=40, help='Количество строк')
    logs_parser.add_argument('-n', '--name', default='fastapi', help='Имя лога (fastapi, info, error)')
    config_parser = subparsers.add_parser('config', help='Работа с config.json')
    config_parser.add_argument('subcommand', nargs='?', default='show', help='Субкоманда (show, get, set)')
    config_parser.add_argument('key', nargs='?', default='', help='Ключ')
    config_parser.add_argument('value', nargs='?', default='', help='Значение')
    subparsers.add_parser('test', help='Запустить тесты')
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    cli = AssistCLI()
    if args.command == 'start':
        return cli.cmd_start(args.service)
    elif args.command == 'stop':
        return cli.cmd_stop(args.service)
    elif args.command == 'restart':
        return cli.cmd_restart()
    elif args.command == 'status':
        return cli.cmd_status()
    elif args.command == 'providers':
        return cli.cmd_providers()
    elif args.command == 'logs':
        return cli.cmd_logs(args.lines, args.name)
    elif args.command == 'config':
        return cli.cmd_config(args.subcommand, args.key, args.value)
    elif args.command == 'test':
        return cli.cmd_test()
    else:
        parser.print_help()
        return 1
if __name__ == '__main__':
    sys.exit(main())
