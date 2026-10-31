"""
=============================================================================
Process Name: Test Theme Editor Inheritance and Standard Themes Protection
=============================================================================
Description:
    Модульные тесты для проверки архитектуры наследования тем оформления:
    1. Неизменяемость и защита стандартных встроенных тем от перезаписи/удаления.
    2. Создание дочерней темы на базе выбранной стандартной (parent).
    3. Наследование базовых параметров (категория, baseType, токены родителя).
    4. Обновление, переименование, удаление и сброс дочерней темы к родителю.
    5. Корректное наполнение селекторов опций с группировкой дочерних тем.
    6. Наличие необходимых элементов UI (бейджи, алерты, модальные окна) в index.html.

File: test_theme_editor_inheritance.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-20 15:10:00
=============================================================================
"""

import json
from pathlib import Path
import subprocess
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_themes_directory_scanning_and_catalog() -> None:
    """Проверяет физическое размещение тем в директориях и работу генератора каталога."""
    from apps.windows.api.webgui.themes.generate_themes_catalog import scan_themes_directory, build_themes_catalog_file

    themes_root = _WEBGUI_DIR / "themes"
    assert themes_root.is_dir(), "Директория apps/windows/api/webgui/themes должна существовать"

    themes = scan_themes_directory(themes_root)
    assert len(themes) >= 10, f"Ожидалось не менее 10 тем в директориях, найдено: {len(themes)}"

    ids = {t["id"] for t in themes}
    assert "nightview" in ids, "Тема nightview должна присутствовать в каталоге"
    assert "light" in ids, "Тема light должна присутствовать в каталоге"
    assert "dark" in ids, "Тема dark должна присутствовать в каталоге"
    assert "theme-dark-slate" in ids, "Тема theme-dark-slate должна присутствовать в каталоге"

    # Проверка параметров nightview
    nv = next(t for t in themes if t["id"] == "nightview")
    assert nv["baseType"] == "light", f"nightview должна иметь baseType='light', получено {nv['baseType']}"
    assert nv["category"] == "light"
    assert nv["tokens"]["--bg-color"] == "#f5f2eb"

    # Проверка генерации файла каталога
    count = build_themes_catalog_file()
    assert count == len(themes)
    catalog_file = themes_root / "themes_catalog.json"
    assert catalog_file.is_file()



def test_theme_engine_source_code_integrity() -> None:
    """Проверяет наличие функций и сигнатур наследования в theme-engine.js."""
    engine_file = _WEBGUI_DIR / "js" / "theme-engine.js"
    assert engine_file.exists(), f"Файл {engine_file} не найден"
    content = engine_file.read_text(encoding="utf-8")

    # Константы хранилища
    assert "CUSTOM_THEMES_STORAGE_KEY = 'theme_custom_themes'" in content
    assert "BUILTIN_THEMES" in content

    # Ключевые методы для дочерних тем
    assert "loadCustomThemes()" in content
    assert "saveCustomThemes()" in content
    assert "createChildTheme(" in content
    assert "updateChildTheme(" in content
    assert "deleteChildTheme(" in content
    assert "resetChildThemeToParent(" in content
    assert "getCustomThemes()" in content
    assert "getChildTheme(" in content
    assert "getStandardThemes()" in content
    assert "isBuiltinTheme(" in content
    assert "isChildTheme(" in content
    assert "getParentTheme(" in content

    # Проверка защиты встроенных тем от модификации
    assert "Стандартные темы системы защищены от перезаписи" in content
    assert "Нельзя удалять встроенные стандартные темы" in content

    # Проверка наследования в applyTheme и previewTheme
    assert "data-parent-theme" in content
    assert "child-theme" in content
    assert "optgroup label=\"✨ Пользовательские (дочерние) темы\"" in content


