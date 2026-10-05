# Как работаем

Соглашение о разработке для команды 146. Окружение и запуск описаны в [docs/setup.md](docs/setup.md).

## Ветки и pull request

- В `main` напрямую не пушим, ветка защищена. Под каждую задачу своя ветка от свежего `main`.
- Имя ветки: `ник/короткое-описание`, например `avoronov/download-script`, `ira/label-stats`.
- PR вливается, когда его одобрил кто-то из команды и все замечания в ревью закрыты (кнопка Resolve). Правило действует на всех, включая владельца репозитория.
- Вливание только **Rebase and merge**, мердж-коммитов в `main` не бывает. Если GitHub предлагает обновить ветку, выбираем "Update with rebase".
- CI на каждый PR: `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest`. Красный CI не вливаем.
- После вливания ветка на GitHub удаляется сама. Локальную убираем через `git branch -d <ветка>`, устаревшие ссылки на удалённые ветки чистит `git fetch -p`.

## Коммиты

- GitHub при вливании коммиты не склеивает, поэтому перед PR история приводится в порядок: "fix", "wip", "ещё раз" сжимаем через `git rebase -i main`. Один коммит на одно осмысленное изменение.
- Сообщение коммита: первая строка до 72 символов, что сделано и зачем, без точки в конце. Язык русский или английский, но в одном коммите один.
- Коммиты подписываем вузовской почтой, см. настройку git ниже.

## Настройка git один раз

Выполняется в папке склонированного репозитория, без `--global`, чтобы не трогать другие проекты. Настройки живут в этом клоне: если клонируете ещё раз, например в WSL, повторите.

```bash
git config pull.rebase true          # git pull перебазирует ветку, а не делает мердж-коммит
git config rebase.autoStash true     # незакоммиченные правки на время rebase откладываются сами
git config user.email ivanov@edu.hse.ru
git config user.name "Иван Иванов"
```

Почта должна быть добавлена и подтверждена в GitHub (Settings > Emails), иначе коммиты не привяжутся к профилю.

С GitHub работаем по SSH: remote вида `git@github.com:Icemist/hse-ai-2026-ecg-ptbxl.git`, ключ создаётся по инструкции в [docs/setup.md](docs/setup.md).

## Типичный цикл

```bash
git checkout main
git pull
git checkout -b ivanov/new-feature
# правки, коммиты
git push -u origin ivanov/new-feature
# дальше PR на GitHub, ревью, Rebase and merge
```

## Код

- Форматирование и линтер: ruff, настройки в `pyproject.toml` (длина строки 100). Перед PR: `uv run ruff format .` и `uv run ruff check .`.
- Переиспользуемый код живёт в пакете `src/ecg_ptbxl`, ноутбуки в `notebooks/` его импортируют, а не копируют.
- На новый модуль в `src/` хотя бы один тест в `tests/`.
- Новая зависимость: `uv add <пакет>`, для инструментов разработки `uv add --dev <пакет>`. Обновлённый `uv.lock` коммитится вместе с кодом.

## Что не попадает в git

- Данные: папка `data/` целиком в `.gitignore`, её создаёт и наполняет `scripts/download_ptbxl.py`.
- Артефакты моделей, логи MLflow, выходы экспериментов: `models/`, `mlruns/`, `outputs/`.
- Секреты и локальные настройки: `.env`, `.venv/`.

## Шпаргалка по uv

Окружение и зависимости:

```bash
uv sync                        # создать или обновить .venv строго по uv.lock (после clone и после каждого pull)
uv sync --locked               # то же, но упасть, если lock разошёлся с pyproject (так делает CI)
uv add <пакет>                 # добавить зависимость проекта: правит pyproject.toml и uv.lock
uv add --dev <пакет>           # добавить инструмент разработки (линтер, тесты, ноутбуки)
uv remove <пакет>              # убрать зависимость
uv lock --upgrade-package <пакет>   # поднять версию одного пакета в lock
uv lock --upgrade              # поднять всё, что позволяют ограничения в pyproject (отдельным PR)
uv tree                        # дерево зависимостей: кто кого притащил
uv pip list                    # что реально стоит в .venv
```

Запуск внутри окружения, активировать `.venv` не нужно:

```bash
uv run python scripts/download_ptbxl.py
uv run pytest
uv run jupyter lab
uv run python -c "import ecg_ptbxl; print(ecg_ptbxl.__version__)"
uv run --with <пакет> python   # разово попробовать пакет, не добавляя в проект
```

Если всё же хочется активировать окружение: `source .venv/bin/activate` (Linux, macOS, WSL), в Windows PowerShell `.venv\Scripts\activate`. После этого `uv run` можно не писать.

Интерпретаторы и починка:

```bash
uv python list                 # какие Python видит uv
uv python install 3.11         # поставить нужную версию, если в системе нет
uv cache clean                 # если установка странно ломается
rm -rf .venv && uv sync        # пересобрать окружение с нуля (в PowerShell: Remove-Item -Recurse .venv)
uvx <инструмент>               # запустить утилиту без установки в проект, например uvx ruff --version
```

## Шпаргалка по ruff

Три команды перед каждым PR, в таком порядке:

```bash
uv run ruff format .           # отформатировать код
uv run ruff check . --fix      # найти ошибки и починить безопасные: порядок импортов, неиспользуемые импорты
uv run pytest                  # тесты
```

Остальное:

```bash
uv run ruff check .            # только показать проблемы, ничего не менять
uv run ruff format --check .   # только проверить форматирование (так делает CI)
uv run ruff check src/ecg_ptbxl/features.py   # один файл или папка
uv run ruff rule B008          # объяснение правила по коду из сообщения об ошибке
```

Что включено в `pyproject.toml`: `E` и `F` (синтаксис, неиспользуемые имена и импорты), `I` (порядок импортов), `B` (типичные баги вроде изменяемого значения по умолчанию), `UP` (устаревший синтаксис). Длина строки 100. Ноутбуки ruff не проверяет.

Отключить правило точечно, только с кодом и причиной:

```python
import torch  # noqa: F401  нужен для регистрации бэкенда
```

В VS Code: расширение Ruff (`charliermarsh.ruff`), в настройках включить Format on Save, тогда первая команда из списка выполняется сама при сохранении файла.
