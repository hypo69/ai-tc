# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli Commands - Sys Param
# =============================================================================
# Description:
#   Команды безопасного управления системными параметрами Windows (sys-param).
#
# Usage Examples:
#   Python API:
#     from scripts.cli.commands.sys_param import register_sys_param_parser
#
#     res = register_sys_param_parser()
#
# File: sys_param.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 22:22:44
# =============================================================================

from __future__ import annotations
from logger import logger
"""Команды безопасного управления системными параметрами Windows (sys-param)."""

import argparse


def register_sys_param_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрация аргументов команды sys-param."""
    sys_param_parser = subparsers.add_parser('sys-param', help='Safe system parameter management & Windows restore points')
    sys_param_subparsers = sys_param_parser.add_subparsers(dest='subcommand', help='Subcommands')
    sys_param_list = sys_param_subparsers.add_parser('list', help='List system parameters')
    sys_param_list.add_argument('--category', '-c', help='Filter by category')
    sys_param_preview = sys_param_subparsers.add_parser('preview', help='Preview/dry-run parameter change')
    sys_param_preview.add_argument('param_id', help='Parameter ID (e.g. sec.uac_level)')
    sys_param_preview.add_argument('value', help='New parameter value')
    sys_param_set = sys_param_subparsers.add_parser('set', help='Apply parameter change safely (auto restore point)')
    sys_param_set.add_argument('param_id', help='Parameter ID (e.g. sec.uac_level)')
    sys_param_set.add_argument('value', help='New parameter value')
    sys_param_subparsers.add_parser('restore-points', help='List Windows restore points')
    sys_param_rp_create = sys_param_subparsers.add_parser('create-rp', help='Create Windows restore point manually')
    sys_param_rp_create.add_argument('description', nargs='?', default='AI-Windows-Admin Manual Checkpoint', help='Description')
    sys_param_history = sys_param_subparsers.add_parser('history', help='View parameter change history')
    sys_param_history.add_argument('--limit', '-n', type=int, default=20, help='Limit history items')
    sys_param_rollback = sys_param_subparsers.add_parser('rollback', help='Rollback parameter change')
    sys_param_rollback.add_argument('change_id', help='Change ID from history')


def run_sys_param_command(args: argparse.Namespace) -> int:
    """Управление параметрами системы и точками восстановления Windows."""
    from apps.windows.core.system_param_manager import SafeSystemParamManager
    from apps.windows.core.system_restore import WindowsSystemRestoreManager
    restore_mgr = WindowsSystemRestoreManager()
    manager = SafeSystemParamManager(restore_manager=restore_mgr)
    sub = args.subcommand
    if sub == 'list':
        category = getattr(args, 'category', None)
        params = manager.list_parameters(category=category)
        logger.console(f"\n{'ID':<25} | {'SENSITIVE':<10} | {'RISK':<9} | {'CURRENT VALUE':<20} | NAME")
        logger.console('-' * 90)
        for p in params:
            sens_str = 'YES [RP]' if p['is_sensitive'] else 'NO'
            logger.console(f"{p['param_id']:<25} | {sens_str:<10} | {p['risk'].upper():<9} | {str(p['current_value']):<20} | {p['name']}")
        logger.console(f'\nВсего параметров: {len(params)}\n')
        return 0
    if sub == 'preview':
        param_id = getattr(args, 'param_id', '')
        val = getattr(args, 'value', '')
        res = manager.preview_change(param_id, val)
        if not res.get('success'):
            logger.console(f"Ошибка: {res.get('error')}")
            return 1
        logger.console(f'\n--- СИМУЛЯЦИЯ ИЗМЕНЕНИЯ ПАРАМЕТРА ---')
        logger.console(f"Параметр:          {res['name']} ({res['param_id']})")
        logger.console(f"Текущее значение:  {res['current_value']}")
        logger.console(f"Новое значение:    {res['new_value']}")
        logger.console(f"Чувствительный:    {('ДА' if res['is_sensitive'] else 'НЕТ')}")
        logger.console(f"Уровень риска:     {res['risk'].upper()}")
        logger.console(f"Точка восстан.:    {('БУДЕТ СОЗДАНА АВТОМАТИЧЕСКИ' if res['will_create_restore_point'] else 'Не требуется')}")
        if res.get('restore_point_description'):
            logger.console(f"Описание точки:    {res['restore_point_description']}")
        logger.console('------------------------------------\n')
        return 0
    if sub == 'set':
        param_id = getattr(args, 'param_id', '')
        val = getattr(args, 'value', '')
        if val.lower() == 'true':
            parsed_val = True
        elif val.lower() == 'false':
            parsed_val = False
        elif val.isdigit():
            parsed_val = int(val)
        else:
            parsed_val = val
        logger.console(f"Применение изменения для '{param_id}' -> '{parsed_val}'...")
        res = manager.apply_change(param_id, parsed_val)
        if res.get('status') == 'SUCCESS':
            logger.console(f"\n[OK] {res.get('message')}")
            if res.get('restore_point'):
                rp = res['restore_point']
                logger.console(f"  [RP] Точка восстановления Windows: {rp.get('message', 'Создана')} (Статус: {rp.get('success')})")
            logger.console(f"  Change ID: {res.get('change_id')}\n")
            return 0
        else:
            logger.console(f"\n[ERROR] {res.get('message')}\n")
            return 1
    if sub == 'restore-points':
        points = restore_mgr.list_restore_points()
        status = restore_mgr.check_protection_status()
        logger.console(f'\n--- ТОЧКИ ВОССТАНОВЛЕНИЯ WINDOWS ---')
        logger.console(f"Защита системы (Диск C:): {('ВКЛЮЧЕНА' if status.get('system_protection_enabled') else 'ОТКЛЮЧЕНА / НЕДОСТУПНА')}")
        logger.console(f"{'#':<6} | {'ДАТА СОЗДАНИЯ':<22} | {'ТИП':<20} | ОПИСАНИЕ")
        logger.console('-' * 80)
        for pt in points:
            logger.console(f"{pt['sequence_number']:<6} | {pt['creation_time']:<22} | {pt['restore_point_type']:<20} | {pt['description']}")
        logger.console(f'\nВсего точек: {len(points)}\n')
        return 0
    if sub == 'create-rp':
        desc = getattr(args, 'description', '')
        if not desc:
            desc = 'AI-Windows-Admin Manual Checkpoint'
        logger.console(f"Создание точки восстановления Windows: '{desc}'...")
        res = restore_mgr.create_restore_point(desc)
        if res.get('success'):
            logger.console(f"[OK] {res.get('message')}")
            return 0
        else:
            logger.console(f"[ERROR] {res.get('message')}")
            return 1
    if sub == 'history':
        history = manager.get_history(limit=getattr(args, 'limit', 20))
        logger.console(f'\n--- ЖУРНАЛ ИЗМЕНЕНИЙ ПАРАМЕТРОВ ---')
        for h in history:
            rb_tag = ' [ROLLED BACK]' if h.get('rolled_back') else ''
            rp_tag = ' [RP CREATED]' if h.get('restore_point') and h['restore_point'].get('success') else ''
            logger.console(f"[{h.get('timestamp')}] {h.get('param_name')} ({h.get('param_id')}){rb_tag}{rp_tag}")
            logger.console(f"   {h.get('old_value')} -> {h.get('new_value')} | Status: {h.get('status')} | ID: {h.get('change_id')}")
        logger.console(f'\nВсего записей: {len(history)}\n')
        return 0
    if sub == 'rollback':
        cid = getattr(args, 'change_id', '')
        res = manager.rollback_change(cid)
        if res.get('status') == 'SUCCESS':
            logger.console(f"[OK] {res.get('message')}")
            return 0
        else:
            logger.console(f"[ERROR] {res.get('message')}")
            return 1
    logger.console(f'Неизвестная подкоманда sys-param: {sub}')
    return 1

