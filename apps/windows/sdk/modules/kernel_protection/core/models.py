# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Models
# =============================================================================
# Description:
#   Pydantic-модели данных для системы защиты ядра, аудита системных драйверов,
#   файловых минифильтров и расследования причин блокировки операций (Blocker Detection).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core.models import SystemDriverInfo
#
#     driver = SystemDriverInfo(name="ucpd", display_name="User Choice Protection Driver")
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Pydantic-модели данных для подсистемы Kernel Protection & Driver Management."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DriverCategory(str, Enum):
    """Категория системного драйвера."""
    SECURITY = 'security'          # Драйверы безопасности и защиты (ucpd, WdFilter, luafv)
    MINIFILTER = 'minifilter'      # Файловые минифильтры (cldflt, bindflt, storqosflt)
    SYSTEM = 'system'              # Системные драйверы ядра Windows
    THIRD_PARTY = 'third_party'    # Сторонние драйверы (антивирусы, DLP, утилиты)
    UNKNOWN = 'unknown'            # Неопределенная категория


class ComponentCriticality(str, Enum):
    """Уровень критичности компонента для стабильности ОС."""
    CRITICAL = 'critical'          # Нельзя отключать: риск немедленного сбоя/BSOD
    HIGH = 'high'                  # Критичен для безопасности (Real-time Defender, ELAM)
    MEDIUM = 'medium'              # Можно безопасно временно отключать (UCPD)
    LOW = 'low'                    # Низкое влияние (второстепенные фильтры)


class SystemDriverInfo(BaseModel):
    """Сведения о системном драйвере Windows."""
    name: str = Field(..., description='Системное имя драйвера (служба)')
    display_name: str = Field('', description='Отображаемое имя')
    state: str = Field('Unknown', description='Состояние: Running, Stopped и др.')
    start_mode: str = Field('Unknown', description='Режим старта: Boot, System, Auto, Demand, Disabled')
    path_name: str = Field('', description='Файловый путь к бинарнику .sys')
    category: DriverCategory = Field(DriverCategory.SYSTEM, description='Категория драйвера')
    is_running: bool = Field(False, description='Признак активности драйвера')
    purpose_ru: str = Field('', description='Описание назначения на русском языке')
    protection_role: Optional[str] = Field(None, description='Роль в механизмах защиты и ограничений')
    altitude: Optional[str] = Field(None, description='Высота фильтра (для минифильтров)')
    criticality: ComponentCriticality = Field(ComponentCriticality.MEDIUM, description='Критичность компонента')
    can_disable: bool = Field(False, description='Допустимость безопасного отключения')


class MinifilterInfo(BaseModel):
    """Сведения об активном файловом минифильтре Windows (fltmc)."""
    name: str = Field(..., description='Имя фильтра (например WdFilter, cldflt)')
    instances_count: int = Field(0, description='Количество подключенных экземпляров')
    altitude: str = Field('', description='Числовая высота фильтра (Altitude)')
    frame: str = Field('0', description='Номер кадра диспетчера фильтров')
    altitude_group_ru: str = Field('Стандартный фильтр', description='Группа высоты фильтра')
    purpose_ru: str = Field('', description='Назначение фильтра')
    vendor: str = Field('Microsoft', description='Разработчик драйвера фильтра')


class ProtectionMechanismStatus(BaseModel):
    """Статус системного механизма защиты ядра и контроля изменений."""
    id: str = Field(..., description='Идентификатор механизма (hvci, secure_boot, ucpd и др.)')
    name: str = Field(..., description='Название механизма')
    enabled: bool = Field(False, description='Признак включения')
    status_label: str = Field('Неизвестно', description='Текстовый статус (Активен, Выключен, Не поддерживается)')
    category: str = Field('Системная защита', description='Категория механизма')
    description_ru: str = Field('', description='Подробное описание назначения')
    impact_ru: str = Field('', description='Влияние на изменение параметров Windows')
    registry_details: Dict[str, Any] = Field(default_factory=dict, description='Параметры из реестра')
    can_toggle: bool = Field(False, description='Допустимость изменения из AI-TC')


class BlockerTargetType(str, Enum):
    """Тип целевого объекта при проверке блокировки."""
    REGISTRY_KEY = 'registry_key'
    FILE_PATH = 'file_path'
    SERVICE = 'service'
    SYSTEM_SETTING = 'system_setting'