def test_theme_facade_re_exports() -> None:
    """Проверяет реэкспорт новых функций работы с дочерними темами в theme.js."""
    facade_file = _WEBGUI_DIR / "js" / "theme.js"
    assert facade_file.exists(), f"Файл {facade_file} не найден"
    content = facade_file.read_text(encoding="utf-8")

    assert "CUSTOM_THEMES_STORAGE_KEY" in content
    assert "export function createChildTheme" in content
    assert "export function updateChildTheme" in content
    assert "export function deleteChildTheme" in content
    assert "export function resetChildThemeToParent" in content
    assert "export function getCustomThemes" in content
    assert "export function getChildTheme" in content
    assert "export function getStandardThemes" in content
    assert "export function isBuiltinTheme" in content
    assert "export function isChildTheme" in content


def test_theme_editor_html_structure_and_modals() -> None:
    """Проверяет разметку вкладки tab_theme_editor на наличие элементов управления дочерними темами."""
    html_file = _WEBGUI_DIR / "tab_theme_editor" / "index.html"
    assert html_file.exists(), f"Файл {html_file} не найден"
    content = html_file.read_text(encoding="utf-8")

    # Бейджи и алерты статуса
    assert 'id="theme-type-badge"' in content
    assert 'id="theme-inheritance-alert"' in content

    # Кнопки действий над дочерней темой
    assert 'id="theme-btn-create-child"' in content
    assert 'id="theme-btn-rename-child"' in content
    assert 'id="theme-btn-reset-to-parent"' in content
    assert 'id="theme-btn-delete-child"' in content

    # Модальные окна
    assert 'id="themeCreateChildModal"' in content
    assert 'id="child-theme-parent-select"' in content
    assert 'id="child-theme-name-input"' in content
    assert 'id="btn-confirm-create-child"' in content

    assert 'id="themeRenameChildModal"' in content
    assert 'id="child-theme-rename-input"' in content
    assert 'id="btn-confirm-rename-child"' in content


def test_theme_editor_panel_presets_and_actions() -> None:
    """Проверяет логику panel_presets и panel_actions вкладки tab_theme_editor."""
    presets_file = _WEBGUI_DIR / "tab_theme_editor" / "panel_presets" / "panel.js"
    assert presets_file.exists()
    presets_content = presets_file.read_text(encoding="utf-8")

    assert "export function getPreset" in presets_content
    assert "export function updateThemeStatusUI" in presets_content
    assert "export function populatePresetSelect" in presets_content
    assert "themelistchanged" in presets_content

    actions_file = _WEBGUI_DIR / "tab_theme_editor" / "panel_actions" / "panel.js"
    assert actions_file.exists()
    actions_content = actions_file.read_text(encoding="utf-8")

    assert "openCreateChildModal" in actions_content
    assert "btn-confirm-create-child" in actions_content
    assert "theme-btn-delete-child" in actions_content
    assert "theme-btn-reset-to-parent" in actions_content
    assert "theme-btn-rename-child" in actions_content


