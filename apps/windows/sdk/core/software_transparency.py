# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core - Software Transparency
# =============================================================================
# Description:
#   Модуль инспекции прозрачности ПО, анализа конфигураций, мест хранения и сетевых доменов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.software_transparency import init_software_transparency_router
#
# File: software_transparency.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:59:00
# =============================================================================

from __future__ import annotations
"""Модуль инспекции прозрачности ПО, анализа конфигураций, мест хранения и сетевых доменов."""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.sdk.core.software_transparency_analyzers import (
    ConfigFile,
    ConfigFileSaveRequest,
    ConfigInspector,
    EvidenceStatus,
    FullScanReport,
    GeminiAppResearch,
    NetworkEndpoint,
    NetworkTracker,
    ResearchRequest,
    ScanSummary,
    SoftwareInventory,
    SoftwareItem,
    StorageAnalyzer,
    StorageCategory,
    StorageDirectory,
)


class GeminiResearcher:
    """ИИ-исследователь прозрачности ПО через Google Gemini."""

    def __init__(self, chat_provider: Optional[Any] = None) -> None:
        self.chat_provider = chat_provider

    async def research_software(self, app: SoftwareItem) -> GeminiAppResearch:
        """Выполняет аналитическое исследование программы через LLM или эвристику."""
        if self.chat_provider and hasattr(self.chat_provider, 'generate_response'):
            try:
                prompt = f'Проанализируй программу {app.name} версии {app.version} от {app.publisher}.'
                resp = await self.chat_provider.generate_response(prompt)
                parsed = self._parse_json(resp, app.name)
                if parsed:
                    return parsed
            except Exception as ex:
                logger.debug(f'Ошибка вызова Gemini provider: {ex}')
        return self._generate_fallback(app)

    def _parse_json(self, text: str, app_name: str) -> Optional[GeminiAppResearch]:
        try:
            clean = text.strip().strip('`').replace('json', '').strip()
            data = json.loads(clean)
            return GeminiAppResearch(
                app_name=app_name,
                summary=data.get('summary', ''),
                config_purpose_explanation=data.get('config_purpose_explanation', ''),
                data_storage_explanation=data.get('data_storage_explanation', ''),
                network_activity_explanation=data.get('network_activity_explanation', ''),
                confirmed_facts=data.get('confirmed_facts', []),
                inferred_facts=data.get('inferred_facts', []),
                unknown_aspects=data.get('unknown_aspects', []),
                confidence_level=data.get('confidence_level', 'Средний'),
            )
        except Exception:
            return None

    def _generate_fallback(self, app: SoftwareItem) -> GeminiAppResearch:
        return GeminiAppResearch(
            app_name=app.name,
            summary=app.purpose_description or f'Программа {app.name} от разработчика {app.publisher}. Версия: {app.version}.',
            config_purpose_explanation='Параметры работы и пользовательские настройки.',
            data_storage_explanation='Локальные каталоги %APPDATA% и %LOCALAPPDATA%.',
            network_activity_explanation='Проверка обновлений и взаимодействия по сетевым протоколам.',
            confirmed_facts=[f'ПО установлено в системе ({app.name})', f'Издатель: {app.publisher}'],
            inferred_facts=['Использует стандартную структуру расположения данных Windows'],
            unknown_aspects=['Детали проприетарных протоколов сети'],
            confidence_level='Подтверждено документацией',
        )


