# SAM — System Admin Management

Единое десктоп-приложение (Python, PyQt6) для администраторов:

| Вкладка | Назначение |
|---------|------------|
| **Скачивание** | Логи с кластеров/серверов по SSH (read-only), период, grep, ZIP |
| **Обезличивание** | RegCon — поиск PAN/IP/паролей в локальных файлах, маскирование |
| **Подключения** | Vault (шифрование SSH), кластеры, микросервисы |
| **Пользователи** | Учётки SAM (bcrypt), роли operator/admin |

## Запуск

```bat
python -m sam
```

или `run_sam.bat`. Первый запуск — мастер: vault + admin.

## Данные на диске

| Каталог | Содержимое |
|---------|------------|
| `sam_app_data/config.yaml` | Публичные настройки |
| `sam_app_data/vault.enc` | IP, SSH, инфраструктура (AES-GCM) |
| `sam_app_data/users.json` | Пользователи SAM |
| `sam_app_data/audit/`, `logs/` | Аудит и тех. лог |
| `regcon_app_data/` | Настройки и вывод RegCon |

Авто-разблокировка vault: галочка «Сохранить ключ» → `master.key`, или `SAM_MASTER_KEY`.

## Офлайн-установка

См. [`docs/AVAILABLE_LIBRARIES.md`](docs/AVAILABLE_LIBRARIES.md), скрипт `scripts/install_offline.bat`.

## Тесты

```bat
python -m pytest tests/ -q
```

## Структура

- `sam/` — приложение, UI, vault, выгрузка логов  
- `regcon/` — модуль обезличивания (вкладка в SAM, пакет отдельно для тестов)  
- `tests/` — SAM + RegCon

Подробнее: [`sam/README.md`](sam/README.md).
