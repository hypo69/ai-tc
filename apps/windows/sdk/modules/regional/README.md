# 🌐 Модуль региональных параметров Windows (`apps.windows.sdk.modules.regional`)

## 📋 Обзор модуля

Пакет **`apps.windows.sdk.modules.regional`** является официальным компонентом Windows SDK проекта **ai-tc**.
Он инкапсулирует все прямые низкоуровневые операции с операционной системой Windows, связанные с:
1. **Языковыми пакетами (Language Packs / MUI)**: считывание установленных пакетов из системного реестра (`HKLM\SYSTEM\CurrentControlSet\Control\MUI\UILanguages`), активных раскладок пользователя и безопасная установка через PowerShell (`Install-Language`, `Set-WinUserLanguageList`).
2. **Часовыми поясами (Timezones)**: инспекция через `[System.TimeZoneInfo]` и изменение через `tzutil.exe /s`.
3. **Локалями (Locales)**: считывание и назначение системной ANSI локали (`Set-WinSystemLocale`) и пользовательской культуры (`Set-Culture`).
4. **Учетной записью пользователя**: сбор SID, профиля, домена, прав администратора и групп безопасности.
5. **Свойствами хоста**: определение и смена рабочей группы (`NetGetJoinInformation` / `Add-Computer`) и имени компьютера (`Rename-Computer`).

## 🧱 Архитектура и компоненты

- **`manager.py` (`RegionalManager`)**: Главный класс-фасад для всех операций. Исключает прямое обращение к ОС из API-роутеров.
- **`models.py`**: Pydantic-модели данных (`LanguagePackModel`, `TimezoneModel`, `LocaleModel`, `UserAccountModel`).
- **`__init__.py`**: Точка входа подпакета.

## 💡 Пример использования в Python

```python
from apps.windows.sdk import windows_sdk

# Получение списка языковых пакетов
packs = windows_sdk.modules.regional.get_language_packs()
for pack in packs:
    print(pack["tag"], pack["name"], pack["is_installed"])

# Установка/активация пакета
result = windows_sdk.modules.regional.install_language_pack("he-IL")
print(result)

# Смена часового пояса
windows_sdk.modules.regional.set_timezone("Russian Standard Time")
```