def test_theme_engine_runtime_in_node() -> None:
    """Выполняет реальный тест ThemeEngine в Node.js для проверки функционала создания и наследования."""
    node_script = """
    import { ThemeEngine, BUILTIN_THEMES } from './apps/windows/api/webgui/js/theme-engine.js';

    // Мок LocalStorage
    const storage = {};
    global.localStorage = {
      getItem: (k) => storage[k] || null,
      setItem: (k, v) => { storage[k] = String(v); },
      removeItem: (k) => { delete storage[k]; }
    };
    global.window = {
      matchMedia: () => ({ matches: false }),
      dispatchEvent: () => true
    };
    global.document = {
      documentElement: {
        setAttribute: () => {},
        removeAttribute: () => {},
        classList: { add: () => {}, remove: () => {} }
      },
      head: { appendChild: () => {} },
      createElement: () => ({ setAttribute: () => {}, textContent: '' }),
      getElementById: () => null,
      querySelectorAll: () => []
    };

    const engine = new ThemeEngine();

    // 1. Проверяем стандартные темы
    if (!engine.isBuiltinTheme('theme-dark-slate')) {
      throw new Error('theme-dark-slate должна быть стандартной темой');
    }
    if (engine.isChildTheme('theme-dark-slate')) {
      throw new Error('theme-dark-slate не должна быть дочерней темой');
    }

    // 1b. Проверяем Windows System Light и аутентичную NightView
    const sysLight = engine.getTheme('light');
    if (!sysLight || sysLight.name !== 'Windows System Light') {
      throw new Error('Тема "light" должна называться "Windows System Light", получено: ' + (sysLight ? sysLight.name : 'null'));
    }

    const nightView = engine.getTheme('nightview');
    if (!nightView || nightView.name !== 'NightView (Тёплая бумага)') {
      throw new Error('Тема "nightview" должна называться "NightView (Тёплая бумага)", получено: ' + (nightView ? nightView.name : 'null'));
    }
    if (nightView.tokens['--bg-color'] !== '#ede6d9' || nightView.tokens['--surface-1'] !== '#f6f1e8') {
      throw new Error('Некорректная палитра NightView (Warm Paper): ' + JSON.stringify(nightView.tokens));
    }

    // 1c. Проверяем полное покрытие токенов для NightView и Light (исключение лакун и просвечивания)
    const requiredTokens = [
      '--bg-color', '--surface-1', '--surface-2', '--card-bg', '--card-text',
      '--ui-bg-base', '--ui-bg-surface', '--ui-bg-surface-elevated',
      '--border-color', '--card-border', '--ui-border-color-subtle',
      '--badge-warning-bg', '--badge-warning-text', '--badge-warning-border',
      '--badge-danger-bg', '--badge-danger-text', '--badge-danger-border',
      '--badge-success-bg', '--badge-success-text', '--badge-success-border',
      '--badge-info-bg', '--badge-info-text', '--badge-info-border',
      '--badge-neutral-bg', '--badge-neutral-text', '--badge-neutral-border',
      '--bs-body-bg', '--bs-body-color', '--bs-card-bg', '--bs-card-color',
      '--bs-modal-bg', '--bs-modal-color', '--bs-tertiary-bg', '--bs-secondary-bg',
      '--table-bg', '--table-color', '--table-border-color', 'color-scheme'
    ];
    for (const t of requiredTokens) {
      if (!nightView.tokens[t]) {
        throw new Error(`В теме NightView отсутствует токен: ${t}`);
      }
      if (!sysLight.tokens[t]) {
        throw new Error(`В теме Windows System Light отсутствует токен: ${t}`);
      }
    }

    // 1d. Проверяем корректность переключения классов на body и очистку временных оверрайдов
    const bodyClasses = new Set();
    global.document.body = {
      className: '',
      classList: {
        add: (cls) => bodyClasses.add(cls),
        remove: (cls) => bodyClasses.delete(cls),
        contains: (cls) => bodyClasses.has(cls)
      }
    };
    engine.applyTheme('dark');
    if (!bodyClasses.has('theme-dark-slate')) {
      throw new Error('body должен содержать theme-dark-slate');
    }
    engine.applyTheme('nightview');
    if (bodyClasses.has('theme-dark-slate')) {
      throw new Error('theme-dark-slate не должен оставаться на body при переключении на nightview');
    }
    if (!bodyClasses.has('theme-nightview')) {
      throw new Error('body должен содержать theme-nightview');
    }

    // 2. Попытка перезаписать стандартную тему должна вызывать ошибку
    try {
      engine.updateChildTheme('theme-dark-slate', { name: 'Hack' });
      throw new Error('updateChildTheme на стандартной теме должна выбрасывать исключение');
    } catch (e) {
      if (!e.message.includes('защищены')) {
        throw new Error('Неожиданное сообщение об ошибке: ' + e.message);
      }
    }

    // 3. Создаем дочернюю тему на базе Dark Slate
    const child = engine.createChildTheme({
      name: 'Мой Тёмный Сланец',
      parentId: 'theme-dark-slate',
      tokens: {
        '--ui-accent': '#ff0055',
        '--radius-md': '14px'
      },
      settings: {
        fontSize: 18,
        borderRadius: 14
      }
    });

    if (!child.id || !child.isChild) {
      throw new Error('Дочерняя тема некорректно создана: ' + JSON.stringify(child));
    }
    if (child.baseType !== 'dark' || child.parentId !== 'theme-dark-slate') {
      throw new Error('Наследование от Dark Slate нарушено: baseType=' + child.baseType);
    }
    if (child.tokens['--ui-accent'] !== '#ff0055') {
      throw new Error('Токен --ui-accent не переопределен');
    }

    // 4. Проверяем наличие в реестре дочерних тем
    const customList = engine.getCustomThemes();
    if (customList.length !== 1 || customList[0].id !== child.id) {
      throw new Error('getCustomThemes() не вернул созданную тему');
    }

    // 5. Проверяем генерацию опций
    const optionsHtml = engine.renderOptionsHTML(child.id);
    if (!optionsHtml.includes('Мой Тёмный Сланец') || !optionsHtml.includes('на базе: Dark Slate')) {
      throw new Error('renderOptionsHTML не включил дочернюю тему: ' + optionsHtml);
    }

    // 6. Обновление дочерней темы
    engine.updateChildTheme(child.id, { name: 'Мой Обновленный Сланец' });
    const updated = engine.getChildTheme(child.id);
    if (updated.name !== 'Мой Обновленный Сланец') {
      throw new Error('Имя дочерней темы не обновилось');
    }

    // 7. Сброс дочерней темы к родителю
    engine.resetChildThemeToParent(child.id);
    const resetTheme = engine.getChildTheme(child.id);
    if (resetTheme.tokens['--ui-accent'] === '#ff0055') {
      throw new Error('Токен --ui-accent не был сброшен к родителю');
    }

    // 8. Удаление дочерней темы
    const deleted = engine.deleteChildTheme(child.id);
    if (!deleted || engine.getChildTheme(child.id) !== null) {
      throw new Error('Дочерняя тема не была удалена');
    }

    // 8b. Проверка создания дочерней темы на базе NightView
    const nvChild = engine.createChildTheme({
      name: 'Мой NightView Кастом',
      parentId: 'nightview',
      tokens: {
        '--ui-accent': '#2563eb'
      }
    });
    if (nvChild.parentId !== 'nightview' || nvChild.tokens['--bg-color'] !== '#ede6d9') {
      throw new Error('Дочерняя тема на базе NightView некорректна: ' + JSON.stringify(nvChild));
    }
    engine.deleteChildTheme(nvChild.id);

    // 8c. Проверка гарантированного сброса оверрайдов при переключении на стандартные темы
    storage['theme_custom_overrides'] = JSON.stringify({ '--bg-color': '#112233' });
    const mockStyleEl = { textContent: ':root { --bg-color: #112233 !important; }' };
    engine._customStyleEl = mockStyleEl;
    engine.applyTheme('nightview');
    if (mockStyleEl.textContent !== '') {
      throw new Error('Оверрайды _customStyleEl не были очищены при применении nightview');
    }
    if (storage['theme_custom_overrides']) {
      throw new Error('Ключ theme_custom_overrides должен быть удален из LocalStorage при переходе на стандартную тему');
    }
    // Проверяем, что _applyStoredOverrides не восстанавливает стили на стандартной теме
    engine._applyStoredOverrides();
    if (mockStyleEl.textContent !== '') {
      throw new Error('_applyStoredOverrides не должен применять стили к стандартной теме');
    }

    // 8d. Проверка динамического определения темы инлайн-скриптом без хардкода имён
    if (!storage['themes_catalog']) {
      throw new Error('Каталог themes_catalog должен быть автоматически сохранен в LocalStorage');
    }
    const cachedThemes = JSON.parse(storage['themes_catalog']);
    const cachedNightView = cachedThemes.find(t => t.id === 'nightview');
    if (!cachedNightView || cachedNightView.baseType !== 'light') {
      throw new Error('В кеше themes_catalog тема nightview должна иметь baseType === light');
    }

    console.log('ALL_NODE_TESTS_PASSED');
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", node_script],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Ошибка выполнения теста Node.js: {res.stderr}\n{res.stdout}"
    assert "ALL_NODE_TESTS_PASSED" in res.stdout

