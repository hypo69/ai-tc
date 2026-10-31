# transports/ — Транспортный уровень (Transport Layer)

**Описание:** Унифицированные транспорты доставки команд и файлов для локального, SSH и гибридного Remote MCP режимов.

## Файлы

- `base.py` — `BaseTransport`, `RawExecutionResult`.
- `ssh_transport.py` — `AsyncSSHTransport` с обязательной верификацией публичного ключа сервера.
- `sftp_transport.py` — `SFTPFileManager` с потоковым чтением/записью, контролем размера и SHA-256.
- `local_transport.py` — `LocalTransport` и `build_safe_shell_invocation` (раздельная передача параметров).
- `remote_mcp_transport.py` — `RemoteMCPTransport` для обращения к удалённому MCP-агенту по HTTPS.