def _map_db_to_software_item(app_dict: Dict[str, Any]) -> SoftwareItem:
    """Преобразование записи БД в объект SoftwareItem."""
    storage_dirs: List[StorageDirectory] = []
    for loc in app_dict.get('storage_locations', []):
        cat_str = loc.get('category', 'unknown')
        try:
            category_enum = StorageCategory(cat_str)
        except Exception:
            category_enum = StorageCategory.UNKNOWN
        storage_dirs.append(StorageDirectory(
            path=loc.get('path', ''),
            display_path=loc.get('display_path') or loc.get('path', ''),
            category=category_enum,
            description=loc.get('description', ''),
            file_count=int(loc.get('file_count', 0) or 0),
            total_size_bytes=int(loc.get('size_bytes', 0) or 0),
            status=EvidenceStatus.LOCAL_OBSERVED,
        ))

    cfg_files: List[ConfigFile] = []
    for cf in app_dict.get('config_files', []):
        f_path = cf.get('file_path') or cf.get('path', '')
        cfg_files.append(ConfigFile(
            path=f_path,
            display_path=cf.get('display_path') or f_path,
            filename=Path(f_path).name if f_path else 'config',
            format=cf.get('format', 'unknown'),
            size_bytes=int(cf.get('size_bytes', 0) or 0),
            purpose=cf.get('purpose', 'Настройки программы'),
            sample_content=cf.get('snippet') or cf.get('sample_content'),
            status=EvidenceStatus.LOCAL_OBSERVED,
        ))

    net_eps: List[NetworkEndpoint] = []
    for ne in app_dict.get('network_endpoints', []):
        if isinstance(ne, dict) and ne.get('domain_or_ip'):
            net_eps.append(NetworkEndpoint(
                domain_or_ip=ne['domain_or_ip'],
                port=ne.get('port'),
                protocol=ne.get('protocol', 'HTTPS'),
                source=ne.get('source', 'observed'),
                purpose=ne.get('purpose', ''),
            ))

    ai_research = None
    if app_dict.get('ai_research'):
        ai_data = app_dict['ai_research']
        ai_research = GeminiAppResearch(
            app_name=app_dict.get('display_name', ''),
            summary=ai_data.get('summary', ''),
            config_purpose_explanation=ai_data.get('config_purpose_explanation', ''),
            data_storage_explanation=ai_data.get('data_storage_explanation', ''),
            network_activity_explanation=ai_data.get('network_activity_explanation', ''),
            confirmed_facts=ai_data.get('confirmed_facts', []),
            inferred_facts=ai_data.get('inferred_facts', []),
            confidence_level=str(ai_data.get('confidence_level', 'Средний')),
        )

    exec_info = app_dict.get('execution_info') or {}
    exe_path = app_dict.get('executable_path') or (exec_info.get('raw_path') if isinstance(exec_info, dict) else None)

    return SoftwareItem(
        id=app_dict.get('app_id', ''),
        name=app_dict.get('display_name') or app_dict.get('name', ''),
        version=app_dict.get('version') or 'Не указана',
        publisher=app_dict.get('publisher') or 'Неизвестен',
        install_location=app_dict.get('install_location') or None,
        executable_path=exe_path,
        uninstall_string=app_dict.get('uninstall_string') or None,
        architecture=app_dict.get('architecture') or 'x64',
        install_date=app_dict.get('install_date') or None,
        registry_key=app_dict.get('registry_key') or None,
        category=app_dict.get('category') or 'Прочее ПО',
        purpose_description=app_dict.get('purpose_description') or '',
        size_bytes=int(app_dict.get('size_bytes', 0) or 0),
        is_system_component=bool(app_dict.get('is_system_component', False)),
        last_run_time=app_dict.get('last_run_time'),
        run_count=int(app_dict.get('run_count', 0) or 0),
        config_files=cfg_files,
        data_directories=storage_dirs,
        network_endpoints=net_eps,
        ai_research=ai_research,
    )


