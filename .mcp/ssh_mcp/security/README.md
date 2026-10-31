# security/ — Система безопасности и аудита

**Описание:** Защита учётных данных, проверка подлинности SSH-ключей серверов (`known_hosts`), аутентификация Remote MCP, контроль файловых путей, маскирование секретов и ведение неизменяемого журнала аудита.

## Файлы

- `credentials.py` — `CredentialManager` (хранение ссылок без записи паролей в SQLite).
- `host_verification.py` — `HostKeyVerifier` (защита от подмены SSH-сервера).
- `authentication.py` — `RemoteMCPAuthenticator` (проверка Bearer-токена, Origin и сетевой привязки).
- `authorization.py` — `PathPolicyValidator` (защита от Path Traversal).
- `secret_redactor.py` — `SecretRedactor` (очистка логов и ответов от паролей, ключей и токенов).
- `audit.py` — `AuditLogger` (журналирование всех административных операций).
