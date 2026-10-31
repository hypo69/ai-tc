# Подсистема контекстной справки модуля Software Monitor

Данная директория содержит атомарные HTML-фрагменты и композитный шаблон интерактивной справки для раздела **«Установленные программы и Мониторинг ПО»** (`#tab-software-monitor` / `tab_software_monitor`).

## Архитектура: Атомарные блоки и Композиция

Подсистема реализована по иерархическому принципу:
1. **Атомарные блоки (`help/blocks/`)**:
   - `block_inventory.html`: Реестр установленных программ (x64/x86/MSIX), тихая деинсталляция Quiet Uninstall и экспорт инвентаря.
   - `block_packages.html`: Менеджер пакетов ПО (WinGet, MSI Installer API, Microsoft Store AppX и автообновления Ninite).
   - `block_dormant_orphans.html`: Спящие программы (>90 дней без запуска на базе Prefetch) и сироты/остатки деинсталляции.
   - `block_startup.html`: Аудит автозапуска программ (Startup Auditor) в реестре и системных папках с оценкой влияния на загрузку.
   - `block_transparency.html`: ИИ-аудит прозрачности и рисков ПО (проверка Authenticode, цифровых подписей и скрытых угроз).
   - `block_heavy_sockets.html`: Ресурсоемкие программы (нагрузка CPU/RAM/Disk I/O) и открытые сокеты/порты процессов.

2. **Композитный уровень (`help/index.html`)**:
   - Объединяет все 6 блоков через `<div data-help-include="/html/tab_software_monitor/help/blocks/block_*.html"></div>`.
   - Включает панель быстрого перехода (`[data-help-jump]`).

3. **Интеграция с Universal HelpModal**:
   - Открывается в модальном окне `80vw × 80vh` по клику на кнопку в шапке (`data-help-url="/html/tab_software_monitor/help/index.html"`).

Updated: 2026-10-31 18:37:00
