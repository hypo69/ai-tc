# Панель настройки входящего удалённого доступа (`panel_remote_access`)

Модуль субпанели вкладки `tab_network` для диагностики и быстрой настройки входящего удалённого доступа на компьютере Windows.

## Назначение

Устраняет ошибки подключения вида `Код: 53` (недоступность портов **SMB 445** и **WinRM 5985**) и `Код: 5` (`Access Denied` из-за UAC Remote Restrictions) при входе на компьютер из локальной сети.

## Функциональность

- **Диагностика (`GET /api/v1/network/remote-access/status`)**:
  - Проверка прав администратора процесса сервера.
  - Проверка сетевых профилей адаптеров (`Public` / `Private` / `DomainAuthenticated`).
  - Проверка службы `LanmanServer`, порта TCP `445` и входящего правила брандмауэра SMB-In.
  - Проверка службы `WinRM`, порта TCP `5985` и входящего правила брандмауэра WinRM-HTTP-In.
  - Проверка параметра реестра `LocalAccountTokenFilterPolicy`.
- **Управление (`POST /api/v1/network/remote-access/apply`)**:
  - Комплексное включение/отключение всех параметров одной кнопкой (`enable_all` / `disable_all`) с явным подтверждением перед сменой профиля `Public` → `Private`.
  - Индивидуальное управление сетевым профилем (`set_private_profile`), SMB (`enable_smb` / `disable_smb`), WinRM (`enable_winrm` / `disable_winrm`) и UAC (`enable_uac_remote` / `disable_uac_remote`).
- **Видимость в локальной сети (L1–L4) и File & Printer Sharing (`visibility_sharing.js`)**:
  - 4-уровневая диагностика (`GET /api/v1/network/visibility/diagnose`) с кодами `VIS001..VIS010` (Профиль сети, 6 служб `FDResPub`/`fdPHost`/`SSDPSRV`/`upnphost`/`LanmanServer`/`LanmanWorkstation`, Firewall, SMB 1.0/2/3).
  - Инвентаризация общих папок (`GET /api/v1/network/sharing/status`), удаление пользовательских шар (`DELETE /api/v1/network/sharing/shares/{name}`) и список активных SMB-сессий (`GET /api/v1/network/sharing/sessions`).
  - Раздельное включение/отключение File & Printer Sharing (`@FirewallAPI.dll,-28502`, только для `Private,Domain`) с автоматическим созданием снимка и кнопкой отката (`POST /api/v1/network/visibility/rollback/{snapshot_id}`).

---
**Updated:** 2026-11-20 22:05:00
