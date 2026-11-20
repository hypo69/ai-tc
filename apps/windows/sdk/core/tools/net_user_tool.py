# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Core Tools - Net User Tool
# =============================================================================
# Description:
#   Инструмент прямого управления локальными учетными записями Windows через net user.
#   Поддерживает аудит, изменение паролей, флагов PasswordRequired/Active,
#   а также опасные операции удаления пользователей (/delete).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tools.net_user_tool import NetUserTool
#
#     tool = NetUserTool()
#     res = await tool.execute(action="get", username="user")
#
# File: net_user_tool.py
# Project: ai-tc
# Package: apps.windows.sdk.core.tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations

"""Инструмент прямого управления локальными учетными записями Windows через net user."""

import asyncio
import platform
import re
import subprocess
from typing import Any, Dict, List, Optional

from logger import logger
from apps.windows.sdk.core.models import RiskLevel
from apps.windows.sdk.core.tools.base import BaseTool, ToolExecutionResult


class NetUserTool(BaseTool):
    """Инструмент управления локальными учетными записями Windows через утилиту net user."""

    name = "net_user"
    title = "Управление учетными записями (net user)"
    description = (
        "Управляет локальными пользователями Windows с помощью встроенной утилиты 'net user'. "
        "Поддерживает аудит списка пользователей (list), детальные свойства учетной записи (get: "
        "флаги Password required, Account active, группы), смену паролей (set_password), установку "
        "обязательности пароля (set_password_required: /passwordreq:yes|no), блокировку/разблокировку "
        "(set_active: /active:yes|no), создание пользователей (create: /add) и радикальные деструктивные "
        "операции полного удаления учетных записей (delete: /delete), а также членство в локальных "
        "группах (group_add, group_delete через net localgroup)."
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list",
                    "get",
                    "set_password",
                    "set_password_required",
                    "set_active",
                    "set_password_changeable",
                    "set_logon_password_change",
                    "set_expires",
                    "set_fullname",
                    "set_comment",
                    "modify",
                    "create",
                    "delete",
                    "group_add",
                    "group_delete",
                    "raw",
                ],
                "description": (
                    "Действие для выполнения: list (список всех пользователей), get (детальные свойства), "
                    "set_password (задать пароль), set_password_required (установить требование пароля), "
                    "set_active (активировать или заблокировать), set_password_changeable (разрешить/запретить смену пароля), "
                    "set_logon_password_change (требовать смену пароля при следующем входе), set_expires (срок действия), "
                    "set_fullname (полное имя), set_comment (описание), modify (пакетное изменение параметров net user), "
                    "create (создать пользователя), delete (безвозвратно удалить пользователя), "
                    "group_add/group_delete (членство в группе), raw (произвольные аргументы для net user)."
                ),
            },
            "username": {
                "type": "string",
                "description": "Имя локальной учетной записи (например: 'user', 'Administrator').",
            },
            "password": {
                "type": "string",
                "description": "Новый или временный пароль для учетной записи.",
            },
            "password_required": {
                "type": "boolean",
                "description": "Флаг обязательности пароля (/passwordreq:yes|no). True = yes, False = no.",
            },
            "active": {
                "type": "boolean",
                "description": "Флаг активности учетной записи (/active:yes|no). True = yes, False = no.",
            },
            "password_changeable": {
                "type": "boolean",
                "description": "Флаг разрешения пользователю менять пароль (/passwordchg:yes|no). True = yes, False = no.",
            },
            "logon_password_change": {
                "type": "boolean",
                "description": "Требовать смену пароля при следующем входе (/logonpasswordchg:yes|no). True = yes, False = no.",
            },
            "expires": {
                "type": "string",
                "description": "Срок действия учетной записи (/expires:never или дата MM/DD/YYYY).",
            },
            "full_name": {
                "type": "string",
                "description": "Полное имя пользователя (/fullname:\"...\").",
            },
            "comment": {
                "type": "string",
                "description": "Описание / комментарий к учетной записи (/comment:\"...\").",
            },
            "user_comment": {
                "type": "string",
                "description": "Пользовательский служебный комментарий (/usercomment:\"...\").",
            },
            "homedir": {
                "type": "string",
                "description": "Путь к домашней директории пользователя (/homedir:\"...\").",
            },
            "profilepath": {
                "type": "string",
                "description": "Путь к сетевому профилю пользователя (/profilepath:\"...\").",
            },
            "scriptpath": {
                "type": "string",
                "description": "Путь к скрипту входа (/scriptpath:\"...\").",
            },
            "times": {
                "type": "string",
                "description": "Часы разрешенного входа (/times:all или M-F,8am-5pm).",
            },
            "workstations": {
                "type": "string",
                "description": "Список разрешенных рабочих станций (/workstations:... или *).",
            },
            "countrycode": {
                "type": "integer",
                "description": "Числовой код страны для локализации сообщений (/countrycode:nnn).",
            },
            "domain": {
                "type": "boolean",
                "default": False,
                "description": "Выполнить операцию на контроллере домена (/domain).",
            },
            "group_name": {
                "type": "string",
                "description": "Имя локальной группы (например, 'Администраторы' или 'Administrators').",
            },
            "raw_args": {
                "type": "string",
                "description": "Произвольные дополнительные параметры для команды net user.",
            },
            "confirm_destructive": {
                "type": "boolean",
                "default": True,
                "description": "Явное подтверждение выполнения опасных и деструктивных операций (например, delete).",
            },
        },
        "required": ["action"],
    }

    risk_level = RiskLevel.SAFE

    @staticmethod
    def _parse_user_list(output: str) -> List[str]:
        """Разбирает текстовый вывод 'net user' на список имен пользователей.

        Args:
            output: Текстовый вывод команды net user.

        Returns:
            List[str]: Список имен пользователей.
        """
        users: List[str] = []
        lines = output.splitlines()
        capture = False

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("---"):
                capture = True
                continue
            if "The command completed successfully" in line_str or "Команда успешно выполнена" in line_str:
                break
            if capture:
                # В выводе имена пользователей идут колонками
                tokens = re.split(r"\s{2,}", line.strip())
                for tok in tokens:
                    cleaned = tok.strip()
                    if cleaned and not cleaned.startswith("-"):
                        users.append(cleaned)

        return users

    @staticmethod
    def _parse_user_details(output: str) -> Dict[str, str]:
        """Разбирает детальный вывод 'net user <username>' в словарь атрибутов.

        Args:
            output: Текстовый вывод команды net user <username>.

        Returns:
            Dict[str, str]: Словарь параметров учетной записи.
        """
        details: Dict[str, str] = {}
        for line in output.splitlines():
            line_str = line.strip()
            if not line_str or "The command completed successfully" in line_str or "Команда успешно выполнена" in line_str:
                continue
            parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
            if len(parts) == 2:
                details[parts[0].strip()] = parts[1].strip()
            elif len(parts) == 1 and ":" in parts[0]:
                k, v = parts[0].split(":", 1)
                details[k.strip()] = v.strip()
        return details

    async def execute(
        self,
        action: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        password_required: Optional[bool] = None,
        active: Optional[bool] = None,
        password_changeable: Optional[bool] = None,
        logon_password_change: Optional[bool] = None,
        expires: Optional[str] = None,
        full_name: Optional[str] = None,
        comment: Optional[str] = None,
        user_comment: Optional[str] = None,
        homedir: Optional[str] = None,
        profilepath: Optional[str] = None,
        scriptpath: Optional[str] = None,
        times: Optional[str] = None,
        workstations: Optional[str] = None,
        countrycode: Optional[int] = None,
        domain: bool = False,
        group_name: Optional[str] = None,
        raw_args: Optional[str] = None,
        confirm_destructive: bool = True,
        **kwargs: Any,
    ) -> ToolExecutionResult:
        """Исполнение команды net user на хосте.

        Args:
            action: Тип действия (list, get, modify, set_password, set_password_required, set_active, etc.).
            username: Имя учетной записи.
            password: Новый пароль.
            password_required: Требовать ли пароль (/passwordreq:yes|no).
            active: Активна ли учетная запись (/active:yes|no).
            password_changeable: Разрешить смену пароля (/passwordchg:yes|no).
            logon_password_change: Требовать смену пароля при входе (/logonpasswordchg:yes|no).
            expires: Срок действия (/expires:never|date).
            full_name: Полное имя (/fullname:"...").
            comment: Описание (/comment:"...").
            user_comment: Служебный комментарий (/usercomment:"...").
            homedir: Домашний каталог (/homedir:"...").
            profilepath: Сетевой профиль (/profilepath:"...").
            scriptpath: Скрипт входа (/scriptpath:"...").
            times: Часы входа (/times:...|all).
            workstations: Список рабочих станций (/workstations:...|*).
            countrycode: Код страны (/countrycode:nnn).
            domain: Выполнять на контроллере домена (/domain).
            group_name: Имя группы.
            raw_args: Дополнительные аргументы.
            confirm_destructive: Подтверждение опасной операции.
            **kwargs: Прочие аргументы.

        Returns:
            ToolExecutionResult: Результат выполнения с собранными фактами или статусом.
        """
        action = (action or "list").lower().strip()
        cmd: List[str] = []
        op_risk = RiskLevel.SAFE

        if action == "list":
            cmd = ["net", "user"]
            if domain:
                cmd.append("/domain")

        elif action == "get":
            if not username:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для действия 'get' необходимо указать параметр username.",
                )
            cmd = ["net", "user", username]
            if domain:
                cmd.append("/domain")

        elif action == "set_password":
            if not username or password is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_password' требуются параметры username и password.",
                )
            cmd = ["net", "user", username, password]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "set_password_required":
            if not username or password_required is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_password_required' требуются username и password_required (True/False).",
                )
            flag_val = "yes" if password_required else "no"
            cmd = ["net", "user", username, f"/passwordreq:{flag_val}"]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "set_active":
            if not username or active is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_active' требуются username и active (True/False).",
                )
            flag_val = "yes" if active else "no"
            cmd = ["net", "user", username, f"/active:{flag_val}"]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "set_password_changeable":
            if not username or password_changeable is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_password_changeable' требуются username и password_changeable (True/False).",
                )
            flag_val = "yes" if password_changeable else "no"
            cmd = ["net", "user", username, f"/passwordchg:{flag_val}"]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "set_logon_password_change":
            if not username or logon_password_change is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_logon_password_change' требуются username и logon_password_change (True/False).",
                )
            flag_val = "yes" if logon_password_change else "no"
            cmd = ["net", "user", username, f"/logonpasswordchg:{flag_val}"]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "set_expires":
            if not username or expires is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_expires' требуются username и expires ('never' или дата MM/DD/YYYY).",
                )
            cmd = ["net", "user", username, f"/expires:{expires}"]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "set_fullname":
            if not username or full_name is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_fullname' требуются username и full_name.",
                )
            cmd = ["net", "user", username, f'/fullname:"{full_name}"']
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.MEDIUM

        elif action == "set_comment":
            if not username or comment is None:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'set_comment' требуются username и comment.",
                )
            cmd = ["net", "user", username, f'/comment:"{comment}"']
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.MEDIUM

        elif action in ("modify", "configure"):
            if not username:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для действия 'modify' необходимо указать username.",
                )
            cmd = ["net", "user", username]
            opts_count = 0
            if active is not None:
                cmd.append(f"/active:{'yes' if active else 'no'}")
                opts_count += 1
            if password_required is not None:
                cmd.append(f"/passwordreq:{'yes' if password_required else 'no'}")
                opts_count += 1
            if password_changeable is not None:
                cmd.append(f"/passwordchg:{'yes' if password_changeable else 'no'}")
                opts_count += 1
            if logon_password_change is not None:
                cmd.append(f"/logonpasswordchg:{'yes' if logon_password_change else 'no'}")
                opts_count += 1
            if expires is not None:
                cmd.append(f"/expires:{expires}")
                opts_count += 1
            if full_name is not None:
                cmd.append(f'/fullname:"{full_name}"')
                opts_count += 1
            if comment is not None:
                cmd.append(f'/comment:"{comment}"')
                opts_count += 1
            if user_comment is not None:
                cmd.append(f'/usercomment:"{user_comment}"')
                opts_count += 1
            if homedir is not None:
                cmd.append(f'/homedir:"{homedir}"')
                opts_count += 1
            if profilepath is not None:
                cmd.append(f'/profilepath:"{profilepath}"')
                opts_count += 1
            if scriptpath is not None:
                cmd.append(f'/scriptpath:"{scriptpath}"')
                opts_count += 1
            if times is not None:
                cmd.append(f"/times:{times}")
                opts_count += 1
            if workstations is not None:
                cmd.append(f"/workstations:{workstations}")
                opts_count += 1
            if countrycode is not None:
                cmd.append(f"/countrycode:{countrycode}")
                opts_count += 1
            if domain:
                cmd.append("/domain")

            if opts_count == 0 and not domain:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'modify' не передано ни одного параметра для изменения (/active, /passwordreq, /passwordchg и др.).",
                )
            op_risk = RiskLevel.HIGH

        elif action == "create":
            if not username:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'create' требуется имя пользователя username.",
                )
            cmd = ["net", "user", username]
            if password:
                cmd.append(password)
            cmd.append("/add")
            if active is not None:
                cmd.append(f"/active:{'yes' if active else 'no'}")
            if password_required is not None:
                cmd.append(f"/passwordreq:{'yes' if password_required else 'no'}")
            if password_changeable is not None:
                cmd.append(f"/passwordchg:{'yes' if password_changeable else 'no'}")
            if full_name is not None:
                cmd.append(f'/fullname:"{full_name}"')
            if comment is not None:
                cmd.append(f'/comment:"{comment}"')
            if expires is not None:
                cmd.append(f"/expires:{expires}")
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.HIGH

        elif action == "delete":
            if not username:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для удаления пользователя необходимо передать параметр username.",
                )
            if not confirm_destructive:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message=(
                        f"Удаление учетной записи '{username}' отклонено: требуется явное подтверждение "
                        "confirm_destructive=True (опасная необратимая операция)."
                    ),
                    risk_level=RiskLevel.CRITICAL,
                )
            cmd = ["net", "user", username, "/delete"]
            if domain:
                cmd.append("/domain")
            op_risk = RiskLevel.CRITICAL

        elif action == "group_add":
            if not username or not group_name:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'group_add' требуются username и group_name.",
                )
            cmd = ["net", "localgroup", group_name, username, "/add"]
            op_risk = RiskLevel.HIGH

        elif action == "group_delete":
            if not username or not group_name:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data=None,
                    message="Для 'group_delete' требуются username и group_name.",
                )
            cmd = ["net", "localgroup", group_name, username, "/delete"]
            op_risk = RiskLevel.HIGH

        elif action == "raw":
            cmd = ["net", "user"]
            if raw_args:
                cmd.extend(raw_args.split())
            op_risk = RiskLevel.HIGH

        else:
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                data=None,
                message=f"Неизвестное действие net user: '{action}'",
            )

        cmd_str = " ".join(cmd)

        if platform.system() != "Windows":
            return ToolExecutionResult(
                tool_name=self.name,
                status="ok",
                data={"mock": True, "action": action, "command": cmd_str},
                message=f"Симуляция net user ({cmd_str}) для не-Windows среды.",
                command_executed=cmd_str,
                risk_level=op_risk,
            )

        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                err_msg = stderr or stdout or f"Код ошибки {proc.returncode}"
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data={"stderr": stderr, "stdout": stdout},
                    message=f"Команда '{cmd_str}' завершилась с ошибкой: {err_msg}",
                    command_executed=cmd_str,
                    risk_level=op_risk,
                )

            # Структурирование результатов
            if action == "list":
                parsed = {"users": self._parse_user_list(stdout), "raw": stdout}
                msg = f"Получен список локальных пользователей ({len(parsed['users'])} учетных записей)."
            elif action == "get":
                parsed = self._parse_user_details(stdout)
                msg = f"Получены свойства локальной учетной записи '{username}'."
            else:
                parsed = {"output": stdout, "command": cmd_str}
                msg = f"Команда '{cmd_str}' успешно выполнена."

            return ToolExecutionResult(
                tool_name=self.name,
                status="ok",
                data=parsed,
                message=msg,
                command_executed=cmd_str,
                risk_level=op_risk,
            )

        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                data=None,
                message=f"Превышен таймаут выполнения команды net user: '{cmd_str}'",
                command_executed=cmd_str,
                risk_level=op_risk,
            )
        except Exception as e:
            logger.error(f"[NetUserTool] Ошибка выполнения '{cmd_str}': {e}", exc_info=True)
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                data=None,
                message=f"Сбой выполнения '{cmd_str}': {e}",
                command_executed=cmd_str,
                risk_level=op_risk,
            )

