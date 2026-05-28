# Доступные библиотеки и офлайн-установка

Документ описывает **фактически доступный** набор пакетов (локальные `.whl` / `.tar.gz`), процесс установки без интернета и привязку к задачам **System Admin Management (SAM)**.

Манифест имён файлов: [`DATA/req.txt`](../DATA/req.txt) (59 позиций).  
Пины версий для `pip`: [`DATA/requirements-offline.txt`](../DATA/requirements-offline.txt).

---

## Требования к окружению

| Параметр | Рекомендация |
|----------|----------------|
| ОС | **Windows 10/11**, amd64 (большинство wheels — `win_amd64`) |
| Python | **3.13** (`cp313` в именах файлов) |
| Сеть | **Не требуется** при установке из локальной папки |
| Папка с дистрибутивами | `DATA\wheels\` — сюда кладутся все файлы из `req.txt` |

> В каталоге есть wheels для **PyPy** (`pp39`, `pp310`) и **macOS** (`PyQt6` universal2) — на Windows они не используются, но могут лежать рядом: `pip` выберет подходящий файл сам.

---

## Полный список доступных пакетов

| № | Пакет | Версия | Файл в `DATA\req.txt` | Назначение для SAM |
|---|--------|--------|------------------------|---------------------|
| 1 | altgraph | 0.17.4 | `altgraph-0.17.4-py2.py3-none-any.whl` | Зависимость PyInstaller |
| 2 | ansi2html | 1.9.2 | `ansi2html-1.9.2-py3-none-any.whl` | ANSI → HTML (логи в UI) |
| 3 | babel | 2.16.0 | `babel-2.16.0-py3-none-any.whl` | Локализация, даты в UI |
| 4 | **bcrypt** | 4.2.1 | `bcrypt-4.2.1-cp37-abi3-win_amd64.whl` | **Хэш паролей пользователей SAM** |
| 5 | cffi | 1.17.1 | `cffi-1.17.1-cp313-cp313-win_amd64.whl` | Зависимость cryptography |
| 6 | configparser | 7.0.1 | `configparser-7.0.1-py3-none-any.whl` | Расширенный config (backport) |
| 7 | contourpy | 1.3.1 | `contourpy-1.3.1-cp313-cp313-win_amd64.whl` | Зависимость matplotlib |
| 8 | contourpy | 1.3.1 (free-threaded) | `contourpy-1.3.1-cp313-cp313t-win_amd64.whl` | Только для Python 3.13t |
| 9 | **cryptography** | 43.0.3 | `cryptography-43.0.3-cp39-abi3-win_amd64.whl` | **Шифрование vault (SFTP/FTP секреты)** |
| 10 | cx_Oracle | 8.3.0 | `cx_Oracle-8.3.0-cp310-cp310-win_amd64.whl` | Oracle DB (если понадобится) |
| 11 | cycler | 0.12.1 | `cycler-0.12.1-py3-none-any.whl` | Зависимость matplotlib |
| 12 | **Django** | 5.1.7 | `Django-5.1.7-py3-none-any.whl` | **Веб-UI, пользователи, админка** |
| 13 | et_xmlfile | 2.0.0 | `et_xmlfile-2.0.0-py3-none-any.whl` | Зависимость openpyxl |
| 14 | fonttools | 4.55.0 | `fonttools-4.55.0-cp313-cp313-win_amd64.whl` | Шрифты / matplotlib |
| 15 | future | 1.0.0 | `future-1.0.0-py3-none-any.whl` | Совместимость Py2/3 кода |
| 16 | kiwisolver | 1.4.7 | `kiwisolver-1.4.7-cp313-cp313-win_amd64.whl` | Зависимость matplotlib |
| 17 | kiwisolver | 1.4.7 (PyPy) | `kiwisolver-1.4.7-pp310-pypy310_pp73-win_amd64.whl` | Не для CPython 3.13 |
| 18 | matplotlib | 3.9.2 | `matplotlib-3.9.2-cp313-cp313-win_amd64.whl` | Графики (статистика логов) |
| 19 | matplotlib | 3.9.2 (PyPy) | `matplotlib-3.9.2-pp39-pypy39_pp73-win_amd64.whl` | Не для CPython 3.13 |
| 20 | numexpr | 2.10.2 | `numexpr-2.10.2-cp313-cp313-win_amd64.whl` | Ускорение pandas |
| 21 | **numpy** | 2.1.3 | `numpy-2.1.3-cp313-cp313-win_amd64.whl` | Обработка больших данных |
| 22 | openpyxl | 3.1.5 | `openpyxl-3.1.5-py2.py3-none-any.whl` | Excel-отчёты |
| 23 | oracledb | 2.5.0 | `oracledb-2.5.0-cp313-cp313-win_amd64.whl` | Oracle (новый драйвер) |
| 24 | packaging | 24.2 | `packaging-24.2-py3-none-any.whl` | Версии пакетов / pip |
| 25 | pandas | 2.2.3 | `pandas-2.2.3-cp312-cp312-win_amd64.whl` | Для Python 3.12 |
| 26 | **pandas** | 2.2.3 | `pandas-2.2.3-cp313-cp313-win_amd64.whl` | **Разбор/фильтр больших логов** |
| 27 | pandastable | 0.13.1 | `pandastable-0.13.1.tar.gz` | Таблица в GUI (опционально) |
| 28 | **paramiko** | 3.5.1 | `paramiko-3.5.1-py3-none-any.whl` | **SFTP — основной доступ к логам** |
| 29 | pefile | 2023.2.7 | `pefile-2023.2.7-py3-none-any.whl` | Зависимость PyInstaller |
| 30 | pillow | 11.0.0 | `pillow-11.0.0-cp313-cp313-win_amd64.whl` | Изображения в UI |
| 31 | pip | 24.3.1 | `pip-24.3.1-py3-none-any.whl` | Установщик пакетов |
| 32 | psycopg2-binary | 2.9.10 | `psycopg2_binary-2.9.10-cp313-cp313-win_amd64.whl` | PostgreSQL |
| 33 | pyasn1 | 0.6.1 | `pyasn1-0.6.1-py3-none-any.whl` | ASN.1, зависимость crypto |
| 34 | pycparser | 2.22 | `pycparser-2.22-py3-none-any.whl` | Зависимость cffi |
| 35 | **pycryptodomex** | 3.22.0 | `pycryptodomex-3.22.0-cp37-abi3-win_amd64.whl` | **Доп. шифрование (AES, RSA)** |
| 36 | **pyinstaller** | 6.11.1 | `pyinstaller-6.11.1-py3-none-win_amd64.whl` | **Сборка SAM в .exe** |
| 37 | pyinstaller-hooks-contrib | 2024.10 | `pyinstaller_hooks_contrib-2024.10-py3-none-any.whl` | Хуки PyInstaller |
| 38 | **pyminizip** | 0.2.6 | `pyminizip-0.2.6.tar.gz` | **ZIP с паролем (экспорт)** |
| 39 | PyNaCl | 1.5.0 | `PyNaCl-1.5.0-cp36-abi3-win_amd64.whl` | Зависимость paramiko |
| 40 | pyparsing | 3.2.0 | `pyparsing-3.2.0-py3-none-any.whl` | Парсинг / matplotlib |
| 41 | **PyQt5** | 5.15.11 | `PyQt5-5.15.11-cp38-abi3-win_amd64.whl` | **Десктоп-GUI (вариант UI)** |
| 42 | PyQt6 | 6.7.1 | `PyQt6-6.7.1.tar.gz` | Исходники (сборка) |
| 43 | PyQt6 | 6.7.1 | `PyQt6-6.7.1-cp38-abi3-macosx_11_0_universal2.whl` | Только macOS |
| 44 | **PyQt6** | 6.8.1 | `PyQt6-6.8.1-cp39-abi3-win_amd64.whl` | **Десктоп-GUI (основной Qt6)** |
| 45 | PyQt6-Qt6 | 6.8.2 | `PyQt6_Qt6-6.8.2-py3-none-win_amd64.whl` | Qt6 runtime для PyQt6 |
| 46 | PyQt6_sip | 13.10.0 | `PyQt6_sip-13.10.0-cp313-cp313-win_amd64.whl` | SIP для PyQt6 |
| 47 | **PySimpleGUI** | 5.0.7 | `PySimpleGUI-5.0.7-py3-none-any.whl` | **Простой десктоп-GUI** |
| 48 | **python-dateutil** | 2.9.0.post0 | `python_dateutil-2.9.0.post0-py2.py3-none-any.whl` | **Разные форматы даты в логах** |
| 49 | **pytz** | 2024.2 | `pytz-2024.2-py2.py3-none-any.whl` | **Часовые пояса серверов** |
| 50 | pywin32-ctypes | 0.2.3 | `pywin32_ctypes-0.2.3-py3-none-any.whl` | Windows / PyInstaller |
| 51 | **PyYAML** | 6.0.3 | `pyyaml-6.0.3-cp313-cp313-win_amd64.whl` | **config.yaml серверов и сервисов** |
| 52 | **pyzipper** | 0.3.6 | `pyzipper-0.3.6-py2.py3-none-any.whl` | **AES-шифрование ZIP-архивов** |
| 53 | rsa | 4.9 | `rsa-4.9-py3-none-any.whl` | RSA, ключи |
| 54 | setuptools | 75.6.0 | `setuptools-75.6.0-py3-none-any.whl` | Сборка пакетов |
| 55 | sip | 6.10.0 | `sip-6.10.0-1-py3-none-any.whl` | Зависимость PyQt |
| 56 | six | 1.16.0 | `six-1.16.0-py2.py3-none-any.whl` | Совместимость |
| 57 | **tkcalendar** | 1.6.1 | `tkcalendar-1.6.1-py3-none-any.whl` | **Выбор даты в форме** |
| 58 | tzdata | 2024.2 | `tzdata-2024.2-py2.py3-none-any.whl` | База часовых поясов |
| 59 | xlrd | 2.0.1 | `xlrd-2.0.1-py2.py3-none-any.whl` | Чтение старых .xls |

### Чего нет в офлайн-наборе (из README, но можно заменить)

| Планировалось | Чем закрыть из доступного |
|---------------|---------------------------|
| FastAPI / uvicorn | **Django** 5.1.7 |
| passlib / argon2 | **bcrypt** 4.2.1 |
| SQLAlchemy | **Django ORM** или `sqlite3` (stdlib) |
| Typer / Rich | CLI на **stdlib** + PySimpleGUI |
| structlog | **`logging` + JSON** (stdlib) для аудита |
| FTPS | **stdlib** `ftplib` + **cryptography** |

---

## Рекомендуемый стек SAM на доступных библиотеках

| Задача | Библиотеки из списка |
|--------|----------------------|
| SFTP, логи 1–4 ГБ | **paramiko**, stdlib `io` |
| UI (простой) | **PySimpleGUI** + **tkcalendar** или **PyQt6** |
| UI (веб, несколько пользователей) | **Django** (auth, сессии, админка) |
| Пароли SAM | **bcrypt** |
| Vault SFTP/FTP | **cryptography**, **pycryptodomex** |
| Архив на FTP | **pyzipper** / **pyminizip**, stdlib **ftplib** |
| Конфиг | **PyYAML** |
| Время в логах | **python-dateutil**, **pytz**, **tzdata** |
| Анализ / grep по большим файлам | **pandas** (chunks), stdlib **re** |
| Сборка .exe для операторов | **pyinstaller** |
| Аудит действий | stdlib **json**, **logging** |

---

## Подготовка папки `DATA\wheels`

1. Создайте каталог `DATA\wheels` в корне репозитория.
2. Скопируйте в него **все** файлы из вашего локального набора (список — в `DATA\req.txt`).
3. Убедитесь, что имена файлов совпадают с манифестом (регистр букв важен на Linux; на Windows обычно без разницы).

Структура:

```
sam/
├── DATA/
│   ├── req.txt
│   ├── requirements-offline.txt
│   └── wheels/          ← все .whl и .tar.gz
├── docs/
│   └── AVAILABLE_LIBRARIES.md
└── scripts/
    ├── install_offline.bat
    └── install_offline.ps1
