# platforms/ — Платформенные адаптеры Windows и Linux

**Описание:** Реализация OS-специфичной логики администрирования для Windows (PowerShell / CIM / EventLog) и Linux (Bash / procfs / systemd / iproute2) с возвратом унифицированных структур данных.

## Подпакеты

- `windows/` — `executor.py`, `system.py`, `processes.py`, `services.py`, `filesystem.py`, `network.py`, `users.py`, `events.py`.
- `linux/` — `executor.py`, `system.py`, `processes.py`, `services.py`, `filesystem.py`, `network.py`, `users.py`, `logs.py`.
