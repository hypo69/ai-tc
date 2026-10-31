# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Registry - Router
# =============================================================================
# Description:
#   FastAPI роутер для приложения Windows Registry Viewer.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.registry.router import init_router
#
#     res = init_router()
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.registry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:37:55
# =============================================================================

from __future__ import annotations
"""FastAPI роутер для приложения Windows Registry Viewer."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from apps.windows.registry.models import BookmarkItem, CreateKeyRequestDTO, DeleteKeyRequestDTO, DeleteValueRequestDTO, EditOperationResultDTO, RegistryKeyDetailsDTO, RestoreBackupResponseDTO, SearchResponseDTO, SetValueRequestDTO
from apps.windows.registry.viewer import RegistryViewer
from apps.common.telemetry_logger import AppTelemetryLogger

def init_router(viewer: Optional[RegistryViewer]=None) -> APIRouter:
    """Инициализировать и вернуть FastAPI роутер Registry Viewer."""
    registry_engine = viewer or RegistryViewer()
    router = APIRouter(prefix='/api/registry', tags=['registry-viewer'])
    telemetry_logger = AppTelemetryLogger('registry_viewer')

    @router.get('/bookmarks')
    async def get_bookmarks() -> Dict[str, Any]:
        """Получить список быстрых системных закладок реестра."""
        bookmarks = registry_engine.get_bookmarks()
        telemetry_logger.log_poll(poll_type='bookmarks', metric_name='bookmarks_count', value=len(bookmarks), unit='count', status='ok')
        return {'status': 'ok', 'bookmarks': [bm.model_dump() for bm in bookmarks]}

    @router.get('/key', response_model=RegistryKeyDetailsDTO)
    async def get_key_details(hive: str=Query(default='HKEY_LOCAL_MACHINE', description='Корневая ветка реестра (HKLM, HKCU и др.)'), path: str=Query(default='', description='Относительный путь к разделу реестра')) -> RegistryKeyDetailsDTO:
        """Получить список подразделов и параметров указанного ключа реестра."""
        try:
            return registry_engine.read_key(hive=hive, path=path)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/search', response_model=SearchResponseDTO)
    async def search_registry(hive: str=Query(default='HKEY_LOCAL_MACHINE', description='Корневая ветка для поиска'), path: str=Query(default='SOFTWARE', description='Базовый путь поиска'), query: str=Query(..., min_length=2, description='Поисковая строка'), max_results: int=Query(default=50, ge=1, le=200, description='Максимум результатов')) -> SearchResponseDTO:
        """Поиск ключей, параметров и значений в системном реестре."""
        try:
            res = registry_engine.search(query=query, hive=hive, path=path, max_results=max_results)
            telemetry_logger.log_event(event_type='registry_search', status='ok', details=f'hive={hive},path={path},query={query},results={res.total_found}')
            return res
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/export')
    async def export_key(hive: str=Query(default='HKEY_LOCAL_MACHINE', description='Корневая ветка'), path: str=Query(default='', description='Путь ключа'), format: str=Query(default='json', enum=['json', 'csv'], description='Формат экспорта')) -> Response:
        """Экспорт параметров ключа реестра в JSON или CSV."""
        try:
            details = registry_engine.read_key(hive=hive, path=path)
            telemetry_logger.log_event(event_type='registry_export', status='ok', details=f'hive={hive},path={path},format={format},values_count={len(details.values)}')
            if format == 'csv':
                csv_data = registry_engine.export_key_to_csv(details)
                return Response(content=csv_data, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="registry_export.csv"'})
            json_data = registry_engine.export_key_to_json(details)
            return Response(content=json_data, media_type='application/json', headers={'Content-Disposition': 'attachment; filename="registry_export.json"'})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/value', response_model=EditOperationResultDTO)
    async def set_value(req: SetValueRequestDTO) -> EditOperationResultDTO:
        """Создать или изменить параметр реестра с созданием снимка резервной копии."""
        try:
            res = registry_engine.set_value(req)
            telemetry_logger.log_param_change(param_name=f'{req.hive}\\{req.path}\\{req.name}', old_value='<previous>', new_value=str(req.data), status='success' if res.status == 'ok' else 'error', details=f"type={req.type_name},backup={(res.backup.backup_id if res.backup else '')}")
            return res
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete('/value', response_model=EditOperationResultDTO)
    async def delete_value(req: DeleteValueRequestDTO) -> EditOperationResultDTO:
        """Удалить параметр реестра с созданием снимка резервной копии."""
        try:
            res = registry_engine.delete_value(req)
            telemetry_logger.log_param_change(param_name=f'{req.hive}\\{req.path}\\{req.name}', old_value='<deleted>', new_value='<null>', status='success' if res.status == 'ok' else 'error', details=f"backup={(res.backup.backup_id if res.backup else '')}")
            return res
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/key', response_model=EditOperationResultDTO)
    async def create_key(req: CreateKeyRequestDTO) -> EditOperationResultDTO:
        """Создать новый раздел в реестре."""
        try:
            res = registry_engine.create_key(req)
            telemetry_logger.log_event(event_type='create_key', status='success' if res.status == 'ok' else 'error', details=f'hive={req.hive},path={req.path}')
            return res
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete('/key', response_model=EditOperationResultDTO)
    async def delete_key(req: DeleteKeyRequestDTO) -> EditOperationResultDTO:
        """Удалить раздел реестра с созданием снимка резервной копии."""
        try:
            res = registry_engine.delete_key(req)
            telemetry_logger.log_event(event_type='delete_key', status='success' if res.status == 'ok' else 'error', details=f"hive={req.hive},path={req.path},backup={(res.backup.backup_id if res.backup else '')}")
            return res
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/backups')
    async def list_backups() -> Dict[str, Any]:
        """Получить список всех резервных копий реестра."""
        try:
            backups = registry_engine.list_backups()
            telemetry_logger.log_poll(poll_type='backups', metric_name='backups_count', value=len(backups), unit='count', status='ok')
            return {'status': 'ok', 'total': len(backups), 'backups': [b.model_dump() for b in backups]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/restore', response_model=RestoreBackupResponseDTO)
    async def restore_backup(backup_id: str=Query(..., description='ID резервной копии для восстановления')) -> RestoreBackupResponseDTO:
        """Восстановить раздел реестра из снимка бэкапа."""
        try:
            res = registry_engine.restore_backup(backup_id)
            telemetry_logger.log_event(event_type='restore_backup', status='success' if res.success else 'error', details=f'backup_id={backup_id},restored_keys={res.restored_keys_count},restored_values={res.restored_values_count}')
            return res
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return router
