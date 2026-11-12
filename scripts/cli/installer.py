# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli - Installer
# =============================================================================
# Description:
#   Cross-platform installation system for AI Windows Admin.
#
# Usage Examples:
#   CLI:
#     python -m scripts.cli.installer
#   Python API:
#     from scripts.cli.installer import Language
#
#     service = Language()
#
# File: installer.py
# Project: ai-windows-admin
# Package: scripts.cli
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:37:00
# =============================================================================

"""Cross-platform installation system for AI Windows Admin.

Ported from legacy install.ps1 to work on Windows, Linux, and macOS.

Usage:
    python scripts/cli/installer.py
    python scripts/cli/installer.py --lang en
    python scripts/cli/installer.py --skip-models"""

from logger import logger
import argparse
import json
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.cli.paths import get_paths, CrossPlatformPaths
from scripts.cli.config import get_config_manager
from scripts.cli.utils import which, run_command

class Language(Enum):
    """Supported languages"""
    EN = 'en'
    RU = 'ru'
    ES = 'es'
    HE = 'he'
MESSAGES = {'en': {'welcome': '🎯 AI Windows Admin Installation', 'step_venv': '[1/6] Creating Python virtual environment...', 'step_deps': '[2/6] Installing dependencies...', 'step_certs': '[3/6] Setting up SSL certificates...', 'step_cli': '[4/6] Configuring CLI assistant...', 'step_user': 'Configuring default administrator account...', 'step_verify': '[5/6] Verifying installation...', 'step_models': '[6/6] Downloading AI models (optional)...', 'success': '✅ Installation completed successfully!', 'error': '❌ Installation failed:', 'abort': '⚠️  Installation aborted by user'}, 'ru': {'welcome': '🎯 AI Windows Admin Installation', 'step_venv': '[1/6] Creating Python virtual environment...', 'step_deps': '[2/6] Installing dependencies...', 'step_certs': '[3/6] Setting up SSL certificates...', 'step_cli': '[4/6] Configuring CLI assistant...', 'step_user': 'Настройка учетной записи администратора по умолчанию...', 'step_verify': '[5/6] Verifying installation...', 'step_models': '[6/6] Downloading AI models (optional)...', 'success': '✅ Installation completed successfully!', 'error': '❌ Installation failed:', 'abort': '⚠️  Installation aborted by user'}}

