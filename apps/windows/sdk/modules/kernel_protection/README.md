# Модуль защиты ядра и управления драйверами Windows (Kernel & Protection)

**Updated:** 2026-11-01 14:40:00

## 📋 Описание модуля

Модуль `kernel_protection` предоставляет комплексную систему аудита, диагностики и безопасного управления драйверами режима ядра и механизмами защиты Windows 11 (Windows System Protection & Enforcement).

Он разделяет системные ограничения на три ключевые категории:
1. **Драйверы-перехватчики и фильтры**: `ucpd.sys`, `WdFilter.sys`, `WdBoot.sys`, `WdNisDrv.sys`, `luafv.sys`, `bindflt.sys`, `wcifs.sys`, `cldflt.sys`, `storqosflt.sys`, `iorate.sys`, `FileInfo.sys` и зарегистрированные файловые минифильтры (`fltmc`).
2. **Защита ядра и целостности кода**: HVCI (Hypervisor-Enforced Code Integrity / Memory Integrity), Secure Boot, ELAM (Early Launch Anti-Malware), Vulnerable Driver Blocklist, Code Integrity (KMCI).
3. **Механизмы системных ограничений**: Microsoft Defender Tamper Protection, UAC / LUA Virtualization, App Control for Business (WDAC), Smart App Control, Group Policy (GPO) и MDM/CSP.

---

## 🔍 Интеллектуальный детектор блокировок (Operation Blocker Detection)

Модуль позволяет расследовать причину ошибки **Access Denied** при попытках программной модификации реестра, файлов или служб:
- Проверка токена UAC вызывающего процесса (Elevated vs Standard).
- Определение влияния драйвера **UCPD** (User Choice Protection Driver) при изменении ассоциаций браузера, PDF или параметров Taskbar.
- Проверка защиты **Microsoft Defender Tamper Protection**.
- Анализ владельца дескриптора безопасности (TrustedInstaller / SYSTEM DACL).
- Проверка переопределения политиками Group Policy / MDM.
- Выдача четкого вердикта и безопасных шагов решения проблемы.

---

## 🛡️ Безопасное управление (SafeOps)

Модуль строго запрещает неконтролируемое отключение критических компонентов ядра (уровень `CRITICAL`), предотвращая падение ОС в Blue Screen of Death (BSOD). Для компонентов уровня `MEDIUM` (например, `ucpd`) поддерживается контролируемый режим временной деактивации с автоматическим созданием точки отката (Rollback).

---

## 🌐 REST API Роутер (`/api/kernel-protection`)

- `GET /api/kernel-protection/summary` — Сводный отчет о драйверах и защите ядра.
- `GET /api/kernel-protection/drivers` — Инвентарь системных драйверов с поиском и фильтрацией.
- `GET /api/kernel-protection/minifilters` — Список активных файловых минифильтров и их высот (Altitudes).
- `GET /api/kernel-protection/mechanisms` — Статусы механизмов HVCI, Secure Boot, UCPD, Tamper Protection и др.
- `POST /api/kernel-protection/investigate-blocker` — Запуск расследования причины блокировки доступа.
- `POST /api/kernel-protection/safe-action` — Безопасное выполнение контролируемого действия SafeOps.
