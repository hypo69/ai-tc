# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Network - Discovery Manager
# =============================================================================
# Description:
#   Модуль программного управления сетевым обнаружением Windows (Network Discovery),
#   профилями сетевых подключений (Public / Private), брандмауэром и системными
#   службами публикации ресурсов (FDResPub, fdPHost).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.network.discovery import NetworkDiscoveryManager
#
#     mgr = NetworkDiscoveryManager()
#     status = mgr.inspect()
#     mgr.set_network_category("Private", interface_index=3)
#     mgr.enable(interface_index=3, set_private=True)
#     mgr.disable()
#
# File: discovery.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 05:40:00
# =============================================================================

from __future__ import annotations
"""Управление сетевым обнаружением Windows, сетевыми категориями и службами."""

import json
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
from apps.common.telemetry_logger import AppTelemetryLogger


class NetworkDiscoveryManager:
    """Менеджер сетевого обнаружения и категорий сетевых профилей Windows."""

    FIREWALL_GROUP_INVARIANT: str = "@FirewallAPI.dll,-32752"
    SERVICE_FDRESPUB: str = "FDResPub"
    SERVICE_FDPHOST: str = "fdPHost"

    def __init__(self) -> None:
        """Инициализация менеджера сетевого обнаружения и регистратора телеметрии."""
        self._telemetry_logger = AppTelemetryLogger("network_discovery")

    def _run_ps_command(self, script: str) -> Tuple[int, str, str]:
        """Безопасный запуск PowerShell-команды в неинтерактивном режиме.

        Args:
            script: Исполняемый PowerShell-скрипт или конвейер команд.

        Returns:
            Tuple[int, str, str]: Код возврата, stdout и stderr.
        """
        try:
            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=25,
            )
            return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()
        except Exception as exc:
            logger.error(f"[NetworkDiscovery] Ошибка исполнения PowerShell: {exc}")
            return -1, "", str(exc)

    def get_connection_profiles(self) -> List[Dict[str, Any]]:
        """Получение списка активных сетевых профилей подключения.

        Returns:
            List[Dict[str, Any]]: Список словарей с характеристиками сетевых интерфейсов
                (InterfaceIndex, Name, InterfaceAlias, NetworkCategory, IPv4Connectivity).
        """
        ps_cmd = (
            "Get-NetConnectionProfile -ErrorAction SilentlyContinue | ForEach-Object { "
            "[PSCustomObject]@{ "
            "Name=$_.Name; "
            "InterfaceAlias=$_.InterfaceAlias; "
            "InterfaceIndex=$_.InterfaceIndex; "
            "NetworkCategory=$_.NetworkCategory.ToString(); "
            "IPv4Connectivity=$_.IPv4Connectivity.ToString() "
            "} } | ConvertTo-Json -Compress"
        )
        code, stdout, stderr = self._run_ps_command(ps_cmd)
        if code != 0 or not stdout:
            if stderr:
                logger.warning(f"[NetworkDiscovery] Ошибка Get-NetConnectionProfile: {stderr}")
            return []

        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                return [data]
            if isinstance(data, list):
                return data
        except Exception as exc:
            logger.warning(f"[NetworkDiscovery] Ошибка парсинга JSON профилей сети: {exc}")

        return []

    def get_services_state(self) -> Dict[str, Dict[str, Any]]:
        """Опрос состояния служб обнаружения ресурсов (FDResPub и fdPHost).

        Returns:
            Dict[str, Dict[str, Any]]: Состояние служб, включая статус работы и тип запуска.
        """
        ps_cmd = (
            "Get-Service -Name FDResPub, fdPHost -ErrorAction SilentlyContinue | ForEach-Object { "
            "[PSCustomObject]@{ "
            "Name=$_.Name; "
            "DisplayName=$_.DisplayName; "
            "Status=$_.Status.ToString(); "
            "StartType=$_.StartType.ToString() "
            "} } | ConvertTo-Json -Compress"
        )
        code, stdout, _ = self._run_ps_command(ps_cmd)
        result: Dict[str, Dict[str, Any]] = {}

        if code == 0 and stdout:
            try:
                parsed = json.loads(stdout)
                items = [parsed] if isinstance(parsed, dict) else parsed
                for item in items:
                    name = item.get("Name")
                    if name:
                        result[name] = item
            except Exception as exc:
                logger.warning(f"[NetworkDiscovery] Ошибка парсинга служб: {exc}")

        return result

    def get_firewall_rules_state(self) -> Dict[str, Any]:
        """Опрос правил брандмауэра для сетевого обнаружения с языконезависимым поиском.

        Returns:
            Dict[str, Any]: Сводка правил брандмауэра: общее количество, число активных и статус.
        """
        ps_cmd = (
            "$rules = Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Group -eq '@FirewallAPI.dll,-32752' -or "
            "$_.DisplayGroup -like '*Network Discovery*' -or "
            "$_.DisplayGroup -like '*Обнаружение сети*' }; "
            "if ($rules) { "
            "$rules | Select-Object Name, DisplayName, Enabled, Direction, Action, Group | "
            "ConvertTo-Json -Compress "
            "} else { '[]' }"
        )
        code, stdout, _ = self._run_ps_command(ps_cmd)
        total_rules = 0
        enabled_rules = 0
        rules_list: List[Dict[str, Any]] = []

        if code == 0 and stdout:
            try:
                parsed = json.loads(stdout)
                items = [parsed] if isinstance(parsed, dict) else parsed
                rules_list = items
                total_rules = len(items)
                for r in items:
                    en = r.get("Enabled")
                    if en in (1, True, "1", "True"):
                        enabled_rules += 1
            except Exception as exc:
                logger.warning(f"[NetworkDiscovery] Ошибка парсинга правил брандмауэра: {exc}")

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "is_enabled": enabled_rules > 0 and (enabled_rules >= (total_rules // 2 if total_rules else 1)),
            "group_identifier": self.FIREWALL_GROUP_INVARIANT,
        }

    def inspect(self) -> Dict[str, Any]:
        """Комплексная инспекция сетевого профиля, служб и брандмауэра.

        Returns:
            Dict[str, Any]: Полная диагностическая картина сетевого обнаружения хоста.
        """
        profiles = self.get_connection_profiles()
        services = self.get_services_state()
        firewall = self.get_firewall_rules_state()

        primary_profile: Optional[Dict[str, Any]] = None
        current_category = "Public"
        primary_index = None

        if profiles:
            # Находим профиль с активным интернетом или берем первый
            for p in profiles:
                if str(p.get("IPv4Connectivity", "")).lower() == "internet":
                    primary_profile = p
                    break
            if not primary_profile:
                primary_profile = profiles[0]

            current_category = str(primary_profile.get("NetworkCategory", "Public"))
            primary_index = primary_profile.get("InterfaceIndex")

        # Проверка служб
        fdres = services.get(self.SERVICE_FDRESPUB, {})
        fdphost = services.get(self.SERVICE_FDPHOST, {})
        fdres_running = str(fdres.get("Status", "")).lower() == "running"
        fdphost_running = str(fdphost.get("Status", "")).lower() == "running"

        fw_enabled = firewall.get("is_enabled", False)
        # Обнаружение сети считается включенным, если правила активны и FDResPub запущен
        discovery_enabled = fw_enabled and fdres_running

        return {
            "status": "ok",
            "is_discovery_enabled": discovery_enabled,
            "current_category": current_category,
            "primary_interface_index": primary_index,
            "primary_profile": primary_profile,
            "profiles": profiles,
            "services": {
                self.SERVICE_FDRESPUB: fdres,
                self.SERVICE_FDPHOST: fdphost,
                "fdres_running": fdres_running,
                "fdphost_running": fdphost_running,
            },
            "firewall": firewall,
        }

    def set_network_category(self, category: str, interface_index: Optional[int] = None) -> Dict[str, Any]:
        """Изменение сетевой категории (Public или Private) для интерфейса.

        Args:
            category: Целевая категория ('Public' или 'Private').
            interface_index: Индекс сетевого адаптера. Если не указан, применяется к текущему.

        Returns:
            Dict[str, Any]: Результат выполнения операции.
        """
        cat_clean = category.strip().capitalize()
        if cat_clean not in ("Public", "Private", "Domainauthenticated"):
            return {
                "status": "error",
                "message": f"Недопустимая категория сети: {category}. Разрешены 'Public' или 'Private'.",
            }

        target_idx = interface_index
        if target_idx is None:
            profiles = self.get_connection_profiles()
            if profiles:
                target_idx = profiles[0].get("InterfaceIndex")

        if target_idx is None:
            return {
                "status": "error",
                "message": "Не найден активный сетевой адаптер для смены категории профиля.",
            }

        ps_cmd = f"Set-NetConnectionProfile -InterfaceIndex {target_idx} -NetworkCategory {cat_clean} -ErrorAction Stop"
        code, stdout, stderr = self._run_ps_command(ps_cmd)

        if code != 0:
            err_msg = stderr or stdout or "Требуются права администратора Windows"
            logger.error(f"[NetworkDiscovery] Ошибка смены категории на {cat_clean} (Index {target_idx}): {err_msg}")
            return {
                "status": "error",
                "interface_index": target_idx,
                "target_category": cat_clean,
                "message": f"Ошибка смены профиля сети: {err_msg}",
            }

        msg = f"Профиль сети для интерфейса {target_idx} успешно переключен на '{cat_clean}'"
        logger.console(f"[NetworkDiscovery] {msg}")
        self._telemetry_logger.log_event(
            event_type="set_network_category",
            status="SUCCESS",
            details={
                "target_category": cat_clean,
                "interface_index": target_idx,
            },
        )

        return {
            "status": "ok",
            "interface_index": target_idx,
            "category": cat_clean,
            "message": msg,
        }

    def enable(self, interface_index: Optional[int] = None, set_private: bool = False) -> Dict[str, Any]:
        """Включение сетевого обнаружения Windows, брандмауэра и системных служб.

        Args:
            interface_index: Индекс интерфейса для опциональной смены профиля.
            set_private: Установить доверенный частный профиль (Private).

        Returns:
            Dict[str, Any]: Сводный результат включения сетевого обнаружения.
        """
        actions_log: List[str] = []

        # 1. Опциональная установка частного профиля сети
        if set_private:
            cat_res = self.set_network_category("Private", interface_index=interface_index)
            if cat_res.get("status") == "ok":
                actions_log.append("Сетевой профиль переключен в Private")
            else:
                actions_log.append(f"Предупреждение: {cat_res.get('message')}")

        # 2. Включение правил брандмауэра через инвариантный идентификатор
        fw_script = (
            "$rules = Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Group -eq '@FirewallAPI.dll,-32752' -or "
            "$_.DisplayGroup -like '*Network Discovery*' -or "
            "$_.DisplayGroup -like '*Обнаружение сети*' }; "
            "if ($rules) { $rules | Set-NetFirewallRule -Enabled True -ErrorAction SilentlyContinue; 'OK' } else { 'NO_RULES' }"
        )
        code_fw, out_fw, err_fw = self._run_ps_command(fw_script)
        if code_fw == 0:
            actions_log.append("Правила брандмауэра для обнаружения сети активированы")
        else:
            actions_log.append(f"Ошибка брандмауэра: {err_fw}")

        # 3. Настройка и запуск системных служб публикации
        svc_script = (
            "Set-Service -Name FDResPub -StartupType Automatic -ErrorAction SilentlyContinue; "
            "Start-Service -Name FDResPub -ErrorAction SilentlyContinue; "
            "Set-Service -Name fdPHost -StartupType Manual -ErrorAction SilentlyContinue; "
            "Start-Service -Name fdPHost -ErrorAction SilentlyContinue; "
            "'SERVICES_CONFIGURED'"
        )
        code_svc, _, err_svc = self._run_ps_command(svc_script)
        if code_svc == 0:
            actions_log.append("Службы FDResPub и fdPHost настроены и запущены")
        else:
            actions_log.append(f"Ошибка служб: {err_svc}")

        inspection = self.inspect()
        logger.console(f"[NetworkDiscovery] Сетевое обнаружение включено: {actions_log}")
        self._telemetry_logger.log_event(
            event_type="network_discovery_enable",
            status="SUCCESS",
            details={"actions": actions_log},
        )

        return {
            "status": "ok",
            "message": "Сетевое обнаружение успешно включено",
            "actions": actions_log,
            "state": inspection,
        }

    def disable(self, interface_index: Optional[int] = None, set_public: bool = False) -> Dict[str, Any]:
        """Отключение сетевого обнаружения с восстановлением безопасного состояния.

        Args:
            interface_index: Индекс интерфейса для опциональной смены профиля.
            set_public: Переключить профиль подключения в общедоступный (Public).

        Returns:
            Dict[str, Any]: Сводный результат отключения сетевого обнаружения.
        """
        actions_log: List[str] = []

        # 1. Отключение правил брандмауэра
        fw_script = (
            "$rules = Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Group -eq '@FirewallAPI.dll,-32752' -or "
            "$_.DisplayGroup -like '*Network Discovery*' -or "
            "$_.DisplayGroup -like '*Обнаружение сети*' }; "
            "if ($rules) { $rules | Set-NetFirewallRule -Enabled False -ErrorAction SilentlyContinue; 'OK' } else { 'NO_RULES' }"
        )
        code_fw, _, err_fw = self._run_ps_command(fw_script)
        if code_fw == 0:
            actions_log.append("Правила брандмауэра обнаружения сети деактивированы")
        else:
            actions_log.append(f"Ошибка брандмауэра: {err_fw}")

        # 2. Остановка службы публикации ресурсов
        svc_script = (
            "Stop-Service -Name FDResPub -Force -ErrorAction SilentlyContinue; "
            "Set-Service -Name FDResPub -StartupType Manual -ErrorAction SilentlyContinue; "
            "'SERVICES_STOPPED'"
        )
        code_svc, _, err_svc = self._run_ps_command(svc_script)
        if code_svc == 0:
            actions_log.append("Служба публикации ресурсов FDResPub остановлена")
        else:
            actions_log.append(f"Ошибка служб: {err_svc}")

        # 3. Опциональный перевод в общедоступный профиль
        if set_public:
            cat_res = self.set_network_category("Public", interface_index=interface_index)
            if cat_res.get("status") == "ok":
                actions_log.append("Сетевой профиль переключен в Public")
            else:
                actions_log.append(f"Предупреждение: {cat_res.get('message')}")

        inspection = self.inspect()
        logger.console(f"[NetworkDiscovery] Сетевое обнаружение отключено: {actions_log}")
        self._telemetry_logger.log_event(
            event_type="network_discovery_disable",
            status="SUCCESS",
            details={"actions": actions_log},
        )

        return {
            "status": "ok",
            "message": "Сетевое обнаружение успешно отключено",
            "actions": actions_log,
            "state": inspection,
        }


# Алиас для унификации с соглашениями именования Windows SDK
WindowsNetworkDiscovery = NetworkDiscoveryManager

__all__ = ["NetworkDiscoveryManager", "WindowsNetworkDiscovery"]