class Installer:
    """Main installer class"""

    def __init__(self, language: str='en', install_dir: Optional[Path]=None, light_version: bool=False):
        self.language = Language[language.upper()] if language.upper() in Language.__members__ else Language.EN
        self.messages = MESSAGES.get(self.language.value, MESSAGES['en'])
        self.install_dir = install_dir or self._get_default_install_dir()
        self.venv_dir = self.install_dir / 'venv'
        self.light_version = light_version
        self.config_mgr = get_config_manager()

    def msg(self, key: str) -> str:
        """Get message in current language"""
        return self.messages.get(key, key)

    @staticmethod
    def _get_default_install_dir() -> Path:
        """Get default installation directory"""
        if sys.platform == 'win32':
            localappdata = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
            return Path(localappdata) / (os.environ.get('APP_NAME') or 'ai-tc')
        else:
            return Path.home() / (os.environ.get('APP_NAME') or 'ai-tc')

    def print_header(self):
        """Print installation header"""
        logger.console()
        logger.console('╔' + '═' * 68 + '╗')
        logger.console('║' + self.msg('welcome').center(68) + '║')
        logger.console('╚' + '═' * 68 + '╝')
        logger.console()
        if self.light_version:
            logger.console('Mode: LIGHT VERSION (Gemini / AGY / Cloud Only)')
        logger.console(f'Installing to: {self.install_dir}')
        logger.console()

    def create_venv(self) -> bool:
        """Create virtual environment"""
        logger.console(self.msg('step_venv'))
        try:
            if self.venv_dir.exists():
                logger.console(f'  Removing old venv...', end=' ', flush=True)
                shutil.rmtree(self.venv_dir)
                logger.console('[OK]')
            logger.console(f'  Creating venv...', end=' ', flush=True)
            subprocess.run([sys.executable, '-m', 'venv', str(self.venv_dir)], check=True, capture_output=True)
            logger.console('[OK]')
            logger.console()
            return True
        except Exception as e:
            logger.console(f'[ERROR] {e}')
            logger.console()
            return False

    def install_dependencies(self) -> bool:
        """Install dependencies"""
        logger.console(self.msg('step_deps'))
        try:
            if sys.platform == 'win32':
                pip_exe = self.venv_dir / 'Scripts' / 'pip.exe'
            else:
                pip_exe = self.venv_dir / 'bin' / 'pip'
            if not pip_exe.exists():
                logger.console(f'  [ERROR] pip not found in venv')
                logger.console()
                return False
            if self.light_version:
                req_light = self.install_dir / 'install' / 'req' / 'requirements-light.txt'
                req_files = [req_light] if req_light.exists() else [self.install_dir / 'install' / 'req' / 'requirements-core.txt']
            else:
                req_files = [self.install_dir / 'requirements.txt', self.install_dir / 'install' / 'req' / 'requirements-core.txt', self.install_dir / 'install' / 'req' / 'requirements-ai.txt']
            for req_file in req_files:
                if req_file.exists():
                    logger.console(f'  Installing from {req_file.name}...', end=' ', flush=True)
                    result = subprocess.run([str(pip_exe), 'install', '-r', str(req_file)], capture_output=True, text=True)
                    if result.returncode == 0:
                        logger.console('[OK]')
                    else:
                        logger.console(f'[WARN]')
                        if result.stderr:
                            logger.console(f'    {result.stderr[:100]}')
            logger.console('  Installing Google AI & LangGraph providers (gemini, agy, langgraph)...', end=' ', flush=True)
            subprocess.run([str(pip_exe), 'install', 'google-genai', 'google-antigravity', 'langchain', 'langchain-core', 'langchain-google-genai', 'langgraph'], capture_output=True, text=True)
            logger.console('[OK]')
            logger.console()
            return True
        except Exception as e:
            logger.console(f'[ERROR] {e}')
            logger.console()
            return False

    def setup_ssl_certificates(self) -> bool:
        """Setup SSL certificates"""
        logger.console(self.msg('step_certs'))
        try:
            certs_dir = CrossPlatformPaths().certs_dir
            certs_dir.mkdir(parents=True, exist_ok=True)
            logger.console(f'  Certificates directory: {certs_dir}')
            if which('mkcert'):
                logger.console(f'  mkcert found, generating certificates...', end=' ', flush=True)
                subprocess.run(['mkcert', '-install'], cwd=str(certs_dir), capture_output=True)
                subprocess.run(['mkcert', '-key-file', str(certs_dir / 'localhost+2-key.pem'), '-cert-file', str(certs_dir / 'localhost+2.pem'), 'localhost', '127.0.0.1', '::1'], cwd=str(certs_dir), capture_output=True)
                logger.console('[OK]')
            else:
                logger.console(f'  mkcert not installed (optional)')
                logger.console(f'  Installation: https://github.com/FiloSottile/mkcert')
            logger.console()
            return True
        except Exception as e:
            logger.console(f'[WARN] Error setting up certificates: {e}')
            logger.console()
            return True

    def configure_cli(self) -> bool:
        """Configure CLI assistant"""
        logger.console(self.msg('step_cli'))
        try:
            from scripts.cli.utils import ensure_in_path, add_to_env_var
            logger.console(f'  Adding to PATH...', end=' ', flush=True)
            if ensure_in_path(self.install_dir / 'assist'):
                logger.console('[OK]')
            else:
                logger.console('[WARN]')
            logger.console(f'  Setting environment variables...', end=' ', flush=True)
            add_to_env_var('AIWINDOWSADMIN_DIR', str(self.install_dir))
            add_to_env_var('PYTHONPATH', str(self.install_dir))
            logger.console('[OK]')
            logger.console()
            return True
        except Exception as e:
            logger.console(f'[WARN] {e}')
            logger.console()
            return True

    def verify_installation(self) -> bool:
        """Verify installation"""
        logger.console(self.msg('step_verify'))
        try:
            if sys.platform == 'win32':
                python_exe = self.venv_dir / 'Scripts' / 'python.exe'
            else:
                python_exe = self.venv_dir / 'bin' / 'python'
            if not python_exe.exists():
                logger.console(f'  [ERROR] Python not found in venv')
                logger.console()
                return False
            logger.console(f'  Checking dependencies...', end=' ', flush=True)
            result = subprocess.run([str(python_exe), '-c', "import fastapi, uvicorn, dotenv; logger.console('OK')"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and 'OK' in result.stdout:
                logger.console('[OK]')
            else:
                logger.console('[WARN] Some dependencies may not be installed')
            if self.light_version:
                config_path = self.install_dir / 'config.json'
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                        cfg.setdefault('server', {})
                        cfg['server']['host'] = '127.0.0.1'
                        cfg['server']['use_cloudflared'] = False
                        cfg['server']['client_url'] = 'http://127.0.0.1:8000'
                        ai_conf = cfg.setdefault('ai_providers_and_models_configuration', {})
                        provs = ai_conf.setdefault('providers', {})
                        provs.setdefault('foundry', {})['enabled'] = False
                        provs.setdefault('ollama', {})['enabled'] = False
                        provs.setdefault('gemini_cli', {})['enabled'] = True
                        provs.setdefault('agy', {})['enabled'] = True
                        cfg.pop('ai', None)
                        with open(config_path, 'w', encoding='utf-8') as f:
                            json.dump(cfg, f, indent=4)
                        logger.console('  Patched config.json for light version [OK]')
                    except Exception as ex:
                        logger.console(f'  [WARN] Failed to patch config.json: {ex}')
            assist_file = self.install_dir / 'assist'
            if assist_file.exists() or (self.install_dir / 'assist.cmd').exists():
                logger.console(f'  Checking assist CLI...', end=' ', flush=True)
                logger.console('[OK]')
            else:
                logger.console(f'  [WARN] assist not found')
            logger.console()
            return True
        except Exception as e:
            logger.console(f'[WARN] {e}')
            logger.console()
            return True

    def download_models(self, skip: bool=False) -> bool:
        """Download models (optional)"""
        if skip or self.light_version:
            logger.console(self.msg('step_models'))
            logger.console(f'  Skipping local models (light mode)')
            logger.console()
            return True
        logger.console(self.msg('step_models'))
        logger.console(f'  TODO: Implement model download')
        logger.console()
        return True

    def setup_initial_user(self) -> bool:
        """Configure initial default administrator user"""
        logger.console(self.msg('step_user'))
        try:
            python_exe = self.venv_dir / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
            user_script = self.install_dir / 'scripts' / 'create_initial_user.py'
            if user_script.exists():
                subprocess.run([str(python_exe), str(user_script), '--non-interactive'], capture_output=True, text=True, timeout=30)
                logger.console('  Administrator account initialized [OK]')
            logger.console()
            return True
        except Exception as e:
            logger.console(f'  [WARN] Failed to setup initial user: {e}')
            logger.console()
            return True

    def run(self, skip_models: bool=False, skip_venv: bool=False, skip_deps: bool=False, skip_certs: bool=False) -> int:
        """Run installation"""
        self.print_header()
        try:
            self.install_dir.mkdir(parents=True, exist_ok=True)
            steps = [(not skip_venv, self.create_venv, 'venv'), (not skip_deps, self.install_dependencies, 'dependencies'), (not skip_certs, self.setup_ssl_certificates, 'SSL certificates'), (True, self.configure_cli, 'CLI'), (True, self.setup_initial_user, 'initial user'), (True, self.verify_installation, 'verification'), (True, lambda: self.download_models(skip=skip_models), 'models')]
            for should_run, step_func, step_name in steps:
                if should_run:
                    if not step_func():
                        logger.console(f"{self.msg('error')} {step_name}")
                        return 1
            logger.console('╔' + '═' * 68 + '╗')
            logger.console('║' + self.msg('success').center(68) + '║')
            logger.console('╚' + '═' * 68 + '╝')
            logger.console()
            logger.console(f'Next steps:')
            logger.console(f'  1. Go to installation directory:')
            logger.console(f'     cd {self.install_dir}')
            logger.console(f'  2. Activate venv:')
            if sys.platform == 'win32':
                logger.console(f'     venv\\Scripts\\activate')
            else:
                logger.console(f'     source venv/bin/activate')
            logger.console(f'  3. Start the server:')
            logger.console(f'     python run.py')
            logger.console()
            return 0
        except KeyboardInterrupt:
            logger.console()
            logger.console(self.msg('abort'))
            logger.console()
            return 1
        except Exception as e:
            logger.console(f"{self.msg('error')} {e}")
            return 1

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='AI Windows Admin installer', formatter_class=argparse.RawDescriptionHelpFormatter, epilog='\nExamples:\n  python scripts/cli/installer.py\n  python scripts/cli/installer.py --install-light-version\n  python scripts/cli/installer.py --lang en\n  python scripts/cli/installer.py --install-dir /path/to/install\n  python scripts/cli/installer.py --skip-models\n        ')
    parser.add_argument('--lang', choices=['en', 'ru', 'es', 'he'], default='en', help='Installation language (default: en)')
    parser.add_argument('--install-dir', type=Path, default=None, help='Installation directory')
    parser.add_argument('--install-light-version', '--light', dest='install_light_version', action='store_true', help='Install lightweight version (Gemini/AGY only, no local heavy AI models/providers)')
    parser.add_argument('--skip-models', action='store_true', help='Skip model download')
    parser.add_argument('--skip-venv', action='store_true', help='Skip venv creation')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency installation')
    parser.add_argument('--skip-certs', action='store_true', help='Skip certificate setup')
    args = parser.parse_args()
    installer = Installer(language=args.lang, install_dir=args.install_dir, light_version=args.install_light_version)
    return installer.run(skip_models=args.skip_models or args.install_light_version, skip_venv=args.skip_venv, skip_deps=args.skip_deps, skip_certs=args.skip_certs)
if __name__ == '__main__':
    sys.exit(main())
