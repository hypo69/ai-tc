# Подсистема контекстной справки модуля Processes Load Inspector

Данная директория содержит атомарные HTML-фрагменты и композитный шаблон интерактивной справки для раздела **«Мониторинг процессов и активности хоста»** (`#tab-processes-load-inspector` / `tab_processes_load_inspector`).

## Архитектура: Атомарные блоки и Композиция

Подсистема реализована по иерархическому принципу:
1. **Атомарные блоки (`help/blocks/`)**:
   - `block_manager.html`: Диспетчер процессов и приложений (Apps, Background, Windows), дерево подпроцессов и PID Recycling Guard.
   - `block_top_stream.html`: Топ процессов хоста (Live Stream) по CPU, RAM, Disk I/O и быстрый переход Drill-Down.
   - `block_network_activity.html`: Сетевая активность программ (сокеты TCP/UDP, прослушиваемые порты, скорость трафика).
   - `block_file_changes.html`: Низкоуровневый трекинг изменений файлов в реальном времени через `ReadDirectoryChangesW`.
   - `block_leak_hunter.html`: Аудит утечек ресурсов (Leak Hunter: лимиты GDI/USER объектов, Handle leaks, Page Faults).
   - `block_deep_dive.html`: Модальное окно Process Intelligence Deep Dive (4 графика Chart.js, иерархия Lineage, SafeOps действия).

2. **Композитный уровень (`help/index.html`)**:
   - Объединяет все 6 блоков через `<div data-help-include="/html/tab_processes_load_inspector/help/blocks/block_*.html"></div>`.
   - Включает панель быстрого перехода (`[data-help-jump]`).

3. **Интеграция с Universal HelpModal**:
   - Открывается в модальном окне `80vw × 80vh` по клику на кнопку в шапке (`data-help-url="/html/tab_processes_load_inspector/help/index.html"`).

Updated: 2026-10-31 18:40:00
