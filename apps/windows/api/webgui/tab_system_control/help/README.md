# Подсистема контекстной справки модуля System Control

Данная директория содержит атомарные HTML-фрагменты и композитный шаблон интерактивной справки для раздела **«Центр контроля сбоев и журналов»** (`#tab-system-control` / `tab_system_control`).

## Архитектура: Атомарные блоки и Композиция

Подсистема реализована по иерархическому принципу:
1. **Атомарные блоки (`help/blocks/`)**:
   - `block_summary_dashboard.html`: Сводная панель критических сбоев ядра, аварий BSOD/BugCheck, отключений питания (Kernel-Power 41) и подозрительной активности.
   - `block_event_logs.html`: Классические журналы Windows Event Log, режимы Live Events, Smart Digest (EDA), RAG-поиск и тепловая карта Heatmap.
   - `block_power_lifecycle.html`: Анализ сессий электропитания, аптайма, переходов в сон (Sleep/Modern Standby) и параметров BugCheck.
   - `block_defender_logs.html`: Аудит событий антивируса Microsoft Defender (детекция угроз, сигнатуры, исключения).
   - `block_forensics.html`: Криминалистическая форензика (реестр UserAssist, таймлайн активности, сенсоры оборудования и эскалация привилегий).
   - `block_throttling.html`: Диагностика аппаратного термального троттлинга PROCHOT, задержек DPC/ISR, ошибок PCIe шины и памяти WHEA.

2. **Композитный уровень (`help/index.html`)**:
   - Объединяет атомарные блоки через `<div data-help-include="/html/tab_system_control/help/blocks/block_*.html"></div>`.
   - Поддерживает быструю навигацию (`[data-help-jump]`) по всем 6 разделам вкладки.

3. **Интеграция с Universal HelpModal**:
   - Вызывается в стандартном модальном окне `80vw × 80vh` через `data-help-url="/html/tab_system_control/help/index.html"`.
   - Поддерживает подсветку конкретного блока через `data-help-focus="block_..."`.

Updated: 2026-10-31 18:22:00
