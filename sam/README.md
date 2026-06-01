# SAM — десктоп (выгрузка логов)

## Безопасность

| Что | Как |
|-----|-----|
| Несколько пользователей | `sam_app_data/users.json`, пароли только **bcrypt-хэш** |
| IP, SSH, пути, пароли серверов | В **vault.enc** (AES-GCM), ключ — master-пароль |
| В интерфейсе | IP показываются маской `10.11.***.***` |
| Аудит действий | `sam_app_data/audit/audit-YYYY-MM-DD.jsonl` (IP в записях тоже маскируются) |
| Технический лог | `sam_app_data/logs/sam-YYYY-MM-DD.log` (ошибки, этапы запуска) |

## Первый запуск

1. `python -m sam` — мастер: master vault + admin.
2. Или CLI: `python -m sam users create-admin ivanov --init-vault`
3. Вход логином/паролем SAM.
4. **Инфраструктура…** (admin) — IP, SSH, микросервисы.
5. **Пользователи…** (admin) — новые операторы.


## Выгрузка по кластерам и микросервисам

- **Источник** — кластер (FO, BO) с выбором узла или отдельный сервер (ATM).
- **Микросервисы** — в списке можно выбрать несколько (Ctrl+клик); для каждого выполняется отдельная выгрузка в одном SSH-сеансе.
- **Период** — дата и время «с» / «по»; если время не весь день, строки лога фильтруются по метке времени в строке (`YYYY-MM-DD HH:MM:SS` и `DD.MM.YYYY`).
- В vault JSON у каждого микросервиса: `target_type`, `target_id`, `log_layout` (`daily` | `hourly`), пути и `outputs`.

## Запуск

```bat
python -m sam
```

`python -m sam` = модуль `sam`, файл `sam/__main__.py` (вход, vault, окно).

## Роли

- **operator** — выгрузка логов
- **admin** — + пользователи, инфраструктура (vault)

## Переменные

- `SAM_MASTER_KEY` — base64, 32 байта (авто-разблокировка vault без диалога)

## Аудит (примеры событий)

`app.start`, `auth.login`, `vault.unlock`, `log.fetch.start`, `log.fetch.done`, `log.fetch.error`, `config.save`, `user.create`

## Библиотеки

[`docs/AVAILABLE_LIBRARIES.md`](../docs/AVAILABLE_LIBRARIES.md) — bcrypt, cryptography, paramiko, PyQt6, PyYAML.