class BlockerCulpritType(str, Enum):
    """Выявленная причина блокировки модификации."""
    UCPD = 'ucpd'                          # Драйвер защиты пользовательских предпочтений
    TAMPER_PROTECTION = 'tamper_protection'# Microsoft Defender Tamper Protection
    REGISTRY_ACL = 'registry_acl'          # Ограничения NTFS/реестра (владелец TrustedInstaller/SYSTEM)
    UAC_ELEVATION = 'uac_elevation'        # Недостаточно прав процесса (требуется Run as Admin)
    GPO_MDM = 'gpo_mdm'                    # Групповые политики или MDM/CSP
    MINIFILTER = 'minifilter'              # Перехват файловым минифильтром (WdFilter, bindflt)
    WDAC = 'wdac'                          # Windows Defender Application Control
    NONE_DETECTED = 'none_detected'        # Блокировка не обнаружена (доступ открыт)
    UNKNOWN = 'unknown'                    # Неизвестный источник


class BlockerFinding(BaseModel):
    """Результат конкретной проверки в цепочке расследования."""
    stage: str = Field(..., description='Название этапа проверки')
    passed: bool = Field(True, description='Признак успешности проверки')
    details_ru: str = Field('', description='Результаты этапа на русском языке')
    severity: str = Field('info', description='Уровень важности: info, warning, danger')
    evidence: Dict[str, Any] = Field(default_factory=dict, description='Собранные технические факты')


class BlockerInvestigationRequest(BaseModel):
    """Запрос на проведение расследования блокировки операции."""
    target_type: BlockerTargetType = Field(BlockerTargetType.REGISTRY_KEY, description='Тип объекта')
    target_path: str = Field(..., description='Путь к ключу реестра, файлу или имени службы')
    operation: str = Field('modify', description='Запланированная операция: modify, delete, create')


class BlockerVerdict(BaseModel):
    """Итоговое заключение о причине блокировки операции."""
    is_blocked: bool = Field(False, description='Зафиксирована ли блокировка')
    likely_culprit: BlockerCulpritType = Field(BlockerCulpritType.NONE_DETECTED, description='Главный виновник')
    culprit_title_ru: str = Field('', description='Название виновника на русском языке')
    confidence: float = Field(1.0, description='Степень уверенности от 0.0 до 1.0')
    summary_ru: str = Field('', description='Понятное резюме для администратора')
    remediation_steps_ru: List[str] = Field(default_factory=list, description='Шаги безопасного разрешения')
    findings: List[BlockerFinding] = Field(default_factory=list, description='Детали всех шагов расследования')
    investigated_at: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        description='Время проверки'
    )


class SafeOpsActionRequest(BaseModel):
    """Запрос на безопасное управление компонентом защиты."""
    action: str = Field(..., description='Действие: disable_ucpd, enable_ucpd, restore_driver')
    component_name: str = Field(..., description='Имя компонента или драйвера')
    confirm_risk: bool = Field(False, description='Подтверждение понимания рисков администратором')


class SafeOpsActionResult(BaseModel):
    """Результат выполнения безопасного действия."""
    success: bool = Field(..., description='Успешность операции')
    message: str = Field('', description='Сообщение о результате')
    rollback_available: bool = Field(False, description='Доступность отката изменений')
    backup_id: Optional[str] = Field(None, description='Идентификатор точки отката')
    details: Dict[str, Any] = Field(default_factory=dict, description='Технические детали')


class KernelProtectionReport(BaseModel):
    """Сводный отчет о системе защиты ядра и драйверах Windows."""
    generated_at: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        description='Время генерации отчета'
    )
    total_drivers_count: int = Field(0, description='Всего обнаружено драйверов')
    security_drivers_count: int = Field(0, description='Драйверов защиты и контроля')
    active_minifilters_count: int = Field(0, description='Активных файловых минифильтров')
    mechanisms: List[ProtectionMechanismStatus] = Field(default_factory=list, description='Статус системных механизмов')
    minifilters: List[MinifilterInfo] = Field(default_factory=list, description='Активные минифильтры')
    critical_security_drivers: List[SystemDriverInfo] = Field(default_factory=list, description='Ключевые защитные драйверы')
    recent_verdicts: List[BlockerVerdict] = Field(default_factory=list, description='Недавние расследования блокировок')