```

---

## Процесс установки (офлайн, Windows)

### Шаг 1. Python 3.13

Установите [Python 3.13](https://www.python.org/downloads/) для Windows (amd64).  
При установке отметьте **«Add python to PATH»**.

Проверка:

```bat
python --version
```

Ожидается: `Python 3.13.x`.

### Шаг 2. Виртуальное окружение (рекомендуется)

Из корня проекта:

```bat
cd /d C:\path\to\sam
python -m venv .venv
.venv\Scripts\activate
```

### Шаг 3. Установка pip и setuptools из локальных wheels

```bat
python -m pip install --no-index --find-links=DATA\wheels --upgrade pip setuptools
```

### Шаг 4. Установка всех зависимостей SAM

**Вариант А — автоматический скрипт (рекомендуется):**

```bat
scripts\install_offline.bat
```

**Вариант Б — вручную одной командой:**

```bat
python -m pip install --no-index --find-links=DATA\wheels -r DATA\requirements-offline.txt
```

**Вариант В — установка каждого файла из манифеста (если Б не сработал):**

```bat
for /F %f in (DATA\req.txt) do python -m pip install --no-index --find-links=DATA\wheels DATA\wheels\%f
```

> Вариант В может установить лишние варианты (PyPy/macOS). Лучше использовать `requirements-offline.txt`.

### Шаг 5. Проверка установки

```bat
python -c "import paramiko; import django; import bcrypt; import cryptography; import yaml; print('OK')"
```

При успехе выводится `OK`.

Проверка версий:

```bat
pip list
```

### Шаг 6. Пакеты из `.tar.gz` (если ошибка сборки)

В наборе два исходника, которым может понадобиться компилятор C++:

| Файл | Решение |
|------|---------|
| `pandastable-0.13.1.tar.gz` | Опционален; для MVP можно не ставить |
| `pyminizip-0.2.6.tar.gz` | Использовать **pyzipper** (wheel) вместо pyminizip |
| `PyQt6-6.7.1.tar.gz` | На Windows использовать wheel **PyQt6-6.8.1** (уже в списке) |

Если `pip` ругается на `pandastable` или `pyminizip`, установите остальное без них:

```bat
python -m pip install --no-index --find-links=DATA\wheels -r DATA\requirements-offline.txt --ignore-installed pandastable pyminizip
```

или временно закомментируйте эти две строки в `requirements-offline.txt`.

---

## PowerShell (альтернатива)

```powershell
Set-Location C:\path\to\sam
.\.venv\Scripts\Activate.ps1
.\scripts\install_offline.ps1
```

---

## Порядок установки при конфликтах зависимостей

Если полная установка падает, ставьте группами:

```bat
python -m pip install --no-index --find-links=DATA\wheels pip setuptools packaging six pycparser cffi
python -m pip install --no-index --find-links=DATA\wheels cryptography bcrypt PyNaCl pyasn1 rsa
python -m pip install --no-index --find-links=DATA\wheels paramiko PyYAML python-dateutil pytz tzdata
python -m pip install --no-index --find-links=DATA\wheels numpy pandas pyzipper pycryptodomex
python -m pip install --no-index --find-links=DATA\wheels Django PySimpleGUI tkcalendar PyQt6 PyQt6-Qt6 PyQt6_sip
python -m pip install --no-index --find-links=DATA\wheels pyinstaller pyinstaller-hooks-contrib altgraph pefile pywin32-ctypes
```

---

## Обновление набора библиотек

1. Добавьте новый `.whl` в `DATA\wheels\`.
2. Допишите строку в `DATA\req.txt`.
3. Добавьте `имя==версия` в `DATA\requirements-offline.txt`.
4. Обновите таблицу в этом файле.
5. Переустановите: `scripts\install_offline.bat`.

---

## Минимальная установка только для MVP логов

Если нужен только доступ к SFTP и фильтр по времени без GUI:

```bat
python -m pip install --no-index --find-links=DATA\wheels paramiko cryptography bcrypt PyNaCl cffi pycparser pyasn1 rsa PyYAML python-dateutil pytz tzdata pyzipper
```

FTP — через stdlib `ftplib` (устанавливать нечего).
