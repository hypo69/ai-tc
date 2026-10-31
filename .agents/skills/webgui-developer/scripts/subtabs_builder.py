"""
=============================================================================
Process Name: WebGUI Developer Skill - Subtabs Nav Builder CLI
=============================================================================
Description:
  Инструмент автоматической генерации и внедрения субменю переключения панелей
  в едином стиле верхнего меню (кнопки btn-outline-primary с иконками).
  Позволяет спрятать громоздкие вертикальные секции страницы под аккуратные
  горизонтальные кнопки меню с иконками, заголовком, подзаголовком и
  автоматической синхронизацией выбранной панели в URL (#tab-<tabId>#<panelId>).

Usage Examples:
  1. Генерация HTML шаблона шапки и суб-вкладок:
     py .agents/skills/webgui-developer/scripts/subtabs_builder.py generate \
       --title "Мониторинг процессов" \
       --subtitle "Диспетчер задач и активность" \
       --icon "⚡" \
       --prefix "proc" \
       --tabs "manager:'Диспетчер процессов':bi-layout-text-window-reverse:text-primary top:'Топ процессов':bi-speedometer2:text-warning"

  2. Быстрая генерация JSON-конфигурации:
     py .agents/skills/webgui-developer/scripts/subtabs_builder.py config-template --out config.json

File: subtabs_builder.py
Project: ai-windows-admin
Package: .agents/skills/webgui-developer/scripts
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-28 16:35:00
=============================================================================
"""

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Установка UTF-8 для вывода в консоль Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def build_subtabs_header_html(
    title: str,
    subtitle: str,
    icon: str,
    prefix: str,
    tabs: List[Dict[str, str]],
    extra_badge: Optional[str] = None,
    extra_btn: Optional[str] = None
) -> str:
    """Генерирует HTML разметку верхней шапки с иконкой, заголовком и меню в стиле верхнего меню."""
    nav_id = f"{prefix}-subtabs-nav"
    badge_html = f'\n          {extra_badge}' if extra_badge else ''
    btn_wrapper = f'\n    <div class="d-flex align-items-center gap-2">\n      {extra_btn}\n    </div>' if extra_btn else ''

    btn_items = []
    for i, tab in enumerate(tabs):
        tab_id = tab['id']
        label = tab['label']
        bi_icon = tab.get('icon', 'bi-card-checklist')
        icon_color = tab.get('icon_color', '')
        icon_cls = f"{bi_icon} {icon_color}".strip()
        is_active = (i == 0)
        active_cls = " active" if is_active else ""

        btn_id = f"subtab-{prefix}-{tab_id}-btn"
        target_pane_id = f"subpane-{prefix}-{tab_id}"

        btn_items.append(
            f'      <button class="btn btn-sm btn-outline-primary{active_cls} d-flex align-items-center gap-1.5 py-1 px-2.5 rounded" '
            f'id="{btn_id}" data-panel-id="{tab_id}" data-bs-toggle="pill" data-bs-target="#{target_pane_id}" type="button" role="tab">\n'
            f'        <i class="{icon_cls}"></i>\n'
            f'        <span>{label}</span>\n'
            f'      </button>'
        )

    buttons_html = "\n".join(btn_items)

    html = f"""  <!-- Заголовок вкладки -->
  <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
    <div class="d-flex align-items-center gap-2">
      <span class="fs-4 text-warning">{icon}</span>
      <div>
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <h5 class="mb-0 fw-bold text-white">{title}</h5>{badge_html}
        </div>
        <small class="text-secondary">{subtitle}</small>
      </div>
    </div>{btn_wrapper}
  </div>

  <!-- Блок меню переключения панелей на вкладке. Выбранная панель добавляется в url -->
  <div class="d-flex align-items-center mb-3 pb-2 border-bottom border-secondary border-opacity-25 flex-wrap gap-2">
    <div class="d-flex align-items-center gap-1 flex-wrap" id="{nav_id}" role="tablist">
{buttons_html}
    </div>
  </div>"""
    return html


def build_tab_pane_wrapper(prefix: str, tab_id: str, inner_content: str, is_active: bool = False, panel_id: Optional[str] = None) -> str:
    """Оборачивает содержимое секции в tab-pane."""
    active_cls = " show active" if is_active else ""
    pane_id = f"subpane-{prefix}-{tab_id}"
    panel_attr = f' data-panel-id="{panel_id}"' if panel_id else ''

    return f"""    <!-- Subpane: {tab_id} -->
    <div class="tab-pane fade{active_cls}" id="{pane_id}" role="tabpanel"{panel_attr}>
{inner_content}
    </div>"""


