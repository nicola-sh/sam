# SAM — десктоп (выгрузка логов микросервисов)

Модуль **System Admin Management**: SSH-выгрузка логов с нескольких **микросервисов**, настраиваемых в `config.yaml`.

## Возможности

| Режим | Поведение |
|--------|-----------|
| **С фильтром** | `zgrep` / `grep` по значению (номер АТМ и т.д.) |
| **Без фильтра** | `zcat` / `cat` — полный лог за выбранную дату |
| **Даты** | Один день или период (до 31 дня) |
| **Микросервисы** | Список в конфиге + редактор в UI («Сервисы…») |
| **Пароли** | Зашифрованный **vault** (AES-GCM), не plain-text в git |

## Vault и секреты

1. При первом запуске задайте **master-пароль** (диалог).
2. Меню **«Секреты…»** — сохраните, например, `ssh_password`.
3. В `config.yaml`:

```yaml
ssh:
  username: shirnin_nv
  host: "10.11.44.10"
  password_secret: ssh_password
```

Файлы: `sam_app_data/vault.enc`, опционально `master.key` или переменная `SAM_MASTER_KEY` (base64, 32 байта).

Пароль в открытом виде в конфиге по-прежнему возможен (`password:`), но при сохранении из UI с `password_secret` поле `password` очищается.

## Микросервисы

```yaml
microservices:
  - id: atm-ddc
    name: ATM DDC Service
    service_dir: /srv_mproc/mproc/services/atm-ddc-service
    arch_subdir: /log_arch
    main_subdir: /log
    outputs:
      - id: DDC
        arch_prefix: atm-ddc
        main_name: atm-ddc
        main_only_today: true
```

Добавление других сервисов — через UI или правку YAML.

## Запуск

```bat
scripts\install_offline.bat
python -m sam
```

Шаблон конфига: [`config.example.yaml`](config.example.yaml).

## Библиотеки

[`docs/AVAILABLE_LIBRARIES.md`](../docs/AVAILABLE_LIBRARIES.md) — **paramiko**, **cryptography**, **PyYAML**, **PyQt6**.
