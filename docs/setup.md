# Настройка окружения

Рабочее окружение проекта: Linux. На Windows это WSL2, альтернатива для любой системы: Docker. Нативный Windows тоже работает, uv кроссплатформенный, но проверяем и поддерживаем в первую очередь Linux. Окружением управляет [uv](https://docs.astral.sh/uv/): он ставит нужный Python, создаёт `.venv` и устанавливает зависимости точно по `uv.lock`, поэтому у всей команды одинаковые версии пакетов.

## Вариант A. Windows через WSL2

1. В PowerShell от администратора: `wsl --install -d Ubuntu`, перезагрузка, при первом запуске Ubuntu придумать пользователя и пароль.
2. В терминале Ubuntu: `sudo apt update && sudo apt install -y git curl`.
3. Репозиторий клонировать в файловую систему Linux, например в `~/projects`, а не в `/mnt/c/...`: на диске Windows git и Python работают в разы медленнее и бывают проблемы с правами.
4. Доступ к GitHub по SSH: ключ генерируется внутри Ubuntu, см. раздел "Доступ к GitHub по SSH" ниже. Ключ Windows в WSL не виден, это отдельная домашняя папка.
5. VS Code: поставить расширение **WSL**, затем в терминале Ubuntu внутри папки репозитория выполнить `code .`. Окно откроется в режиме WSL, расширения Python, Jupyter и Ruff ставятся в него отдельно.
6. Дальше общие шаги ниже. Настройки git из [CONTRIBUTING.md](../CONTRIBUTING.md) (почта, pull.rebase) хранятся в папке репозитория, в клоне под WSL их нужно задать заново.

## Вариант B. Linux или macOS

Нужны git и curl, дальше общие шаги.

## Вариант C. Windows без WSL

Работает, но на свой страх и риск. uv ставится из PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Дальше общие шаги, команды те же.

## Доступ к GitHub по SSH

С GitHub работаем по SSH, а не по HTTPS с паролем. Один раз в каждом окружении (Windows и WSL это разные окружения):

```bash
ssh-keygen -t ed25519 -C "ivanov@edu.hse.ru"   # путь по умолчанию, пароль на ключ по желанию
cat ~/.ssh/id_ed25519.pub                       # скопировать вывод целиком, одна строка
```

Публичный ключ добавить на GitHub: Settings > SSH and GPG keys > New SSH key, тип Authentication Key. Проверка:

```bash
ssh -T git@github.com
# Hi <ник>! You've successfully authenticated, but GitHub does not provide shell access.
```

Если ключ с паролем, чтобы не вводить его на каждый push: в Linux и WSL `eval "$(ssh-agent -s)" && ssh-add`, в Windows один раз включить службу ssh-agent в PowerShell от администратора: `Set-Service ssh-agent -StartupType Automatic; Start-Service ssh-agent`, затем `ssh-add`.

Приватный ключ `id_ed25519` никуда не копируем и не пересылаем, в репозиторий он не попадёт в любом случае.

Если репозиторий уже склонирован по HTTPS, переключить remote:

```bash
git remote set-url origin git@github.com:Icemist/hse-ai-2026-ecg-ptbxl.git
```

## Общие шаги

### 1. Установить uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Открыть новый терминал и проверить: `uv --version`.

### 2. Склонировать репозиторий и собрать окружение

```bash
git clone git@github.com:Icemist/hse-ai-2026-ecg-ptbxl.git
cd hse-ai-2026-ecg-ptbxl
uv sync
```

`uv sync` создаст `.venv` с Python 3.11 (версия в `.python-version`) и поставит всё из `uv.lock`, включая dev-группу: jupyter, ruff, pytest. Активировать окружение не обязательно: любая команда запускается через `uv run ...` и попадает в него автоматически.

Повторяйте `uv sync` после каждого `git pull`, если изменился `uv.lock`.

### 3. Скачать данные

```bash
uv run python scripts/download_ptbxl.py
```

Скрипт скачает PTB-XL 1.0.3 с PhysioNet (архив около 1,7 ГБ) и распакует в `data/raw/ptb-xl` (около 3 ГБ). Папка `data/` в `.gitignore`. Если скачивание прервалось, запустите скрипт ещё раз: готовый архив он не качает заново.

### 4. Проверить, что всё работает

```bash
uv run ruff check .
uv run pytest
```

Обе команды должны отработать без ошибок. Это те же проверки, что гоняет CI на каждый PR.

## Ноутбуки

```bash
uv run jupyter lab
```

В VS Code: открыть папку репозитория, в ноутбуке выбрать ядро из `.venv` (Select Kernel > Python Environments > `.venv`). Интерпретатор для обычных `.py` файлов тоже `.venv`.

## Docker

Нужен Docker Desktop (на Windows с бэкендом WSL2) или пакет docker в Linux. Образ описан в `Dockerfile` в корне: Python 3.11, uv и все зависимости из `uv.lock`, окружение внутри образа лежит в `/opt/venv`, поэтому `uv run` там не нужен.

```bash
docker build -t ecg-ptbxl .
docker run --rm -it -v "$PWD:/app" ecg-ptbxl                 # bash внутри контейнера, код с хоста
docker run --rm -it -v "$PWD:/app" ecg-ptbxl pytest          # разовая команда
docker run --rm -it -v "$PWD:/app" -p 8888:8888 ecg-ptbxl \
    jupyter lab --ip 0.0.0.0 --no-browser --allow-root        # ноутбуки в браузере на localhost:8888
```

Папка с кодом монтируется внутрь контейнера: правки на хосте сразу видны внутри, а скачанные в `data/` файлы остаются на хосте. После изменения `uv.lock` образ нужно пересобрать. В PowerShell вместо `$PWD` пишите `${PWD}`.

## Добавить зависимость

```bash
uv add <пакет>          # в проект
uv add --dev <пакет>    # только для разработки
```

Команда правит `pyproject.toml` и `uv.lock`, оба файла идут в коммит.

## Если что-то пошло не так

- `Permission denied (publickey)` при clone или push: ключ не добавлен на GitHub или в этом окружении его нет. Проверить `ssh -T git@github.com` и `ssh-add -l`, при необходимости повторить раздел про SSH.
- WSL: всё медленно или git жалуется на права. Репозиторий лежит на `/mnt/c`, перенесите его в домашнюю папку Linux.
- WSL: `code .` не найден. Поставьте расширение WSL в VS Code и откройте новый терминал Ubuntu.
- WSL: `docker: permission denied`. В Docker Desktop > Settings > Resources > WSL integration включите Ubuntu.
- `uv sync` жалуется на `.venv`: удалите папку `.venv` и запустите `uv sync` снова.
- Нужный Python не найден: `uv python install 3.11`, затем `uv sync`.
- Windows без WSL ругается на длинные пути: `git config --system core.longpaths true`, а для Python включить длинные пути Win32 в параметрах Windows.

Правила работы с ветками и PR: [CONTRIBUTING.md](../CONTRIBUTING.md).
