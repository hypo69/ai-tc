# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Нормализация и стандартизация ответов MCP (Result Normalizer)
# =============================================================================
# Description:
#   Формирование единого контракта StandardMCPResponse для всех успешных и
#   ошибочных операций, очистка секретов через SecretRedactor и контроль
#   максимального размера возвращаемого вывода (`max_output_size_mb`).
#
#   Зачем нужен этот модуль:
#     1. Гарантия того, что ни один инструмент не вернёт неструктурированный
#        ответ или превышающий квоту памяти вывод (Раздел 9 ТЗ).
#     2. Единообразные машиночитаемые коды ошибок (ACCESS_DENIED,
#        APPROVAL_REQUIRED, HOST_KEY_REJECTED, TIMEOUT, COMMAND_NOT_FOUND).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.result_normalizer import ResultNormalizer
#     norm = ResultNormalizer(redactor, max_output_size_mb=10)
#     resp = norm.success("srv-1", "linux", "system.memory", {"total_mb": 16384})
#
# File: result_normalizer.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:48:00
# =============================================================================

from typing import Any, Dict, Optional
from ..schemas.execution import ExecutionMetrics, StandardMCPResponse
from ..security.secret_redactor import SecretRedactor


class ResultNormalizer:
    """Нормализатор результатов выполнения команд и ошибок в единый формат MCP.

    Attributes:
        redactor (SecretRedactor): Сервис маскирования секретов.
        max_output_bytes (int): Максимальный размер текстового вывода в байтах.

    Examples:
        >>> norm = ResultNormalizer(SecretRedactor(), max_output_size_mb=1)
        >>> r = norm.success("h1", "linux", "system.info", {"os": "Ubuntu"})
        >>> r["success"]
        True
    """

    def __init__(self, redactor: SecretRedactor, max_output_size_mb: int = 10) -> None:
        """Инициализация нормализатора результатов.

        Args:
            redactor (SecretRedactor): Экземпляр фильтра секретов.
            max_output_size_mb (int): Лимит вывода в мегабайтах.

        Examples:
            >>> norm = ResultNormalizer(SecretRedactor())
        """
        self.redactor = redactor
        self.max_output_bytes = max(1, max_output_size_mb) * 1024 * 1024

    def truncate_text(self, text: str) -> tuple[str, bool]:
        """Усечение строки при превышении допустимого объёма вывода.

        Args:
            text (str): Исходная строка.

        Returns:
            tuple[str, bool]: Кортеж (усечённая_строка, флаг_усечения).

        Examples:
            >>> norm = ResultNormalizer(SecretRedactor(), max_output_size_mb=1)
            >>> norm.truncate_text("hello")
            ('hello', False)
        """
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= self.max_output_bytes:
            return text, False
        clipped = encoded[: self.max_output_bytes].decode("utf-8", errors="ignore")
        return f"{clipped}\n...[TRUNCATED]...", True

    def success(
        self,
        host: str,
        platform: str,
        operation: str,
        data: Optional[Dict[str, Any]] = {},
        duration_ms: int = 0,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> Dict[str, Any]:
        """Формирование стандартизированного успешного ответа MCP.

        Args:
            host (str): Идентификатор узла.
            platform (str): Платформа ('windows' или 'linux').
            operation (str): Идентификатор операции.
            data (Optional[Dict[str, Any]]): Полезная нагрузка результата.
                                             Значение по умолчанию: {}.
            duration_ms (int): Длительность выполнения в мс.
            exit_code (int): Код завершения процесса.
            stdout (str): Поток stdout.
            stderr (str): Поток stderr.

        Returns:
            Dict[str, Any]: Словарь ответа по контракту Раздела 9 ТЗ.

        Examples:
            >>> norm = ResultNormalizer(SecretRedactor())
            >>> res = norm.success("srv-1", "linux", "system.memory", {"total_mb": 1024}, 42, 0)
            >>> res["execution"]["duration_ms"]
            42
        """
        redacted_out = self.redactor.redact_text(stdout)
        redacted_err = self.redactor.redact_text(stderr)
        trunc_out, is_trunc_out = self.truncate_text(redacted_out)
        trunc_err, is_trunc_err = self.truncate_text(redacted_err)

        safe_data = self.redactor.redact_dict(data if data else {})
        resp = StandardMCPResponse(
            success=True,
            host=host,
            platform=platform,
            operation=operation,
            execution=ExecutionMetrics(
                duration_ms=max(0, duration_ms),
                exit_code=exit_code,
                stdout=trunc_out,
                stderr=trunc_err,
                truncated=is_trunc_out or is_trunc_err,
            ),
            data=safe_data,
            error={},
        )
        return resp.to_contract_dict()

    def failure(
        self,
        host: str,
        platform: str,
        operation: str,
        code: str,
        message: str,
        duration_ms: int = 0,
        exit_code: int = 1,
        stdout: str = "",
        stderr: str = "",
        extra_error: Optional[Dict[str, Any]] = {},
    ) -> Dict[str, Any]:
        """Формирование стандартизированного ответа об ошибке MCP.

        Args:
            host (str): Идентификатор узла.
            platform (str): Платформа узла.
            operation (str): Идентификатор операции.
            code (str): Стандартизированный код ошибки (например, ACCESS_DENIED).
            message (str): Описание ошибки.
            duration_ms (int): Время до возникновения ошибки в мс.
            exit_code (int): Код возврата (по умолчанию 1).
            stdout (str): Стандартный вывод.
            stderr (str): Вывод ошибок.
            extra_error (Optional[Dict[str, Any]]): Дополнительные поля ошибки (approval_id и др.).
                                                    Значение по умолчанию: {}.

        Returns:
            Dict[str, Any]: Словарь ошибки по контракту Раздела 9 ТЗ.

        Examples:
            >>> norm = ResultNormalizer(SecretRedactor())
            >>> err = norm.failure("win-01", "windows", "service.restart", "ACCESS_DENIED", "Denied")
            >>> err["success"]
            False
            >>> err["error"]["code"]
            'ACCESS_DENIED'
        """
        err_dict: Dict[str, Any] = {
            "code": code,
            "message": self.redactor.redact_text(message),
        }
        if extra_error:
            err_dict.update(self.redactor.redact_dict(extra_error))

        resp = StandardMCPResponse(
            success=False,
            host=host,
            platform=platform,
            operation=operation,
            execution=ExecutionMetrics(
                duration_ms=max(0, duration_ms),
                exit_code=exit_code,
                stdout=self.redactor.redact_text(stdout),
                stderr=self.redactor.redact_text(stderr),
            ),
            data={},
            error=err_dict,
        )
        return resp.to_contract_dict()
