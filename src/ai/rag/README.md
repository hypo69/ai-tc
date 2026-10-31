# Унифицированный стек знаний и RAG (Unified Knowledge & RAG Stack)

Пакет `src/ai/rag` объединяет передовые методы поиска и прогрессивного накопления знаний в единую архитектуру платформы **AI Windows Admin**.

---

## 🏛 Архитектурные компоненты

```
                             UnifiedKnowledgeHub
                                      │
    ┌────────────────┬────────────────┼────────────────┬────────────────┐
    ▼                ▼                ▼                ▼                ▼
 WikiLLM         Text RAG       Codebase RAG      Pixel RAG         Log RAG
(wikillm)       (text_rag)     (codebase_rag)     (pixel_rag)      (log_rag)
    │                │                │                │                │
Exact L1 (O(1))  Эмбеддинги       AST-парсер      Визуальные хэши   Адаптивные чанки
Fingerprint L2   FAISS поиск     Python + MD      OCR текст         Кластеризация
Semantic L3      Документы       Диагностика      UI-скриншоты      Связка с Event ID
LLM Resolver L4                  кода и логов     Диаграммы ОС      Анализ инцидентов
```

---

## 🔍 Согласованный конвейер разрешения (Harmonized Pipeline)

1. **L1 — Exact Match ($O(1)$ в SQLite)**: Мгновенное получение детерминированных фактов, кодов ошибок Win32/NTSTATUS, системных команд и AST-символов кода без расхода токенов.
2. **L2 — Fingerprint Match**: Сопоставление с динамическими шаблонами журналов и сообщений об ошибках со стёртыми переменными (GUID, PID, адреса).
3. **L3 — Hybrid Semantic & AST Search**:
   - **WikiLLM FTS5**: Полнотекстовый поиск по морфологии симптомов и проверенным рекомендациям.
   - **Codebase RAG (`CodebaseRAG`)**: Индексация AST-деревьев Python (классы, функции, методы, сигнатуры, docstrings, граф вызовов) и секций Markdown-документации; извлечение стек-трейсов, строк и исключений из логов для формирования структурированного заключения `CodeDiagnosticConclusion`.
   - **Text RAG**: Поиск по семантическим векторным эмбеддингам Gemini и FAISS по документации и исходному коду.
   - **Log RAG**: Поиск по контекстным чанкам системных журналов Windows и профилированию инцидентов.
   - **Pixel RAG**: Сопоставление графических скриншотов окон ошибок и состояний UI.
4. **L4 — LLM Structured Synthesis**: Вызов LLM (`UnifiedChatModel` / Gemini) с получением строго структурированного JSON, Pydantic-валидацией и автоматическим занесением факта в базу знаний.

---

## 🌐 Интеграция с REST API и WebGUI

1. **Codebase Diagnostic & AST RAG (`/api/rag/codebase/...`)**:
   - `POST /api/rag/codebase/build` — построение AST + Markdown индекса кодовой базы.
   - `POST /api/rag/codebase/diagnose` — получение структурированного инженерного заключения (`CodeDiagnosticConclusion`) по вопросу (`question`), списку логов (`logs`) или сообщению об ошибке/трейсбеку (`error_message`).
   - `POST /api/rag/codebase/search` — гибридный семантический и сигнальный поиск по чанкам кода.
   - `POST /api/rag/codebase/symbols` — поиск по таблице AST-символов.
   - `GET /api/rag/codebase/indexes` — список построенных индексов кодовой базы.
2. **System Control Tab (`http://localhost:8001/tc#tab-system-control`)**:
   - Панель **«Semantic RAG Search in Logs»** использует `LogRAG` и `AdaptiveLogRAG` через эндпоинты `/api/v1/system_logs/rag/query` и `/api/v1/system_logs/rag/build`.
3. **RAG Tab (`tab_rag`)**:
   - Управление глобальными документами, AST-индексами кодовой базы и коллекциями Multi-RAG.
4. **Pixel RAG Tab (`pixelrag_tab`)**:
   - Индексация и визуальный поиск по скриншотам и окнам ошибок через `/api/rag/pixel/...`.
5. **AI Diagnostics Modal Dialog (`ai_modal_dialog`)**:
   - Мгновенное подтверждение и фиксация проверенных знаний в WikiLLM через `/api/windows/wikillm/approve`.

---

## 🚀 Примеры использования

```python
from src.ai.rag import CodebaseRAG, UnifiedKnowledgeHub

# 1. Построение AST-индекса кодовой базы и получение заключения по логам и ошибке
code_rag = CodebaseRAG()
code_rag.build_index(project_root=".", index_name="codebase", include_dirs=["src/ai/rag"])

conclusion = await code_rag.diagnose(
    question="Почему возникает ошибка при вызове search?",
    logs=["[ERROR] text_rag.py:255 - dimension mismatch in query vector"],
    error_message='File "src/ai/rag/text_rag.py", line 255, in search\nValueError: Несоответствие размерности вектора',
)
print(conclusion.summary)
print(conclusion.root_cause)
for loc in conclusion.affected_locations:
    print(f"{loc.file_path}:{loc.start_line}-{loc.end_line} ({loc.symbol_name})")

# 2. Сквозное разрешение через UnifiedKnowledgeHub
hub = UnifiedKnowledgeHub()
result = await hub.resolve_query("0x80070490")
```
