# betdev-cloud/tailscale

Fork-репозиторий для автоматической сборки бинарников [tailscale/tailscale](https://github.com/tailscale/tailscale) и публикации их в GitHub Releases.

## Как это работает

1. `sync-tags.yml` раз в час проверяет новые stable-теги в upstream.
2. `sync_tags.py` создаёт такой же тег в этом репозитории на **upstream commit**, а не на `main`.
3. После создания тега запускается `build.yml`, который собирает `tailscale`, `tailscaled`, `derper`, `derpprobe` и публикует release.

## Changelog из upstream

Официальные GitHub Releases у Tailscale обычно содержат только ссылку на https://tailscale.com/changelog. Для release notes в этом репозитории используется скрипт `fetch_changelog.py`, который собирает заметки из нескольких upstream-источников:

1. **GitHub Release body** из `tailscale/tailscale`, если release уже существует.
2. **Список коммитов между предыдущим stable-тегом и текущим** через GitHub Compare API.
3. Ссылка на официальный changelog и upstream tag.

### Локальный запуск

```bash
uv sync
uv run python fetch_changelog.py v1.102.3
uv run python fetch_changelog.py v1.102.3 -o release-notes.md
```

Пример вывода для `v1.102.3`:

```markdown
# Tailscale v1.102.3

## Changes since v1.102.2

- ipn/ipnlocal,net/dns/resolver: prevent bare name resolution when MagicDNS is disabled (abc1234)
- feature/conn25: don't pre-size flow table maps (def5678)
...

---
Official changelog: https://tailscale.com/changelog
Upstream tag: https://github.com/tailscale/tailscale/tree/v1.102.3
Compare: https://github.com/tailscale/tailscale/compare/v1.102.2...v1.102.3
```

### Ручной запуск сборки

Workflow `Create and publish artifacts` можно запустить вручную с input `version`, например `v1.102.3`.

## Структура

| Файл | Назначение |
|------|------------|
| `sync_tags.py` | Синхронизация stable-тегов и trigger build |
| `fetch_changelog.py` | Формирование release notes из upstream |
| `github_utils.py` | Общие helper-функции для GitHub API |
| `.github/workflows/sync-tags.yml` | Cron-синхронизация тегов |
| `.github/workflows/build.yml` | Сборка и публикация release |

## Dry-run проверка в PR

Для pull request в `sync-tags.yml` добавлен отдельный job `sync_tags_dry_run`, который запускает:

```bash
uv run python sync_tags.py --dry-run
```

В этом режиме скрипт получает список тегов из upstream, определяет последний новый stable-тег и выводит план действий, но **не**:

- создаёт теги в форке;
- запускает workflow сборки.

## Ограничения

- Pre-release теги (`-pre`) игнорируются.
- Официальный changelog на tailscale.com рендерится на клиенте и не имеет публичного JSON API, поэтому для diff используется GitHub Compare API.
- Если upstream release ещё не создан, в release notes останется только diff коммитов и ссылка на официальный changelog.
