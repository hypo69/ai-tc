---
name: kernel-protection-agent
description: "Автономный агент и специализированный инженерный навык для аудита системных драйверов Windows, высот файловых минифильтров (fltmc), механизмов защиты ядра (HVCI, Secure Boot, UCPD, Defender Tamper Protection, WDAC) и расследования причин блокировок операций (Operation Blocker Detection)."
description_i18n:
  en: Autonomous agent and engineering skill for Windows kernel drivers audit, filesystem minifilters (fltmc), kernel protection mechanisms (HVCI, Secure Boot, UCPD, Tamper Protection), and Operation Blocker Detection.
  ru: Автономный агент и специализированный инженерный навык для аудита системных драйверов Windows, высот файловых минифильтров (fltmc), механизмов защиты ядра (HVCI, Secure Boot, UCPD, Defender Tamper Protection, WDAC) и расследования причин блокировок операций (Operation Blocker Detection).
---

# 🛡️ Агент защиты ядра и драйверов Windows (Kernel Protection Agent)

## 🎯 Назначение
Навык `kernel-protection-agent` предоставляет автономному AI-агенту возможности глубокого анализа, инвентаризации и диагностики подсистемы **Windows System Protection & Enforcement** на базе `apps/windows/sdk` (`windows_sdk.drivers`, `DriverInventoryManager`, `ProtectionMechanismsAuditor`, `OperationBlockerDetector`, `KernelSafeOpsManager`).

Агент решает ключевую задачу: **отличать обычный отказ в правах (Access Denied) от низкоуровневой системной защиты, фильтрации драйвером или административной политики**.

---

## 🏗️ Архитектура и компоненты SDK

Агент оперирует тремя фундаментальными категориями механизмов Windows:
1. **Драйверы-перехватчики и файловые фильтры (Minifilters)**:
   - `ucpd.sys` — User Choice Protection Driver (блокирует прямую смену ассоциаций браузера и файлов через реестр).
   - `WdFilter.sys` — Антивирусный минифильтр Microsoft Defender (высота Altitude: 328010).
   - `WdBoot.sys` — Ранняя антивирусная проверка при загрузке (ELAM).
   - `WdNisDrv.sys` — Сетевой компонент инспекции Defender.
   - `luafv.sys` — Фильтрация операций UAC и виртуализация реестра/файлов.
   - `bindflt.sys` — Файловая изоляция и перенаправление путей (контейнеры/WSL).
   - `wcifs.sys` — Контейнерная изоляция файловой системы.
   - `cldflt.sys` — Интеграция Cloud Files API (OneDrive).
   - `storqosflt.sys` и `iorate.sys` — Дросселирование и контроль качества дискового ввода-вывода.
2. **Защита ядра и целостности кода**:
   - `HVCI` / Memory Integrity — Изоляция ядра гипервизором VBS.
   - `Secure Boot` — Проверка доверенности загрузчиков UEFI.
   - `ELAM` & `Vulnerable Driver Blocklist` — Блокировка уязвимых драйверов (BYOVD).
   - `Code Integrity` (KMCI) — Обязательная цифровая подпись драйверов ядра.
3. **Системные ограничители**:
   - Microsoft Defender Tamper Protection — Защита от несанкционированного изменения антивируса.
   - App Control for Business (WDAC) & Smart App Control.
   - Group Policy (GPO) и MDM/CSP.
   - Дескрипторы безопасности NTFS/Registry ACL (TrustedInstaller / SYSTEM).

---

## 🔍 Интеллектуальное расследование блокировок (Operation Blocker Detection)

При возникновении ошибки **Access Denied** при попытке изменить реестр, службу или файл агент запускает 6-шаговую цепочку проверок:
1. Проверка токена UAC процесса (`IsUserAnAdmin`).
2. Проверка активности драйвера **UCPD** (ассоциации браузера `UserChoice`, `TaskbarDa`).
3. Проверка **Defender Tamper Protection** (попытки отключения антивируса).
4. Проверка владельца объекта по дескриптору безопасности (NTFS/Registry DACL).
5. Проверка контроля со стороны доменных или локальных политик **Group Policy / MDM**.
6. Анализ свежих событий Windows Event Log (CodeIntegrity 3076, Defender 5007, Security 4656).

На основе фактов формируется вердикт с расчетом достоверности (`confidence`) и пошаговым планом решения (`remediation_steps_ru`).

---

## 🛡️ Безопасное управление (SafeOps)

> [!CAUTION]
> **Принцип SafeOps:** Агент никогда не отключает критические драйверы ядра (`WdFilter`, `WdBoot`, `luafv`, `FileInfo`), так как это гарантированно приводит к отказу системы или BSOD.
> Для компонентов категории `MEDIUM` (например, `ucpd`) агент поддерживает контролируемый сценарий временной деактивации с обязательным созданием точки отката и последующим включением.

---

## 💻 Команды и запуск

### 1. Вызов через TUI / CLI
```powershell
# Сводный отчет о защите ядра и активных фильтрах
py -m apps.windows.sdk.modules.kernel_protection.tui summary

# Список зарегистрированных файловых минифильтров
py -m apps.windows.sdk.modules.kernel_protection.tui minifilters

# Расследование причины Access Denied для конкретного ключа или файла
py -m apps.windows.sdk.modules.kernel_protection.tui investigate "Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"

# Безопасное временное отключение UCPD для настройки ассоциаций
py -m apps.windows.sdk.modules.kernel_protection.tui safe-action disable_ucpd --confirm

# Восстановление штатной защиты UCPD
py -m apps.windows.sdk.modules.kernel_protection.tui safe-action enable_ucpd
```

### 2. Программное использование в Python
```python
from apps.windows.sdk import windows_sdk
from apps.windows.sdk.modules.kernel_protection.core import (
    BlockerInvestigationRequest,
    BlockerTargetType,
)

# 1. Получение инвентаря драйверов и механизмов
drivers = windows_sdk.drivers.inventory.get_all_system_drivers()
mechanisms = windows_sdk.drivers.mechanisms.audit_all_mechanisms()

# 2. Запуск расследования блокировки
verdict = windows_sdk.drivers.blocker_detector.investigate_blocker(
    BlockerInvestigationRequest(
        target_type=BlockerTargetType.REGISTRY_KEY,
        target_path=r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        operation="modify"
    )
)

print(f"Виновник блокировки: {verdict.culprit_title_ru} (Уверенность: {verdict.confidence})")
for step in verdict.remediation_steps_ru:
    print(f"Рекомендация: {step}")
```

### 3. WebGUI Вкладки и Панели
1. **Панель UCPD в Windows Sysadmin**:
   - URL: `http://127.0.0.1:8001/tc#tab-windows-admin#ucpd`
   - Инженерный пульт управления драйвером UCPD и задачей планировщика UcpdVelocity, статус перезагрузки, аудит исходного типа старта (SafeOps) и эмпирический стенд тестирования TaskbarDa.
2. **Консоль Kernel & Protection**:
   - URL: `http://127.0.0.1:8001/tc#tab-kernel-protection`
   - Интерактивный дашборд механизмов, каталог драйверов с интеграцией в `AIModalDialog`, высоты минифильтров `fltmc` и стенд Operation Blocker Detection.