def init_software_transparency_router(
    chat_provider: Optional[Any] = None,
    chat_model: Optional[Any] = None,
    **kwargs: Any,
) -> APIRouter:
    """Инициализация FastAPI роутера сканера прозрачности ПО на базе SQLite."""
    active_model = chat_provider or chat_model
    router = APIRouter(prefix='/api/v1/software-scanner', tags=['AI Software Transparency Scanner'])
    storage = TelemetryStorage.get_instance()
    inventory = SoftwareInventory()
    storage_analyzer = StorageAnalyzer()
    config_inspector = ConfigInspector()
    network_tracker = NetworkTracker()
    researcher = GeminiResearcher(chat_provider=active_model)
    _cache: Dict[str, SoftwareItem] = {}
    _last_summary: Optional[ScanSummary] = None

    def _execute_full_scan_sync(save_to_db: bool = False) -> FullScanReport:
        nonlocal _cache, _last_summary
        start_time = time.time()
        storage_analyzer.reset_cache()
        network_tracker.reset_cache()
        apps = inventory.scan_installed_software()
        _cache = {}
        total_configs = 0
        total_domains = 0
        total_bytes = 0

        inventory_records = []
        storage_locations = []
        config_files_records = []
        ai_research_records = []

        for app in apps:
            dirs = storage_analyzer.discover_storage_for_app(app)
            app.data_directories = dirs
            app.windows_services = storage_analyzer.discover_services_for_app(app)
            dir_bytes = sum(d.total_size_bytes for d in dirs)
            total_bytes += dir_bytes
            if app.size_bytes == 0 and dir_bytes > 0:
                app.size_bytes = dir_bytes
            for d in dirs:
                storage_locations.append({
                    'app_id': app.id,
                    'category': d.category.value if hasattr(d.category, 'value') else str(d.category),
                    'path': d.path,
                    'display_path': d.display_path,
                    'description': d.description,
                    'size_bytes': d.total_size_bytes,
                    'file_count': d.file_count,
                })

            cfgs = config_inspector.inspect_directories_for_configs(dirs)
            app.config_files = cfgs
            total_configs += len(cfgs)
            for c in cfgs:
                config_files_records.append({
                    'app_id': app.id,
                    'file_path': c.path,
                    'display_path': c.display_path,
                    'format': c.format,
                    'size_bytes': c.size_bytes,
                    'purpose': c.purpose,
                    'snippet': c.sample_content,
                })

            nets = network_tracker.track_app_network(app, cfgs)
            app.network_endpoints = nets
            total_domains += len(nets)

            inventory_records.append({
                'app_id': app.id,
                'display_name': app.name,
                'version': app.version,
                'publisher': app.publisher,
                'install_date': app.install_date,
                'install_location': app.install_location,
                'architecture': app.architecture,
                'is_system_component': app.is_system_component,
                'uninstall_string': app.uninstall_string,
                'size_bytes': app.size_bytes,
                'category': app.category,
                'purpose_description': app.purpose_description,
                'registry_key': app.registry_key,
            })

            if app.ai_research:
                ai_research_records.append({
                    'app_id': app.id,
                    'summary': app.ai_research.summary,
                    'config_purpose_explanation': app.ai_research.config_purpose_explanation,
                    'data_storage_explanation': app.ai_research.data_storage_explanation,
                    'network_activity_explanation': app.ai_research.network_activity_explanation,
                    'confirmed_facts': app.ai_research.confirmed_facts,
                    'inferred_facts': app.ai_research.inferred_facts,
                    'confidence_level': 1.0 if app.ai_research.confidence_level == 'Высокий' else 0.5,
                })

            _cache[app.id] = app

        if save_to_db:
            try:
                storage.save_software_inventory(
                    apps=inventory_records,
                    storage_locations=storage_locations,
                    config_files=config_files_records,
                    ai_research=ai_research_records,
                )
            except Exception as ex:
                logger.debug(f'Ошибка сохранения инвентаря ПО в SQLite: {ex}')

        dur = round(time.time() - start_time, 2)
        _last_summary = ScanSummary(
            total_apps=len(_cache),
            total_configs_found=total_configs,
            total_network_domains=total_domains,
            total_storage_bytes=total_bytes,
            scan_duration_sec=dur,
            last_scan_time=time.strftime('%Y-%m-%dT%H:%M:%S'),
        )
        return FullScanReport(summary=_last_summary, apps=list(_cache.values()))

    async def _execute_full_scan(save_to_db: bool = False) -> FullScanReport:
        return await asyncio.to_thread(_execute_full_scan_sync, save_to_db)

    @router.get('/status')
    async def get_status() -> Dict[str, Any]:
        return {
            'status': 'online',
            'service': 'AI Software Transparency Scanner',
            'version': '1.0.0',
            'cached_apps_count': len(_cache),
        }

    @router.get('/scan', response_model=FullScanReport)
    @router.post('/scan', response_model=FullScanReport)
    async def run_full_scan(
        force_refresh: bool = Query(False, description='Принудительно пересканировать'),
        save_to_db: bool = Query(False, description='Сохранять результат в базу данных телеметрии')
    ) -> FullScanReport:
        nonlocal _cache, _last_summary
        has_enriched_cache = bool(
            _cache and (
                sum(len(it.config_files) for it in _cache.values()) > 0
                or sum(len(it.network_endpoints) for it in _cache.values()) > 0
            )
        )
        if not has_enriched_cache or force_refresh:
            if not force_refresh:
                db_apps = storage.get_software_inventory_from_db(limit=500)
                if db_apps:
                    temp_cache: Dict[str, SoftwareItem] = {}
                    for a in db_apps:
                        details = storage.get_software_app_details_from_db(a.get('app_id', ''))
                        if details:
                            item = _map_db_to_software_item(details)
                            temp_cache[item.id] = item
                    cfg_total = sum(len(it.config_files) for it in temp_cache.values())
                    net_total = sum(len(it.network_endpoints) for it in temp_cache.values())
                    if temp_cache and (cfg_total > 0 and net_total > 0):
                        _cache = temp_cache
                        _last_summary = ScanSummary(
                            total_apps=len(_cache),
                            total_configs_found=cfg_total,
                            total_network_domains=net_total,
                            total_storage_bytes=sum(sum(d.total_size_bytes for d in it.data_directories) for it in _cache.values()),
                            scan_duration_sec=0.01,
                            last_scan_time=time.strftime('%Y-%m-%dT%H:%M:%S'),
                        )
                        return FullScanReport(summary=_last_summary, apps=list(_cache.values()))

            return await _execute_full_scan(save_to_db)
        return FullScanReport(summary=_last_summary or ScanSummary(total_apps=len(_cache)), apps=list(_cache.values()))

    @router.post('/refresh')
    async def refresh_software(
        save_to_db: bool = Query(False, description='Сохранять в базу данных телеметрии')
    ) -> Dict[str, Any]:
        """Принудительное пересканирование ПО."""
        report = await _execute_full_scan(save_to_db)
        return {'status': 'ok', 'message': 'Инвентаризация ПО обновлена', 'total_apps': report.summary.total_apps}

    @router.get('/apps', response_model=List[SoftwareItem])
    async def get_apps(limit: int = 200, offset: int = 0) -> List[SoftwareItem]:
        """Возвращает список установленных программ с поддержкой холодного старта."""
        if not _cache:
            await _execute_full_scan()
        return list(_cache.values())[offset:offset + limit] if offset or limit < len(_cache) else list(_cache.values())

    @router.get('/apps/{app_id}', response_model=SoftwareItem)
    async def get_app_details(app_id: str) -> SoftwareItem:
        """Возвращает карточку программы из кэша или базы данных SQLite."""
        if not _cache:
            await _execute_full_scan()
        if app_id in _cache:
            return _cache[app_id]
        for k, v in _cache.items():
            if app_id.lower() in k.lower() or app_id.lower() in v.name.lower():
                return v
        raise HTTPException(status_code=404, detail=f"Программа с ID '{app_id}' не найдена")

    def _resolve_known_config_path(path: str) -> Path:
        """Проверяет, что путь принадлежит файлу конфигурации, найденному сканером."""
        norm = os.path.normcase(os.path.abspath(path))
        known = {
            os.path.normcase(os.path.abspath(c.path))
            for app in _cache.values()
            for c in app.config_files
        }
        if norm not in known:
            raise HTTPException(status_code=403, detail='Файл не входит в список обнаруженных конфигураций')
        target = Path(norm)
        if not target.is_file():
            raise HTTPException(status_code=404, detail='Файл не найден')
        return Path(os.path.abspath(path))

    @router.get('/config-file')
    async def read_config_file(path: str = Query(..., description='Абсолютный путь к файлу конфигурации')) -> Dict[str, Any]:
        """Возвращает полное содержимое обнаруженного файла конфигурации для редактирования."""
        if not _cache:
            await _execute_full_scan()
        target = _resolve_known_config_path(path)
        if target.stat().st_size > config_inspector.max_file_size_bytes:
            raise HTTPException(status_code=413, detail='Файл превышает лимит размера 256 KB')
        content = await asyncio.to_thread(target.read_text, encoding='utf-8', errors='replace')
        return {'path': str(target), 'content': content}

    @router.put('/config-file')
    async def save_config_file(req: ConfigFileSaveRequest) -> Dict[str, Any]:
        """Сохраняет отредактированное содержимое обнаруженного файла конфигурации."""
        target = _resolve_known_config_path(req.path)
        if len(req.content.encode('utf-8')) > config_inspector.max_file_size_bytes:
            raise HTTPException(status_code=413, detail='Содержимое превышает лимит размера 256 KB')
        try:
            await asyncio.to_thread(target.write_text, req.content, encoding='utf-8', newline='')
        except OSError as exc:
            logger.error(f'Не удалось сохранить файл конфигурации {target}: {exc}')
            raise HTTPException(status_code=500, detail=f'Ошибка записи файла: {exc}')
        logger.info(f'Файл конфигурации сохранён: {target}')
        return {'status': 'ok', 'path': str(target)}

    @router.post('/research', response_model=GeminiAppResearch)
    async def research_app(req: ResearchRequest) -> GeminiAppResearch:
        """Запуск ИИ-исследования программы и сохранение результата в SQLite."""
        if not _cache:
            await _execute_full_scan()
        target_app = _cache.get(req.app_id)
        if not target_app:
            for k, v in _cache.items():
                if req.app_id.lower() in k.lower() or req.app_id.lower() in v.name.lower():
                    target_app = v
                    break
        if not target_app:
            raise HTTPException(status_code=404, detail=f"Программа '{req.app_id}' не найдена для исследования")

        if target_app.ai_research and (not req.force_refresh):
            return target_app.ai_research

        research_res = await researcher.research_software(target_app)
        target_app.ai_research = research_res

        try:
            storage.save_software_inventory(
                apps=[],
                storage_locations=[],
                config_files=[],
                ai_research=[{
                    'app_id': target_app.id,
                    'summary': research_res.summary,
                    'config_purpose_explanation': research_res.config_purpose_explanation,
                    'data_storage_explanation': research_res.data_storage_explanation,
                    'network_activity_explanation': research_res.network_activity_explanation,
                    'confirmed_facts': research_res.confirmed_facts,
                    'inferred_facts': research_res.inferred_facts,
                    'confidence_level': 1.0 if research_res.confidence_level == 'Высокий' else 0.5,
                }],
            )
        except Exception as ex:
            logger.debug(f'Ошибка сохранения AI research в SQLite: {ex}')

        return research_res

    return router


__all__ = [
    'StorageCategory',
    'EvidenceStatus',
    'ConfigFile',
    'StorageDirectory',
    'NetworkEndpoint',
    'GeminiAppResearch',
    'SoftwareItem',
    'ScanSummary',
    'FullScanReport',
    'ResearchRequest',
    'ConfigFileSaveRequest',
    'SoftwareInventory',
    'StorageAnalyzer',
    'ConfigInspector',
    'NetworkTracker',
    'GeminiResearcher',
    'init_software_transparency_router',
]
