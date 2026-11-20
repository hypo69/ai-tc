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
  - Комплексное включение/отключение всех параметров одной кнопкой (`enable_all` / `disable_all`).
  - Индивидуальное управление сетевым профилем (`set_private_profile`), SMB (`enable_smb` / `disable_smb`), WinRM (`enable_winrm` / `disable_winrm`) и UAC (`enable_uac_remote` / `disable_uac_remote`).

---
**Updated:** 2026-11-20 20:45:00
