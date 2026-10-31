# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Log_Intelligence Src - Adaptive Rag
# =============================================================================
# Description:
#   Высокопроизводительный In-Memory (RAM) движок адаптивного RAG-индексирования
#   и семантического поиска по всем системным журналам Windows за последние сутки.
#   Работает исключительно в оперативной памяти без обращений к базам данных.
#
# Usage Examples:
#   Python API:
#     from apps.windows.log_intelligence.src.adaptive_rag import AdaptiveLogRAG
#
#     rag = AdaptiveLogRAG()
#     rag.index_all_system_logs(hours=24)
#     results = rag.search(query="сбои питания и перезагрузка")
#
# File: adaptive_rag.py
# Project: ai-windows-admin
# Package: apps.windows.log_intelligence.src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 16:25:00
# =============================================================================

from __future__ import annotations
"""Высокопроизводительный In-Memory (RAM) движок семантического поиска и RAG по системным журналам."""

import collections
import concurrent.futures
import datetime
import math
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from logger import logger
from .models import DataProfileReport, IngestionDecision, IngestionStrategy, LogEntry
from apps.windows.sdk.win32_ffi.wevtapi import WevtAPI


# Словарь семантических синонимов и концепций для русско-английского поиска в системных журналах
SEMANTIC_SYNONYMS: Dict[str, List[str]] = {
    'сеть': ['network', 'nic', 'ethernet', 'wifi', 'wlan', 'disconnect', 'link', 'down', 'tcp', 'ip', 'dns', 'dhcp', 'realtek', 'intel', 'adapter', 'адаптер', 'подключение', 'интернет'],
    'network': ['сеть', 'адаптер', 'подключение', 'ethernet', 'wifi', 'wlan', 'disconnect', 'link', 'down', 'realtek', 'dns', 'dhcp', 'ip'],
    'отвал': ['disconnect', 'down', 'fail', 'failure', 'drop', 'offline', 'link', 'отключение', 'сбой', 'потеря'],
    'сбой': ['error', 'critical', 'crash', 'fault', 'fail', 'failure', 'exception', 'bugcheck', 'bsod', 'ошибка', 'инцидент', 'авария', 'проблема'],
    'ошибка': ['error', 'critical', 'fail', 'failure', 'fault', 'exception', 'сбой', 'авария', 'неудача', 'предупреждение'],
    'error': ['ошибка', 'сбой', 'critical', 'fail', 'failure', 'fault', 'exception', 'краш', 'авария'],
    'critical': ['критический', 'сбой', 'error', 'fatal', 'аварийный', 'падение', 'bsod'],
    'питание': ['power', 'kernel-power', 'reboot', 'restart', 'shutdown', 'sleep', 'hibernate', 'acpi', 'батарея', 'выключение', 'перезагрузка'],
    'power': ['питание', 'kernel-power', 'reboot', 'restart', 'shutdown', 'sleep', 'hibernate', 'acpi', 'перезагрузка', 'выключение'],
    'перезагрузка': ['reboot', 'restart', 'kernel-power', '1074', '41', '6008', 'shutdown', 'питание', 'выключение'],
    'reboot': ['перезагрузка', 'restart', 'kernel-power', '1074', '41', '6008', 'shutdown'],
    'выключение': ['shutdown', 'poweroff', '1074', '6006', 'перезагрузка', 'питание'],
    'диск': ['disk', 'drive', 'storage', 'ntfs', 'smart', 'volume', 'io', 'sata', 'nvme', 'накопитель', 'том', 'память'],
    'disk': ['диск', 'drive', 'storage', 'ntfs', 'volume', 'накопитель', 'том', 'сектор', 'smart'],
    'служба': ['service', 'scm', 'bits', 'daemon', 'сервис', 'диспетчер', '7036', '7040', 'остановка', 'запуск'],
    'service': ['служба', 'сервис', 'scm', 'bits', 'daemon', '7036', '7040', 'start', 'stop'],
    'доступ': ['permission', 'dcom', 'security', 'denied', 'audit', 'logon', 'uac', '10016', 'права', 'безопасность', 'активация'],
    'permission': ['доступ', 'права', 'dcom', '10016', 'denied', 'security', 'активация', 'разрешение'],
    'dcom': ['distributedcom', '10016', 'permission', 'доступ', 'активация', 'права', 'appidentity'],
    'обновление': ['update', 'windowsupdate', 'cbs', 'dism', 'installer', 'kb', 'патч', 'установка'],
    'update': ['обновление', 'windowsupdate', 'cbs', 'dism', 'installer', 'kb', 'патч'],
    'defender': ['защитник', 'антивирус', 'угроза', 'antivirus', 'malware', 'threat', 'scan', 'сканирование', 'безопасность'],
    'защитник': ['defender', 'антивирус', 'antivirus', 'угроза', 'malware', 'безопасность'],
    'bsod': ['bugcheck', 'синий экран', '1001', '41', 'краш', 'падение', 'дамп', 'minidump', 'crash'],
    'драйвер': ['driver', 'pnp', 'kernel-pnp', 'устройство', 'hardware', 'оборудование', 'device', 'usb', 'pci'],
    'driver': ['драйвер', 'pnp', 'device', 'устройство', 'hardware', 'оборудование'],
    'powershell': ['powershell', 'скрипт', 'script', 'команда', 'командлет', 'cmdlet', 'automation'],
    'память': ['memory', 'ram', 'exhaustion', 'leak', 'озу', 'утечка', 'переполнение'],
    'memory': ['память', 'ram', 'exhaustion', 'leak', 'озу', 'утечка'],
}


