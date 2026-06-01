# SAM — десктоп (MVP: логи atm-ddc)

Первый модуль **System Admin Management**: выгрузка логов **atm-ddc-service** по номеру АТМ и дате — аналог скрипта `atm-ddc-logs.sh`, с графическим интерфейсом на **PyQt6**.

## Зависимости

Только пакеты из офлайн-набора репозитория — см. [`docs/AVAILABLE_LIBRARIES.md`](../docs/AVAILABLE_LIBRARIES.md):

- **paramiko** — SSH и SFTP
- **PyYAML** — конфигурация
- **PyQt6** (или PyQt5) — интерфейс

Установка: `scripts\install_offline.bat` из корня репозитория.

## Запуск

```bat
cd C:\path\to\sam-repo
python -m sam
```

или `run_sam.bat`.

При первом запуске настройте `sam_app_data\config.yaml` (скопируйте из [`config.example.yaml`](config.example.yaml)).

## Поведение

1. Подключение по SSH к хосту из `ssh` (там должны быть пути `/srv_mproc/...`).
2. Для каждого типа лога (**DDC**, **DDC5556**):
   - `zgrep` по архиву `atm-ddc.YYYY-MM-DD.*.gz` (и аналог для 5556);
   - если дата — сегодня, дополнительно `grep` по текущему файлу в `/log`.
3. Результат сохраняется локально: `{папка}/{ATM}/{ATM}_{MMDD}_DDC.txt`.
4. Опционально (`upload.enabled: true`) — отправка файлов на другой хост через SFTP (как `scp` в скрипте).

## Связь с RegCon

После выгрузки файлы можно обработать в **RegCon** (маскирование PAN и т.д.) — [`regcon/README.md`](../regcon/README.md).

## Дальше

- вход пользователей и аудит (см. корневой [`README.md`](../README.md));
- vault для паролей SSH;
- другие микросервисы и интервалы времени.
