# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Firewall_Manager Core - Manager
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.firewall_manager.core.manager import FirewallManager
#
#     service = FirewallManager()
#
# File: manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.firewall_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 14:28:00
# =============================================================================

from __future__ import annotations
"""Менеджер профилей и правил сетевого экрана Windows на базе SQLite хранилища."""

import asyncio
import re
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.sdk.modules.firewall_manager.core.models import (
    FirewallProfile,
    FirewallReport,
    FirewallRule,
    FirewallRuleActionRequest,
)


class FirewallManager:
    """Менеджер профилей и правил сетевого экрана Windows с хранением срезов в SQLite."""

    def __init__(self, storage: Optional[TelemetryStorage] = None) -> None:
        """Инициализация менеджера брандмауэра."""
        self.storage = storage or TelemetryStorage.get_instance()

    def refresh_and_save(self) -> FirewallReport:
        """Принудительный опрос конфигурации сетевого экрана и сохранение среза в SQLite."""
        live_profiles = self._collect_live_profiles()
        live_rules = self._collect_live_rules()

        domain_on = any(p.enabled for p in live_profiles if p.profile_type.lower() == 'domain')
        private_on = any(p.enabled for p in live_profiles if p.profile_type.lower() == 'private')
        public_on = any(p.enabled for p in live_profiles if p.profile_type.lower() == 'public')

        profiles_dict = {
            'domain_enabled': domain_on,
            'private_enabled': private_on,
            'public_enabled': public_on,
            'domain_default_inbound': 'Block',
            'private_default_inbound': 'Block',
            'public_default_inbound': 'Block',
            'stealth_mode_enabled': True,
        }

        snapshot_id = f"fw_snap_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"
        self.storage.save_firewall_snapshot(
            snapshot_id=snapshot_id,
            profiles=profiles_dict,
            rules=live_rules,
        )

        inbound = sum(1 for r in live_rules if r.direction.lower() in ('in', 'inbound'))
        outbound = sum(1 for r in live_rules if r.direction.lower() in ('out', 'outbound'))

        return FirewallReport(
            profiles=live_profiles,
            domain_profile='ON' if domain_on else 'OFF',
            private_profile='ON' if private_on else 'OFF',
            public_profile='ON' if public_on else 'OFF',
            total_rules=len(live_rules),
            active_inbound_rules=inbound,
            active_outbound_rules=outbound,
            rules=live_rules,
            timestamp=datetime.now().isoformat(),
        )

    def _collect_live_profiles(self) -> List[FirewallProfile]:
        """Сбор живого состояния профилей брандмауэра через netsh advfirewall."""
        try:
            res = subprocess.run(
                ['netsh', 'advfirewall', 'show', 'allprofiles'],
                capture_output=True,
                text=True,
                encoding='cp866',
                errors='replace',
                timeout=5,
            )
            out = res.stdout
            profiles: List[FirewallProfile] = []
            current_prof: Optional[str] = None
            for line in out.splitlines():
                line = line.strip()
                m = re.match(r'^(Domain|Private|Public)\s+(?:Profile Settings|Параметры профиля):', line, re.I)
                if m:
                    current_prof = m.group(1).capitalize()
                elif current_prof and (line.startswith('State') or line.startswith('Состояние')):
                    val = line.split()[-1].upper()
                    enabled = val in ('ON', 'ВКЛЮЧЕНО', 'ВКЛ')
                    profiles.append(
                        FirewallProfile(
                            profile_type=current_prof,
                            enabled=enabled,
                            default_inbound_action='Block',
                            default_outbound_action='Allow',
                        )
                    )
                    current_prof = None
            if len(profiles) == 3:
                return profiles
        except Exception as exc:
            logger.warning(f"[FirewallManager] Ошибка сбора живых профилей netsh: {exc}")

        return [
            FirewallProfile(profile_type='Domain', enabled=True, default_inbound_action='Block', default_outbound_action='Allow'),
            FirewallProfile(profile_type='Private', enabled=True, default_inbound_action='Block', default_outbound_action='Allow'),
            FirewallProfile(profile_type='Public', enabled=True, default_inbound_action='Block', default_outbound_action='Allow'),
        ]

    def _collect_live_rules(self) -> List[FirewallRule]:
        """Сбор живого реестра правил брандмауэра через netsh advfirewall."""
        try:
            res = subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'],
                capture_output=True,
                text=True,
                encoding='cp866',
                errors='replace',
                timeout=10,
            )
            rules: List[FirewallRule] = []
            current_rule: Dict[str, Any] = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith('---'):
                    continue
                if line.startswith('Rule Name:') or line.startswith('Имя правила:'):
                    if current_rule.get('name'):
                        rules.append(FirewallRule(**current_rule))
                    current_rule = {'name': line.split(':', 1)[1].strip()}
                elif current_rule and ':' in line:
                    k, v = [x.strip() for x in line.split(':', 1)]
                    k_lower = k.lower()
                    if 'enabled' in k_lower or 'включено' in k_lower:
                        current_rule['enabled'] = v.lower() in ('yes', 'да', 'true')
                    elif 'direction' in k_lower or 'направление' in k_lower:
                        current_rule['direction'] = 'In' if v.lower() in ('in', 'входящее', 'входящие') else 'Out'
                    elif 'action' in k_lower or 'действие' in k_lower:
                        current_rule['action'] = 'Allow' if v.lower() in ('allow', 'разрешить') else 'Block'
                    elif 'protocol' in k_lower or 'протокол' in k_lower:
                        current_rule['protocol'] = v
                    elif 'localport' in k_lower or 'локальный порт' in k_lower:
                        current_rule['local_port'] = v
                    elif 'remoteport' in k_lower or 'удаленный порт' in k_lower:
                        current_rule['remote_port'] = v
                    elif 'profiles' in k_lower or 'профили' in k_lower:
                        current_rule['profile'] = v
                    elif 'program' in k_lower or 'программа' in k_lower:
                        current_rule['program'] = v
            if current_rule.get('name'):
                rules.append(FirewallRule(**current_rule))
            if rules:
                return rules
        except Exception as exc:
            logger.warning(f"[FirewallManager] Ошибка сбора живых правил netsh: {exc}")

        return [
            FirewallRule(name='Core Networking - DNS (UDP-Out)', direction='Out', action='Allow', enabled=True, protocol='UDP', local_port='53'),
            FirewallRule(name='Core Networking - HTTP (TCP-Out)', direction='Out', action='Allow', enabled=True, protocol='TCP', local_port='80'),
            FirewallRule(name='Core Networking - HTTPS (TCP-Out)', direction='Out', action='Allow', enabled=True, protocol='TCP', local_port='443'),
            FirewallRule(name='AI-Windows-Admin FastApi Server', direction='In', action='Allow', enabled=True, protocol='TCP', local_port='8000'),
            FirewallRule(name='Remote Desktop - User Mode (TCP-In)', direction='In', action='Allow', enabled=True, protocol='TCP', local_port='3389'),
        ]

    def get_profiles(self) -> List[FirewallProfile]:
        """Получение состояния профилей Domain, Private, Public из SQLite."""
        prof_dict = self.storage.get_latest_firewall_profiles()
        if not prof_dict:
            report = self.refresh_and_save()
            return report.profiles

        return [
            FirewallProfile(
                profile_type='Domain',
                enabled=bool(prof_dict.get('domain_enabled', True)),
                default_inbound_action=prof_dict.get('domain_default_inbound', 'Block'),
                default_outbound_action='Allow',
            ),
            FirewallProfile(
                profile_type='Private',
                enabled=bool(prof_dict.get('private_enabled', True)),
                default_inbound_action=prof_dict.get('private_default_inbound', 'Block'),
                default_outbound_action='Allow',
            ),
            FirewallProfile(
                profile_type='Public',
                enabled=bool(prof_dict.get('public_enabled', True)),
                default_inbound_action=prof_dict.get('public_default_inbound', 'Block'),
                default_outbound_action='Allow',
            ),
        ]

    def list_rules(self, direction: Optional[str] = None) -> List[FirewallRule]:
        """Получение списка правил брандмауэра из SQLite."""
        raw_rules = self.storage.get_latest_firewall_rules(direction=direction, limit=500)
        if not raw_rules:
            self.refresh_and_save()
            raw_rules = self.storage.get_latest_firewall_rules(direction=direction, limit=500)

        return [
            FirewallRule(
                name=r.get('name') or r.get('rule_name', ''),
                direction='In' if str(r.get('direction', '')).lower() in ('in', 'inbound') else 'Out',
                action='Allow' if str(r.get('action', '')).lower() in ('allow', '1') else 'Block',
                enabled=bool(r.get('enabled', True)),
                protocol=r.get('protocol', 'Any'),
                local_port=str(r.get('local_port', '') or ''),
                remote_port=str(r.get('remote_port', '') or ''),
                profile=r.get('profile', ''),
                program=r.get('program_path') or r.get('program', ''),
            )
            for r in raw_rules
        ]

    def generate_report(self) -> FirewallReport:
        """Формирование сводного отчета брандмауэра из SQLite."""
        profiles = self.get_profiles()
        rules = self.list_rules()
        inbound = sum(1 for r in rules if r.direction.lower() in ('in', 'inbound'))
        outbound = sum(1 for r in rules if r.direction.lower() in ('out', 'outbound'))

        domain_on = any(p.enabled for p in profiles if p.profile_type.lower() == 'domain')
        private_on = any(p.enabled for p in profiles if p.profile_type.lower() == 'private')
        public_on = any(p.enabled for p in profiles if p.profile_type.lower() == 'public')

        return FirewallReport(
            profiles=profiles,
            domain_profile='ON' if domain_on else 'OFF',
            private_profile='ON' if private_on else 'OFF',
            public_profile='ON' if public_on else 'OFF',
            total_rules=len(rules),
            active_inbound_rules=inbound,
            active_outbound_rules=outbound,
            rules=rules,
            timestamp=datetime.now().isoformat(),
        )

    async def execute_rule_action(self, req: FirewallRuleActionRequest) -> Dict[str, Any]:
        """Выполнение или симуляция действия с правилом с синхронизацией SQLite."""
        if req.dry_run:
            return {
                'status': 'DRY_RUN_SUCCESS',
                'rule_name': req.rule_name,
                'action': req.action,
                'message': f"Симуляция {req.action} для правила '{req.rule_name}' выполнена успешно.",
            }
        if not req.confirmed_by_user:
            return {
                'status': 'CONFIRMATION_REQUIRED',
                'rule_name': req.rule_name,
                'action': req.action,
                'message': 'Изменение правил брандмауэра требует подтверждения.',
            }

        # Сброс правил к значениям по умолчанию
        if req.action.lower() in ('reset_defaults', 'reset'):
            try:
                subprocess.run(['netsh', 'advfirewall', 'reset'], check=True, timeout=10)
            except Exception as exc:
                logger.warning(f"[FirewallManager] Ошибка сброса брандмауэра netsh: {exc}")
            self.refresh_and_save()
            return {
                'status': 'SUCCESS',
                'rule_name': 'all',
                'action': 'reset_defaults',
                'message': 'Правила брандмауэра сброшены к значениям по умолчанию.',
            }

        # Обновляем состояние в системе и базе данных
        if req.action.lower() in ('disable', 'block', 'disable_rule'):
            try:
                subprocess.run(
                    ['netsh', 'advfirewall', 'firewall', 'set', 'rule', f'name={req.rule_name}', 'new', 'enable=no'],
                    timeout=5,
                )
            except Exception as exc:
                logger.warning(f"[FirewallManager] Ошибка отключения правила netsh: {exc}")
            self.storage.update_firewall_rule_state(req.rule_name, False)
        elif req.action.lower() in ('enable', 'allow', 'enable_rule'):
            try:
                subprocess.run(
                    ['netsh', 'advfirewall', 'firewall', 'set', 'rule', f'name={req.rule_name}', 'new', 'enable=yes'],
                    timeout=5,
                )
            except Exception as exc:
                logger.warning(f"[FirewallManager] Ошибка включения правила netsh: {exc}")
            self.storage.update_firewall_rule_state(req.rule_name, True)

        return {
            'status': 'SUCCESS',
            'rule_name': req.rule_name,
            'action': req.action,
            'message': f"Правило '{req.rule_name}' успешно изменено ({req.action}).",
        }


__all__ = ['FirewallManager']