def build_subtabs_js_helper(prefix: str, tabs: List[Dict[str, str]], function_name: Optional[str] = None) -> str:
    """Генерирует JS функцию для программного переключения между субвкладками с обновлением URL."""
    fn_name = function_name or f"switch{prefix.capitalize()}SubTab"
    nav_id = f"{prefix}-subtabs-nav"
    tab_id = f"tab-{prefix}"

    mapping_entries = []
    for tab in tabs:
        t_id = tab['id']
        btn_id = f"subtab-{prefix}-{t_id}-btn"
        mapping_entries.append(f"    case '{t_id}':\n      btnId = '{btn_id}';\n      canonical = '{t_id}';\n      break;")

    cases_code = "\n".join(mapping_entries)
    default_tab = tabs[0]["id"]

    return f"""/**
 * Обновляет адресную строку браузера активной суб-панелью (#{tab_id}#<panel_id>).
 * @param {{string}} panelId - Идентификатор панели.
 */
function updateUrlWithPanel(panelId) {{
  if (typeof location === 'undefined') return;
  const newHash = `#{tab_id}#${{panelId}}`;
  if (location.hash !== newHash) {{
    try {{
      history.replaceState(null, null, `${{location.pathname}}${{location.search || ''}}${{newHash}}`);
    }} catch (_) {{}}
  }}
}}

/**
 * Программное переключение между суб-вкладками раздела ({prefix}).
 * @param {{string}} subtabId - Идентификатор подвкладки
 * @param {{boolean}} [updateUrl=true] - Обновлять ли URL
 */
window.{fn_name} = function(subtabId, updateUrl = true) {{
  let btnId = 'subtab-{prefix}-{default_tab}-btn';
  let canonical = '{default_tab}';
  switch (subtabId) {{
{cases_code}
  }}
  const btn = document.getElementById(btnId);
  if (btn) {{
    if (window.bootstrap && window.bootstrap.Tab) {{
      const tabInst = window.bootstrap.Tab.getInstance(btn) || new window.bootstrap.Tab(btn);
      tabInst.show();
    }} else {{
      btn.click();
    }}
  }}
  if (updateUrl) {{
    updateUrlWithPanel(canonical);
  }}
}};

// Подключение слушателей кнопок меню для автоматической передачи активной панели в URL
const subnavEl = document.getElementById('{nav_id}');
if (subnavEl && !subnavEl.dataset.urlBound) {{
  subnavEl.dataset.urlBound = 'true';
  subnavEl.addEventListener('click', (e) => {{
    const btn = e.target.closest('button[data-panel-id]');
    if (btn) {{
      const pId = btn.getAttribute('data-panel-id');
      if (pId) updateUrlWithPanel(pId);
    }}
  }});
  subnavEl.querySelectorAll('button[data-bs-toggle="pill"]').forEach((btn) => {{
    btn.addEventListener('shown.bs.tab', (e) => {{
      const pId = e.target.getAttribute('data-panel-id');
      if (pId) updateUrlWithPanel(pId);
    }});
  }});
}}"""


def parse_tabs_cli_arg(tabs_str: str) -> List[Dict[str, str]]:
    """
    Парсит CLI строку параметров табов вида:
    "id1:'Метка 1':icon1:color1 id2:'Метка 2':icon2:color2"
    """
    tabs = []
    tokens = shlex.split(tabs_str.strip())
    for token in tokens:
        if not token:
            continue
        parts = token.split(':')
        tab_id = parts[0].strip()
        label = parts[1].strip() if len(parts) > 1 else tab_id.capitalize()
        icon = parts[2].strip() if len(parts) > 2 else "bi-card-checklist"
        icon_color = parts[3].strip() if len(parts) > 3 else ""
        tabs.append({
            "id": tab_id,
            "label": label,
            "icon": icon,
            "icon_color": icon_color
        })
    return tabs


def main():
    parser = argparse.ArgumentParser(description="WebGUI Subtabs Builder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Команда generate
    gen_parser = subparsers.add_parser("generate", help="Сгенерировать HTML/JS код суб-вкладок")
    gen_parser.add_argument("--title", required=True, help="Главный заголовок вкладки")
    gen_parser.add_argument("--subtitle", default="", help="Подзаголовок вкладки")
    gen_parser.add_argument("--icon", default="📦", help="Emoji или символ иконки")
    gen_parser.add_argument("--prefix", required=True, help="Префикс идентификаторов (напр. sw, proc, net)")
    gen_parser.add_argument("--tabs", required=True, help="Строка спецификации вкладок: id:label:icon:color ...")
    gen_parser.add_argument("--js-fn", default=None, help="Имя JS функции переключения (по умолчанию switch<Prefix>SubTab)")

    # Команда config-template
    tpl_parser = subparsers.add_parser("config-template", help="Создать пример конфигурации JSON")
    tpl_parser.add_argument("--out", required=True, help="Путь к результирующему файлу JSON")

    args = parser.parse_args()

    if args.command == "generate":
        tabs = parse_tabs_cli_arg(args.tabs)
        html = build_subtabs_header_html(args.title, args.subtitle, args.icon, args.prefix, tabs)
        js = build_subtabs_js_helper(args.prefix, tabs, args.js_fn)

        print("<!-- === HTML HEADER & SUBTABS === -->")
        print(html)
        print("\n<!-- === JAVASCRIPT SWITCHER HELPER === -->")
        print(js)

    elif args.command == "config-template":
        sample = {
            "title": "Установленные программы и Мониторинг ПО",
            "subtitle": "Полная инвентаризация установленных программ Windows",
            "icon": "📦",
            "prefix": "sw",
            "tabs": [
                {"id": "inventory", "label": "Реестр программ (Инвентарь)", "icon": "bi-card-checklist", "icon_color": "text-primary"},
                {"id": "packages", "label": "Менеджер пакетов", "icon": "bi-box-seam", "icon_color": "text-info"},
                {"id": "dormant", "label": "Спящие программы и Сироты", "icon": "bi-clock-history", "icon_color": "text-warning"}
            ]
        }
        out_path = Path(args.out)
        out_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"Шаблон сохранен в: {out_path}")


if __name__ == "__main__":
    main()