@dataclass
class RAMLogChunk:
    """Структурированный документ журнала событий в оперативной памяти (RAM)."""
    id: str
    channel: str
    provider: str
    event_id: int
    level: str
    timestamp: str
    message: str
    title: str = ''
    computer: str = ''
    process_id: int = 0
    record_id: int = 0
    event_data: Dict[str, Any] = field(default_factory=dict)
    raw_data: str = ''
    search_text: str = ''
    token_count: int = 0


def get_default_storage_dir() -> Path:
    """Сохранена сигнатура функции для совместимости."""
    return Path('.').resolve()


class AdaptiveLogRAG:
    """Высокоскоростной адаптивный RAG-движок, работающий исключительно в оперативной памяти (RAM).

    Обеспечивает:
    1. Параллельный сбор записей за последние 24 часа со всех системных каналов Windows.
    2. Индексирование документов в оперативной памяти (BM25 + TF-IDF + инвертированный индекс).
    3. Семантическое расширение поисковых терминов (русский/английский, синонимы, концепции).
    4. Ранжирование по релевантности, учету серьезности инцидентов и свежести событий.
    5. Полное отсутствие внешних баз данных и дискового ввода-вывода при поиске.
    """

    def __init__(self, storage_dir: Optional[Any] = None, max_chunks: int = 15000) -> None:
        """Инициализировать In-Memory RAG хранилище.

        Args:
            storage_dir: Необязательный параметр совместимости (диск не используется).
            max_chunks: Максимальное количество документов в оперативной памяти.
        """
        self.storage_dir = Path(storage_dir).resolve() if storage_dir else get_default_storage_dir()
        self.max_chunks = max_chunks

        self._lock = threading.RLock()
        self._wevtapi = WevtAPI()

        # Основные структуры оперативной памяти (In-Memory RAM structures)
        self.chunks: List[RAMLogChunk] = []
        self._doc_map: Dict[str, RAMLogChunk] = {}
        self._inverted_index: Dict[str, Set[int]] = collections.defaultdict(set)
        self._doc_lengths: List[int] = []
        self._avg_doc_len: float = 1.0
        self._doc_freq: Dict[str, int] = collections.defaultdict(int)

        # Метаданные и аналитическая статистика текущего индекса в RAM
        self._last_built_at: Optional[str] = None
        self._indexed_channels: Set[str] = set()
        self._stats: Dict[str, Any] = {
            'total_events': 0,
            'critical_count': 0,
            'error_count': 0,
            'warning_count': 0,
            'info_count': 0,
            'channels_scanned': 0,
            'build_duration_ms': 0,
        }

    def clear(self) -> None:
        """Полная очистка In-Memory структур в оперативной памяти."""
        with self._lock:
            self.chunks.clear()
            self._doc_map.clear()
            self._inverted_index.clear()
            self._doc_lengths.clear()
            self._avg_doc_len = 1.0
            self._doc_freq.clear()
            self._indexed_channels.clear()
            self._stats = {
                'total_events': 0,
                'critical_count': 0,
                'error_count': 0,
                'warning_count': 0,
                'info_count': 0,
                'channels_scanned': 0,
                'build_duration_ms': 0,
            }

    @staticmethod
    def _normalize_token(word: str) -> str:
        """Нормализация токена (нижний регистр, очистка)."""
        w = word.lower().strip('.,;:!?"\'()[]{}<>-/*+=')
        return w

    def _tokenize(self, text: str) -> List[str]:
        """Быстрая токенизация текста на слова, идентификаторы и hex-коды."""
        if not text:
            return []
        tokens = re.findall(r'0x[0-9a-fA-F]+|[a-zA-Zа-яА-ЯёЁ0-9_\-]+', text)
        result: List[str] = []
        for t in tokens:
            norm = self._normalize_token(t)
            if len(norm) > 1 or norm.isdigit():
                result.append(norm)
        return result

    def _expand_query_tokens(self, tokens: List[str]) -> List[Tuple[str, float]]:
        """Семантическое расширение токенов поискового запроса с весовыми коэффициентами."""
        expanded: Dict[str, float] = {}

        for tok in tokens:
            # Исходный токен получает максимальный вес
            expanded[tok] = max(expanded.get(tok, 0.0), 1.0)

            # 1. Поиск синонимов по прямому совпадению
            if tok in SEMANTIC_SYNONYMS:
                for syn in SEMANTIC_SYNONYMS[tok]:
                    expanded[syn] = max(expanded.get(syn, 0.0), 0.85)

            # 2. Поиск по корням (от 3 символов) для русской и английской морфологии
            tok_stem = tok[:3] if len(tok) >= 3 else tok
            for key, syn_list in SEMANTIC_SYNONYMS.items():
                key_stem = key[:3] if len(key) >= 3 else key
                if tok_stem == key_stem or tok.startswith(key_stem) or key.startswith(tok_stem):
                    expanded[key] = max(expanded.get(key, 0.0), 0.8)
                    for syn in syn_list:
                        expanded[syn] = max(expanded.get(syn, 0.0), 0.7)

        return list(expanded.items())

    def index_events(self, events: List[Dict[str, Any] | LogEntry], channel: str = '') -> int:
        """Индексирование переданного списка событий в RAM.

        Args:
            events: Список словарей событий или объектов LogEntry.
            channel: Имя канала (если общее).

        Returns:
            int: Количество проиндексированных документов.
        """
        raw_chunks: List[RAMLogChunk] = []
        for ev in events:
            if isinstance(ev, LogEntry):
                c_name = ev.channel or channel or 'System'
                prov = ev.provider or ev.source or 'System'
                eid = int(ev.event_id or 0)
                lvl = ev.level or 'Information'
                ts = ev.timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                msg = ev.message or ''
                chunk_id = f"{c_name}_{prov}_{eid}_{ts}_{len(raw_chunks)}"
                search_text = f"Channel: {c_name} | Provider: {prov} | EventID: {eid} | Level: {lvl} | {msg}"
                raw_chunks.append(RAMLogChunk(
                    id=chunk_id,
                    channel=c_name,
                    provider=prov,
                    event_id=eid,
                    level=lvl,
                    timestamp=ts,
                    message=msg,
                    title=f"[{lvl}] {prov} (ID {eid})",
                    search_text=search_text,
                ))
            elif isinstance(ev, dict):
                c_name = ev.get('channel') or channel or 'System'
                prov = ev.get('provider') or ev.get('source') or 'System'
                eid = int(ev.get('event_id', 0) or 0)
                lvl = ev.get('level') or 'Information'
                ts = ev.get('timestamp') or ev.get('time_created') or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                msg = ev.get('message') or ev.get('formatted_message') or ev.get('raw_data') or ''
                rec_id = int(ev.get('record_id', 0) or 0)
                pid = int(ev.get('process_id', 0) or 0)
                comp = ev.get('computer', '')
                chunk_id = f"{c_name}_{eid}_{rec_id}_{ts}_{len(raw_chunks)}"
                search_text = f"Channel: {c_name} | Provider: {prov} | EventID: {eid} | Level: {lvl} | Computer: {comp} | PID: {pid} | {msg}"
                raw_chunks.append(RAMLogChunk(
                    id=chunk_id,
                    channel=c_name,
                    provider=prov,
                    event_id=eid,
                    level=lvl,
                    timestamp=ts,
                    message=msg,
                    title=f"[{lvl}] {prov} (ID {eid})",
                    computer=comp,
                    process_id=pid,
                    record_id=rec_id,
                    event_data=ev.get('event_data', {}),
                    raw_data=ev.get('raw_data', ''),
                    search_text=search_text,
                ))

        with self._lock:
            for ch in raw_chunks:
                self.chunks.append(ch)
                self._doc_map[ch.id] = ch
                self._indexed_channels.add(ch.channel)

            # Ограничение размера хранилища в RAM
            if len(self.chunks) > self.max_chunks:
                self.chunks = self.chunks[-self.max_chunks:]

            self._rebuild_ram_index()
            return len(raw_chunks)

    def _rebuild_ram_index(self) -> None:
        """Перестроение инвертированного индекса и статистик BM25 в оперативной памяти."""
        self._inverted_index.clear()
        self._doc_lengths.clear()
        self._doc_freq.clear()

        total_length = 0
        crit_count = 0
        err_count = 0
        warn_count = 0
        info_count = 0

        for doc_idx, chunk in enumerate(self.chunks):
            tokens = self._tokenize(chunk.search_text)
            chunk.token_count = len(tokens)
            self._doc_lengths.append(len(tokens))
            total_length += len(tokens)

            lvl_low = chunk.level.lower()
            if 'crit' in lvl_low:
                crit_count += 1
            elif 'err' in lvl_low:
                err_count += 1
            elif 'warn' in lvl_low:
                warn_count += 1
            else:
                info_count += 1

            unique_tokens = set(tokens)
            for ut in unique_tokens:
                self._inverted_index[ut].add(doc_idx)
                self._doc_freq[ut] += 1

        doc_count = len(self.chunks)
        self._avg_doc_len = (total_length / doc_count) if doc_count > 0 else 1.0

        self._stats['total_events'] = doc_count
        self._stats['critical_count'] = crit_count
        self._stats['error_count'] = err_count
        self._stats['warning_count'] = warn_count
        self._stats['info_count'] = info_count
        self._stats['channels_scanned'] = len(self._indexed_channels)

    def index_all_system_logs(
        self,
        hours: int = 24,
        limit_per_channel: int = 150,
        all_channels: bool = True,
        target_channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Сбор записей за последние 24 часа со всех системных каналов Windows и построение RAM RAG индекса.

        Args:
            hours: Диапазон выборки в часах (по умолчанию 24 часа = последние сутки).
            limit_per_channel: Максимум событий с одного канала.
            all_channels: Сканировать абсолютно все активные каналы Windows.
            target_channel: Опциональный конкретный канал для индексации.

        Returns:
            Dict[str, Any]: Итоговый аналитический отчет о построенном RAM индексе.
        """
        start_time = time.time()
        logger.info(f"[AdaptiveLogRAG] Запуск сбора событий за последние {hours}ч со всех каналов Windows...")

        # 1. Получение списка каналов для опроса
        channels_to_scan: List[str] = []
        if target_channel and not all_channels and target_channel.lower() != 'all':
            clean_ch = target_channel.replace('evt:', '').strip()
            channels_to_scan = [clean_ch]
        else:
            try:
                meta_channels = self._wevtapi.enumerate_channels()
                # Отбираем каналы с ненулевым числом записей + стандартные системные каналы
                essential = {'system', 'application', 'security', 'setup', 'microsoft-windows-powershell/operational',
                             'microsoft-windows-kernel-power/operational', 'microsoft-windows-kernel-pnp/configuration',
                             'microsoft-windows-windowsupdateclient/operational', 'microsoft-windows-windows defender/operational',
                             'microsoft-windows-taskscheduler/operational', 'microsoft-windows-hyper-v-compute-operational',
                             'microsoft-windows-sysmon/operational'}

                for c in meta_channels:
                    cname = c.channel_name.strip()
                    if not cname:
                        continue
                    if c.record_count > 0 or cname.lower() in essential:
                        channels_to_scan.append(cname)
            except Exception as e:
                logger.error(f"[AdaptiveLogRAG] Ошибка перечисления каналов: {e}")
                channels_to_scan = ['System', 'Application', 'Security', 'Setup',
                                    'Microsoft-Windows-Kernel-Power/Operational',
                                    'Microsoft-Windows-WindowsUpdateClient/Operational']

        # 2. Параллельный сбор событий за последние 24 часа
        collected_events: List[Dict[str, Any]] = []
        scanned_count = 0

        def _fetch_channel(ch_name: str) -> List[Dict[str, Any]]:
            try:
                return self._wevtapi.read_events(
                    channel=ch_name,
                    limit=limit_per_channel,
                    hours=hours,
                    format_message=True,
                )
            except Exception as ex:
                logger.debug(f"[AdaptiveLogRAG] Ошибка чтения канала {ch_name}: {ex}")
                return []

        # Используем пул потоков для параллельного чтения wevtapi
        max_workers = min(16, max(4, len(channels_to_scan)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_channel = {executor.submit(_fetch_channel, ch): ch for ch in channels_to_scan}
            for future in concurrent.futures.as_completed(future_to_channel):
                ch_name = future_to_channel[future]
                scanned_count += 1
                try:
                    ev_list = future.result()
                    if ev_list:
                        collected_events.extend(ev_list)
                except Exception as ex:
                    logger.debug(f"[AdaptiveLogRAG] Поток чтения канала {ch_name} завершился с ошибкой: {ex}")

        # 3. Полная переиндексация в оперативной памяти (In-Memory)
        with self._lock:
            self.clear()
            self.index_events(collected_events)
            duration_ms = int((time.time() - start_time) * 1000)
            self._last_built_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._stats['build_duration_ms'] = duration_ms
            self._stats['channels_scanned'] = scanned_count
            self._stats['hours'] = hours
            self._stats['period_label'] = '24 часа (сутки)' if hours == 24 else ('7 дней (неделя)' if hours == 168 else ('30 дней (месяц)' if hours == 720 else ('Все время' if hours == 0 else f'{hours}ч')))

        logger.info(
            f"[AdaptiveLogRAG] RAM-индексация завершена за {duration_ms}мс: "
            f"{len(collected_events)} событий из {scanned_count} каналов (период: {self._stats['period_label']})."
        )

        return {
            'status': 'ok',
            'storage_mode': 'RAM_IN_MEMORY',
            'indexed_events': len(self.chunks),
            'scanned_channels': scanned_count,
            'channels_with_events': len(self._indexed_channels),
            'channels_list': sorted(list(self._indexed_channels)),
            'critical_count': self._stats['critical_count'],
            'error_count': self._stats['error_count'],
            'warning_count': self._stats['warning_count'],
            'info_count': self._stats['info_count'],
            'hours': hours,
            'period_label': self._stats['period_label'],
            'build_duration_ms': duration_ms,
            'generated_at': self._last_built_at,
        }

    @staticmethod
    def extract_template(message: str) -> str:
        """Извлечь обобщенный шаблон из сообщения путем маскирования динамических сущностей."""
        if not message:
            return ''
        text = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '<GUID>', message)
        text = re.sub(r'0x[0-9a-fA-F]+', '<HEX>', text)
        text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', text)
        text = re.sub(r'[a-zA-Z]:\\[^\s,;]+', '<PATH>', text)
        text = re.sub(r'\b\d+\b', '<NUM>', text)
        return re.sub(r'\s+', ' ', text).strip()

    def search(
        self,
        query: str,
        top_k: int = 15,
        channel: str = '',
        level: str = '',
        min_score: float = 0.001,
        aggregate: bool = True,
    ) -> List[Dict[str, Any]]:
        """Высокоскоростной семантический и гибридный поиск по RAM RAG индексу с агрегацией повторов.

        Args:
            query: Текстовый поисковый запрос пользователя.
            top_k: Максимальное количество возвращаемых записей/кластеров.
            channel: Фильтр по каналу (пустая строка = все каналы).
            level: Фильтр по уровню важности.
            min_score: Минимальный порог релевантности.
            aggregate: Агрегировать и группировать однотипные повторяющиеся ошибки.

        Returns:
            List[Dict[str, Any]]: Список найденных релевантных событий или агрегированных кластеров с подсветкой и метаданными.
        """
        query_str = (query or '').strip()
        if not query_str:
            return []

        # Автоматическая ленивая сборка индекса, если он пуст
        with self._lock:
            if not self.chunks:
                logger.info("[AdaptiveLogRAG] RAM индекс пуст, запуск автоматической сборки за 24 часа...")
                self.index_all_system_logs(hours=24)

        raw_query_tokens = self._tokenize(query_str)
        if not raw_query_tokens:
            return []

        expanded_tokens_with_weights = self._expand_query_tokens(raw_query_tokens)
        query_terms_set = {t for t, _ in expanded_tokens_with_weights}

        # Выделение явных числовых Event ID и кодов ошибок из запроса
        explicit_eids: Set[int] = set()
        for tok in raw_query_tokens:
            if tok.isdigit() and len(tok) in (1, 2, 3, 4, 5):
                explicit_eids.add(int(tok))

        is_error_intent = any(
            t in ('ошибка', 'сбой', 'error', 'critical', 'fail', 'crash', 'краш', 'авария', 'проблема', 'bsod', '10016', '41')
            for t in query_terms_set
        )

        with self._lock:
            doc_count = len(self.chunks)
            if doc_count == 0:
                return []

            # Кандидаты по инвертированному индексу
            candidate_doc_indices: Set[int] = set()
            for tok, _ in expanded_tokens_with_weights:
                if tok in self._inverted_index:
                    candidate_doc_indices.update(self._inverted_index[tok])

            # Если по токенам ничего не нашлось, проверяем подстрочный поиск
            if not candidate_doc_indices:
                q_low = query_str.lower()
                for idx, ch in enumerate(self.chunks):
                    if q_low in ch.search_text.lower():
                        candidate_doc_indices.add(idx)

            clean_channel_filter = channel.replace('evt:', '').strip().lower() if channel else ''
            clean_level_filter = level.strip().lower() if level else ''

            scored_docs: List[Tuple[float, RAMLogChunk, List[str]]] = []

            # Параметры алгоритма BM25
            k1 = 1.2
            b = 0.75
            avgdl = self._avg_doc_len

            for doc_idx in candidate_doc_indices:
                chunk = self.chunks[doc_idx]

                # Фильтрация по каналу
                if clean_channel_filter and clean_channel_filter != 'all':
                    if chunk.channel.lower() != clean_channel_filter:
                        continue

                # Фильтрация по уровню
                if clean_level_filter:
                    if clean_level_filter not in chunk.level.lower():
                        continue

                doc_len = self._doc_lengths[doc_idx] if doc_idx < len(self._doc_lengths) else 10
                doc_tokens = self._tokenize(chunk.search_text)
                doc_token_counts = collections.Counter(doc_tokens)

                bm25_score = 0.0
                matched_highlights: List[str] = []

                for tok, weight in expanded_tokens_with_weights:
                    tf = doc_token_counts.get(tok, 0)
                    if tf > 0:
                        df = self._doc_freq.get(tok, 1)
                        idf = math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5))
                        tf_component = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avgdl)))
                        term_score = idf * tf_component * weight
                        bm25_score += term_score
                        matched_highlights.append(tok)

                # Дополнительный бустинг за точные совпадения
                bonus = 1.0

                # Точное совпадение Event ID
                if explicit_eids and chunk.event_id in explicit_eids:
                    bonus += 3.0

                # Приоритет критических ошибок при запросе о проблемах
                if is_error_intent:
                    lvl_l = chunk.level.lower()
                    if 'crit' in lvl_l:
                        bonus += 1.8
                    elif 'err' in lvl_l:
                        bonus += 1.4
                    elif 'warn' in lvl_l:
                        bonus += 1.1

                # Точное вхождение исходного запроса
                if query_str.lower() in chunk.search_text.lower():
                    bonus += 2.0

                final_score = bm25_score * bonus
                if final_score >= min_score:
                    scored_docs.append((final_score, chunk, matched_highlights))

            # Сортировка по релевантности (убывание)
            scored_docs.sort(key=lambda x: x[0], reverse=True)

            if not scored_docs:
                return []

            max_raw_score = scored_docs[0][0] if scored_docs else 1.0

            if not aggregate:
                results: List[Dict[str, Any]] = []
                for score, chunk, highlights in scored_docs[:top_k]:
                    norm_score = round(min(1.0, score / max(max_raw_score, 1.0)), 3)
                    results.append({
                        'id': chunk.id,
                        'channel': chunk.channel,
                        'provider': chunk.provider,
                        'event_id': chunk.event_id,
                        'level': chunk.level,
                        'timestamp': chunk.timestamp,
                        'message': chunk.message,
                        'title': chunk.title,
                        'computer': chunk.computer,
                        'process_id': chunk.process_id,
                        'record_id': chunk.record_id,
                        'event_data': chunk.event_data,
                        'relevance_score': norm_score,
                        'score': norm_score,
                        'count': 1,
                        'is_aggregated': False,
                        'text': f"[{chunk.level}] {chunk.timestamp} | {chunk.channel} | {chunk.provider} (ID {chunk.event_id}): {chunk.message}",
                        'content': chunk.message,
                        'matched_terms': list(set(highlights)),
                        'metadata': {
                            'channel': chunk.channel,
                            'provider': chunk.provider,
                            'event_id': chunk.event_id,
                            'level': chunk.level,
                            'timestamp': chunk.timestamp,
                            'score': norm_score,
                        },
                    })
                return results

            # Интеллектуальная кластеризация и агрегация однотипных повторяющихся записей
            cluster_map: Dict[str, Dict[str, Any]] = collections.OrderedDict()

            for score, chunk, highlights in scored_docs:
                tmpl = self.extract_template(chunk.message)
                sig_key = f"{chunk.channel}::{chunk.provider}::{chunk.event_id}::{chunk.level}::{tmpl}"

                if sig_key not in cluster_map:
                    cluster_map[sig_key] = {
                        'representative_score': score,
                        'representative_chunk': chunk,
                        'highlights': set(highlights),
                        'template': tmpl,
                        'occurrences': [],
                        'first_seen': chunk.timestamp,
                        'last_seen': chunk.timestamp,
                    }

                c_entry = cluster_map[sig_key]
                c_entry['highlights'].update(highlights)
                if score > c_entry['representative_score']:
                    c_entry['representative_score'] = score
                    c_entry['representative_chunk'] = chunk

                ts = chunk.timestamp or ''
                if ts:
                    if not c_entry['first_seen'] or ts < c_entry['first_seen']:
                        c_entry['first_seen'] = ts
                    if not c_entry['last_seen'] or ts > c_entry['last_seen']:
                        c_entry['last_seen'] = ts

                c_entry['occurrences'].append({
                    'id': chunk.id,
                    'timestamp': chunk.timestamp,
                    'record_id': chunk.record_id,
                    'process_id': chunk.process_id,
                    'computer': chunk.computer,
                    'event_id': chunk.event_id,
                    'level': chunk.level,
                    'provider': chunk.provider,
                    'channel': chunk.channel,
                    'message': chunk.message,
                })

            sorted_clusters = sorted(
                cluster_map.values(),
                key=lambda x: (x['representative_score'], len(x['occurrences'])),
                reverse=True,
            )

            results: List[Dict[str, Any]] = []
            for cluster in sorted_clusters[:top_k]:
                chunk = cluster['representative_chunk']
                count = len(cluster['occurrences'])
                norm_score = round(min(1.0, cluster['representative_score'] / max(max_raw_score, 1.0)), 3)

                results.append({
                    'id': chunk.id,
                    'channel': chunk.channel,
                    'provider': chunk.provider,
                    'event_id': chunk.event_id,
                    'level': chunk.level,
                    'timestamp': cluster['last_seen'] or chunk.timestamp,
                    'first_seen': cluster['first_seen'] or chunk.timestamp,
                    'last_seen': cluster['last_seen'] or chunk.timestamp,
                    'message': chunk.message,
                    'template': cluster['template'],
                    'title': chunk.title,
                    'computer': chunk.computer,
                    'process_id': chunk.process_id,
                    'record_id': chunk.record_id,
                    'event_data': chunk.event_data,
                    'relevance_score': norm_score,
                    'score': norm_score,
                    'count': count,
                    'is_aggregated': count > 1,
                    'occurrences': cluster['occurrences'][:50],
                    'text': f"[{chunk.level}] {cluster['last_seen']} (x{count}) | {chunk.channel} | {chunk.provider} (ID {chunk.event_id}): {chunk.message}",
                    'content': chunk.message,
                    'matched_terms': list(cluster['highlights']),
                    'metadata': {
                        'channel': chunk.channel,
                        'provider': chunk.provider,
                        'event_id': chunk.event_id,
                        'level': chunk.level,
                        'timestamp': cluster['last_seen'] or chunk.timestamp,
                        'first_seen': cluster['first_seen'],
                        'last_seen': cluster['last_seen'],
                        'count': count,
                        'score': norm_score,
                    },
                })

            return results

    def ingest(self, profile: DataProfileReport, decision: IngestionDecision) -> int:
        """Адаптивное сохранение аналитического профиля в RAM для совместимости с LogIntelligencePipeline."""
        now_str = profile.generated_at or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        snap_id = f"snapshot_{profile.channel}_{now_str[:13]}"
        snap_text = (
            f"Аналитический снимок здоровья канала {profile.channel}.\n"
            f"Метка времени: {now_str}\n"
            f"Индекс здоровья (Health Score): {profile.health_score} / 100\n"
            f"Всего событий: {profile.total_events}, Уникальных шаблонов: {profile.unique_templates_count}\n"
            f"Ошибок: {profile.error_count + profile.critical_count}, Предупреждений: {profile.warning_count}\n"
            f"Выбранная стратегия: {decision.strategy.value}\n"
            f"Обоснование: {decision.rationale}"
        )

        chunk = RAMLogChunk(
            id=snap_id,
            channel=profile.channel,
            provider='LogIntelligence',
            event_id=0,
            level='Information' if profile.health_score >= 80 else 'Warning',
            timestamp=now_str,
            message=snap_text,
            title=f"Снимок здоровья {profile.channel} ({profile.health_score}%)",
            search_text=f"Health snapshot {profile.channel} score {profile.health_score} {snap_text}",
        )

        with self._lock:
            self.chunks.append(chunk)
            self._doc_map[chunk.id] = chunk
            self._rebuild_ram_index()

        return 1

    def get_status(self) -> Dict[str, Any]:
        """Получить статус текущего In-Memory RAG индекса в оперативной памяти."""
        with self._lock:
            return {
                'storage_mode': 'RAM_IN_MEMORY',
                'is_indexed': len(self.chunks) > 0,
                'total_events': len(self.chunks),
                'channels_count': len(self._indexed_channels),
                'channels_list': sorted(list(self._indexed_channels)),
                'last_built_at': self._last_built_at,
                'stats': dict(self._stats),
            }
