"""
=============================================================================
Process Name: WebGUI Developer Skill - Tab Scaffolding CLI Script
=============================================================================
Description:
  CLI скрипт для автоматической генерации новой вкладки (*_tab) в WebGUI.
  Создает изолированный каталог, генерирует index.html, main.js, README.md
  по эталонному шаблону со стандартами проекта (заголовки, русский язык,
  безопасный поллинг через tab-core.js и интеграция с AIModalDialog).

Usage Examples:
  py .agents/skills/webgui-developer/scripts/scaffold_tab.py my_feature --title "Моя функция" --icon "bi-stars"

File: scaffold_tab.py
Project: ai-windows-admin
Package: .agents/skills/webgui-developer/scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-20 10:55:00
=============================================================================
"""

import argparse
import datetime
import re
import sys
from pathlib import Path


def to_pascal_case(snake_str: str) -> str:
    """Преобразует snake_case строку в PascalCase."""
    return ''.join(word.capitalize() for word in snake_str.split('_'))


def to_kebab_case(snake_str: str) -> str:
    """Преобразует snake_case строку в kebab-case."""
    return snake_str.replace('_', '-')


def main():
    parser = argparse.ArgumentParser(description="Генератор новой вкладки WebGUI AI Windows Admin")
    parser.add_argument("name", help="Имя вкладки в формате snake_case (без суффикса _tab, например: security_audit)")
    parser.add_argument("--title", default=None, help="Отображаемый заголовок на русском языке")
    parser.add_argument("--icon", default="bi-grid", help="CSS класс иконки Bootstrap (например: bi-shield-check, bi-cpu)")
    parser.add_argument("--table-type", default="generic", help="Тип таблицы для AIModalDialog (process, service, software, disk, generic)")
    args = parser.parse_args()

    clean_name = args.name.lower().strip()
    if clean_name.endswith("_tab"):
        clean_name = clean_name[:-4]

    pascal_name = to_pascal_case(clean_name)
    kebab_name = to_kebab_case(clean_name)
    title = args.title or f"Раздел {pascal_name}"
    tab_id = f"tab-{kebab_name}"
    tab_folder_name = f"{clean_name}_tab"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version_tag = datetime.datetime.now().strftime("%Y%m%d_v1")

    # Путь к webgui
    root_dir = Path(__file__).resolve().parents[4]
    webgui_dir = root_dir / "apps" / "windows" / "api" / "webgui"
    target_dir = webgui_dir / tab_folder_name

    if target_dir.exists():
        print(f"[!] Директория вкладки уже существует: {target_dir}")
        sys.exit(1)

    target_dir.mkdir(parents=True, exist_ok=True)

    # Генерация index.html
    html_content = f"""<!--
=============================================================================
Process Name: Windows Web Interface - {pascal_name} Tab View
=============================================================================
Description:
  Интерфейсная разметка вкладки {title}.
  Сгенерировано автоматически генератором WebGUI Developer.

Usage Examples:
  Web Route:
    /html/{tab_folder_name}/index.html?v={version_tag}

File: index.html
Project: ai-windows-admin
Package: windows/api/webgui/{tab_folder_name}
Author: hypo69
Copyright: © 2026 hypo69
Updated: {now_str}
=============================================================================
-->

<div class="container-fluid p-3 d-flex flex-column gap-3 {kebab_name}-tab-wrapper" style="max-width: 1400px; margin: 0 auto;">

  <!-- Заголовок вкладки -->
  <div class="tab-header d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
    <div class="d-flex align-items-center gap-2">
      <span class="tab-header-icon fs-4 text-primary"><i class="bi {args.icon}"></i></span>
      <div>
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <h3 class="tab-header-title panel-header mb-0">{title}</h3>
          <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-0.5 small" id="{clean_name}-counter-badge">0 элементов</span>
        </div>
        <small class="tab-header-subtitle text-secondary">
          Мониторинг, анализ и интерактивное управление компонентами {title}.
        </small>
      </div>
    </div>

    <!-- Панель быстрых действий -->
    <div class="d-flex align-items-center gap-2 flex-wrap">
      <div class="form-check form-switch me-2 mb-0" title="Включение автоматического фонового опроса">
        <input class="form-check-input" type="checkbox" role="switch" id="{clean_name}-live-toggle" checked>
        <label class="form-check-label small" for="{clean_name}-live-toggle">Live-опрос</label>
      </div>

      <button type="button" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2" id="{clean_name}-btn-refresh" title="Обновить данные">
        <i class="bi bi-arrow-clockwise" id="{clean_name}-refresh-spinner"></i>
        <span>Обновить</span>
      </button>
    </div>
  </div>

  <!-- Карточка фильтрации и поиска -->
  <div class="card border-subtle shadow-sm bg-body">
    <div class="card-body p-3">
      <div class="row g-2 align-items-center">
        <div class="col-12 col-md-6">
          <div class="input-group input-group-sm">
            <span class="input-group-text bg-body-tertiary text-muted border-end-0">
              <i class="bi bi-search"></i>
            </span>
            <input type="text" class="form-control form-control-sm border-start-0" id="{clean_name}-search-input" placeholder="Поиск по имени, параметрам..." autocomplete="off">
            <button class="btn btn-outline-secondary" type="button" id="{clean_name}-search-clear">
              <i class="bi bi-x"></i>
            </button>
          </div>
        </div>
        <div class="col-12 col-md-6 d-flex justify-content-md-end align-items-center gap-3 small text-muted">
          <span>Статус: <b class="text-success" id="{clean_name}-status-badge">Активен</b></span>
        </div>
      </div>
    </div>
  </div>

  <!-- Карточка таблицы с интеграцией AIModalDialog -->
  <div class="card border-subtle shadow-sm bg-body">
    <div class="card-header bg-body-tertiary py-2 px-3 d-flex align-items-center justify-content-between">
      <div class="fw-semibold small d-flex align-items-center gap-2">
        <i class="bi bi-table text-primary"></i>
        <span>Список сущностей</span>
      </div>
      <span class="badge bg-secondary-subtle text-secondary small" id="{clean_name}-table-state">Готово</span>
    </div>

    <!-- Индикатор загрузки -->
    <div id="{clean_name}-loading-indicator" class="p-5 text-center d-none">
      <div class="spinner-border text-primary mb-2" role="status"></div>
      <div class="text-muted small">Загрузка данных...</div>
    </div>

    <!-- Состояние отсутствия записей -->
    <div id="{clean_name}-empty-state" class="p-5 text-center d-none">
      <div class="fs-1 text-muted mb-2"><i class="bi bi-inbox"></i></div>
      <h6 class="text-body fw-bold">Данные не найдены</h6>
      <p class="text-muted small mb-0">По текущим фильтрам записи отсутствуют.</p>
    </div>

    <!-- Таблица -->
    <div class="table-responsive" id="{clean_name}-table-container">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light border-bottom">
          <tr class="small text-muted">
            <th scope="col">Имя сущности</th>
            <th scope="col">Статус</th>
            <th scope="col">Параметр</th>
            <th scope="col" class="text-end">Действия</th>
          </tr>
        </thead>
        <tbody id="{clean_name}-table-body" class="small">
          <!-- Генерируется через main.js -->
        </tbody>
      </table>
    </div>

    <div class="card-footer bg-body-tertiary py-2 px-3 d-flex align-items-center justify-content-between small text-muted">
      <span id="{clean_name}-footer-summary">Всего: 0</span>
      <span class="fst-italic">Клик по строке запускает контекстный ИИ-анализ</span>
    </div>
  </div>

</div>
"""
    (target_dir / "index.html").write_text(html_content, encoding="utf-8")

    # Генерация main.js
    js_content = f"""/**
 * =============================================================================
 * Process Name: Windows Web Interface - {pascal_name} Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер жизненного цикла вкладки {title}.
 *   Обеспечивает опрос через tab-core.js и вызов ИИ-модального окна AIModalDialog.
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/{tab_folder_name}
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: {now_str}
 * =============================================================================
 */

let tabItems = [];
let isInitialized = false;
const TAB_ID = '{tab_id}';
const API_ENDPOINT = '/api/v1/{clean_name}';

/**
 * Инициализация вкладки {pascal_name}.
 */
export async function init{pascal_name}Tab() {{
  console.log('[{pascal_name}Tab] Инициализация вкладки...');

  if (!isInitialized) {{
    bindEventListeners();
    isInitialized = true;
  }}

  await loadData();

  if (typeof window.registerTabPoller === 'function') {{
    window.registerTabPoller(TAB_ID, async () => {{
      await loadData(true);
    }}, 4000, {{ immediate: false }});
  }}
}}
window.init{pascal_name}Tab = init{pascal_name}Tab;

/**
 * Очистка ресурсов при переключении вкладки.
 */
export function deactivate{pascal_name}Tab() {{
  console.log('[{pascal_name}Tab] Вкладка деактивирована.');
}}
window.deactivate{pascal_name}Tab = deactivate{pascal_name}Tab;

/**
 * Подключение обработчиков DOM.
 */
function bindEventListeners() {{
  const btnRefresh = document.getElementById('{clean_name}-btn-refresh');
  if (btnRefresh) {{
    btnRefresh.onclick = async () => {{
      const spinner = document.getElementById('{clean_name}-refresh-spinner');
      spinner?.classList.add('spin-animation');
      await loadData();
      spinner?.classList.remove('spin-animation');
    }};
  }}

  const liveToggle = document.getElementById('{clean_name}-live-toggle');
  if (liveToggle) {{
    liveToggle.onchange = () => {{
      if (typeof window.setTabPollerEnabled === 'function') {{
        window.setTabPollerEnabled(`${{TAB_ID}}_default`, liveToggle.checked);
      }}
    }};
  }}

  const searchInput = document.getElementById('{clean_name}-search-input');
  if (searchInput) {{
    searchInput.oninput = () => renderTable();
  }}

  const clearBtn = document.getElementById('{clean_name}-search-clear');
  if (clearBtn && searchInput) {{
    clearBtn.onclick = () => {{
      searchInput.value = '';
      renderTable();
    }};
  }}
}}

/**
 * Загрузка телеметрии из API.
 */
async function loadData(isBackground = false) {{
  const loader = document.getElementById('{clean_name}-loading-indicator');
  const tableCont = document.getElementById('{clean_name}-table-container');

  if (!isBackground && loader && tableCont) {{
    loader.classList.remove('d-none');
    tableCont.classList.add('opacity-50');
  }}

  try {{
    const res = await fetch(API_ENDPOINT);
    if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
    const data = await res.json();
    tabItems = Array.isArray(data.items) ? data.items : [];
  }} catch (err) {{
    console.warn('[{pascal_name}Tab] Использование демонстрационных данных:', err);
    tabItems = [
      {{ id: '1', name: '{title} Элемент #1', status: 'Active', value: 'Норма', icon: '⚡' }},
      {{ id: '2', name: '{title} Элемент #2', status: 'Idle', value: 'Ожидание', icon: '⏱️' }}
    ];
  }} finally {{
    if (!isBackground && loader && tableCont) {{
      loader.classList.add('d-none');
      tableCont.classList.remove('opacity-50');
    }}
    renderTable();
  }}
}}

/**
 * Отрисовка таблицы и навешивание AIModalDialog.
 */
function renderTable() {{
  const tbody = document.getElementById('{clean_name}-table-body');
  const emptyState = document.getElementById('{clean_name}-empty-state');
  const searchInput = document.getElementById('{clean_name}-search-input');
  const badge = document.getElementById('{clean_name}-counter-badge');
  const footerSummary = document.getElementById('{clean_name}-footer-summary');

  if (!tbody) return;

  const query = (searchInput?.value || '').trim().toLowerCase();
  const filtered = tabItems.filter(item => !query || item.name.toLowerCase().includes(query));

  if (badge) badge.textContent = `${{filtered.length}} элементов`;
  if (footerSummary) footerSummary.textContent = `Всего: ${{filtered.length}} из ${{tabItems.length}}`;

  if (filtered.length === 0) {{
    tbody.innerHTML = '';
    emptyState?.classList.remove('d-none');
    return;
  }}

  emptyState?.classList.add('d-none');

  tbody.innerHTML = filtered.map(item => `
    <tr class="interactive-table-row" data-id="${{escapeHtml(item.id)}}" style="cursor: pointer;">
      <td>
        <div class="fw-semibold text-body d-flex align-items-center gap-2">
          <span>${{item.icon || '📄'}}</span>
          <span>${{escapeHtml(item.name)}}</span>
        </div>
      </td>
      <td>
        <span class="badge ${{item.status === 'Active' ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-secondary-subtle text-secondary'}}">
          ${{escapeHtml(item.status)}}
        </span>
      </td>
      <td class="font-monospace">${{escapeHtml(item.value || '—')}}</td>
      <td class="text-end no-modal-trigger">
        <button type="button" class="btn btn-sm btn-outline-primary" data-action="ai-inspect" data-id="${{escapeHtml(item.id)}}" title="ИИ-анализ">
          <i class="bi bi-robot"></i>
        </button>
      </td>
    </tr>
  `).join('');

  tbody.querySelectorAll('.interactive-table-row').forEach(row => {{
    row.addEventListener('click', (e) => {{
      if (e.target.closest('button, a, input, select, .no-modal-trigger')) return;
      const itemId = row.getAttribute('data-id');
      const item = tabItems.find(x => String(x.id) === String(itemId));
      if (item) openItemAiModal(item);
    }});
  }});

  tbody.querySelectorAll('button[data-action="ai-inspect"]').forEach(btn => {{
    btn.onclick = (e) => {{
      e.stopPropagation();
      const itemId = btn.getAttribute('data-id');
      const item = tabItems.find(x => String(x.id) === String(itemId));
      if (item) openItemAiModal(item);
    }};
  }});
}}

/**
 * Вызов универсального диалога ИИ-анализа.
 */
function openItemAiModal(item) {{
  const modal = window.AIModalDialog || window.AITableModal;
  if (!modal) {{
    console.warn('[{pascal_name}Tab] AIModalDialog недоступен.');
    return;
  }}

  modal.show({{
    title: item.name,
    subtitle: `ID: ${{item.id}} | Статус: ${{item.status}}`,
    icon: item.icon || '⚙️',
    tableType: '{args.table_type}',
    badges: [
      {{ text: item.status, class: item.status === 'Active' ? 'badge bg-success' : 'badge bg-secondary' }}
    ],
    metadata: [
      {{ label: 'Идентификатор', value: item.id }},
      {{ label: 'Текущее состояние', value: item.value || 'N/A' }},
      {{ label: 'Метка времени', value: new Date().toLocaleTimeString() }}
    ],
    rawTitle: 'Сырые данные (JSON)',
    rawContent: JSON.stringify(item, null, 2),
    autoRun: false
  }});
}}

function escapeHtml(str) {{
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}}
"""
    (target_dir / "main.js").write_text(js_content, encoding="utf-8")

    # Генерация README.md
    readme_content = f"""# {title} ({pascal_name} Tab)

Модуль веб-интерфейса вкладки `{title}`.

---

## 📁 Структура модуля
- `index.html` — разметка вкладки (без `<script>`).
- `main.js` — контроллер жизненного цикла (`window.init{pascal_name}Tab`).
- `README.md` — данная документация.

---

## 🔌 Регистрация вкладки

### 1. `core/tab-registry.js`:
```javascript
{{
  id: '{clean_name}',
  label: '{title}',
  icon: '{args.icon}',
  tab: '{kebab_name}',
  tabId: '{tab_id}',
  html: '/html/{tab_folder_name}/index.html?v={version_tag}',
  js: '/html/{tab_folder_name}/main.js?v={version_tag}'
}}
```

### 2. `config/tc_menu_config.json`:
```json
{{
  "id": "{clean_name}",
  "tab": "{tab_id}",
  "icon": "{args.icon}",
  "label": "{title}",
  "order": 50,
  "visible": true
}}
```
"""
    (target_dir / "README.md").write_text(readme_content, encoding="utf-8")

    print(f"[+] Вкладка успешно создана в: {target_dir}")
    print("\n[i] Код для добавления в apps/windows/api/webgui/core/tab-registry.js:")
    print(f"""  {{ id: '{clean_name}', label: '{title}', icon: '{args.icon}', tab: '{kebab_name}', tabId: '{tab_id}', html: '/html/{tab_folder_name}/index.html?v={version_tag}', js: '/html/{tab_folder_name}/main.js?v={version_tag}' }},""")
    print("\n[i] Код для добавления в apps/windows/api/webgui/config/tc_menu_config.json:")
    print(f"""  {{ "id": "{clean_name}", "tab": "{tab_id}", "icon": "{args.icon}", "label": "{title}", "order": 50, "visible": true }}""")


if __name__ == "__main__":
    main()

