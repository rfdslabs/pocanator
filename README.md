```
 ____   ___   ____                  _
|  _ \ / _ \ / ___|__ _ _ __   __ _| |_ ___  _ __
| |_) | | | | |   / _` | '_ \ / _` | __/ _ \| '__|
|  __/| |_| | |__| (_| | | | | (_| | || (_) | |
|_|    \___/ \____\__,_|_| |_|\__,_|\__\___/|_|

      Security advisories → patches → educational analysis
```

<div align="center">

**Analyze GitHub Security Advisories, read the commits that fix them, and
generate _educational_ proof-of-concept material — with OpenAI _or_ Claude.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![Django 4.2](https://img.shields.io/badge/django-4.2-092E20.svg)](https://www.djangoproject.com/)
[![Providers: OpenAI · Claude](https://img.shields.io/badge/LLM-OpenAI%20%C2%B7%20Claude-5A4FcF.svg)](#-multi-provider-llm)

</div>

> [!WARNING]
> **For authorized security research, defensive security, and education only.**
> Read [SECURITY.md](SECURITY.md) before use. You are responsible for using this
> tool lawfully and only against systems you own or are explicitly authorized to
> test. POCanator is built to _explain_ vulnerabilities and patches for
> defenders — it does not produce weaponized exploits.

---

## What it does

POCanator is a **Django web application** (plus an optional **standalone CLI**)
that turns a public GitHub Security Advisory into a readable, trustworthy
security-education artifact:

1. **Fetch** advisories from GitHub by search query.
2. **Extract** the commits/patches that fix them.
3. **Read** those patches in a modern, GitHub-style diff viewer.
4. **Analyze** the vulnerability and patch with an LLM — structured output, not
   scraped prose.
5. **Learn** from framework-specific secure-coding guidance and annotated,
   educational PoC examples.

## Highlights

- 🔌 **Multi-provider LLM** — OpenAI **and** Anthropic Claude behind one
  interface; pick the model per analysis, provider inferred automatically.
  Default: **Claude Sonnet 5.5**.
- 🧠 **Structured analysis** — vulnerability type, severity, CWE, patch
  effectiveness, PoC feasibility, and a confidence score, parsed from JSON (no
  brittle regex scraping). Token count and estimated cost are shown per run.
- 💸 **Result caching** — an unchanged advisory isn't re-analyzed (and re-billed);
  the stored result is reused, with **Regenerate** always forcing a fresh run.
- 🔍 **Readable diffs** — line-number gutter, syntax highlighting, `+`/`-`
  markers, per-file collapse, and a binary-file state. Patch content is
  HTML-escaped (no stored XSS).
- 🎓 **Educational PoC generation** — multi-stage prompting that pairs vulnerable
  patterns with their secure fix, never weaponized code.
- 🖥️ **Web + CLI** — a full web UI, or a scriptable one-shot CLI.

## 🔌 Multi-provider LLM

The analysis engine is provider-pluggable (`apps/analysis/providers/`). Choose a
model from one grouped dropdown; the provider is derived from the model.

| Provider  | Models                                              | Key |
| --------- | --------------------------------------------------- | --- |
| Anthropic | `claude-sonnet-5-5` (default), `claude-opus-5-5`, `claude-haiku-5-5` | `ANTHROPIC_API_KEY` or per-user profile |
| OpenAI    | `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`            | `OPENAI_API_KEY` or per-user profile |

Keys resolve **per the chosen model's provider**: a key saved on your user
profile wins, otherwise the server's environment key is used. Adding a third
provider is a new file in the `providers/` package, not a refactor.

## Requirements

- **Python 3.10** — pinned dependencies (notably `lxml==4.9.3`) build cleanly on
  3.10. Newer interpreters may fail to build the pins.
- An **OpenAI** and/or **Anthropic** API key (for analysis / PoC features).
- Optionally, **Docker + Docker Compose**.

## Quick start

### Local

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
#   edit .env: set SECRET_KEY, and at least one of
#   ANTHROPIC_API_KEY / OPENAI_API_KEY

python manage.py migrate --run-syncdb
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/. The provided `start_local.sh` automates these steps
(and seeds an `admin`/`admin` superuser for local dev — **change it**).

> [!NOTE]
> Migrations are intentionally disabled (`MIGRATION_MODULES=None`); the schema is
> created with `migrate --run-syncdb`. When upgrading an **existing** database to
> a version that adds columns, apply the matching `ALTER TABLE`s (see
> [CHANGELOG.md](CHANGELOG.md)), since `--run-syncdb` only creates missing tables.

### Docker

```bash
cp .env.example .env   # edit with your configuration
docker compose up -d --build
```

Then open http://localhost:8000/.

## Using the web app

| Area | What you do |
| --- | --- |
| **Advisories** | Import advisories from GitHub, browse, search, view details. |
| **Patches** | Read the fixing commits in a GitHub-style diff viewer. |
| **Analysis** | Generate a structured AI analysis; see CWE, scores, tokens, and estimated cost; **Regenerate** to refresh. |
| **PoC (educational)** | Request annotated examples for a language/framework — the vulnerable pattern _and_ its secure fix. |
| **Profile** | Save your personal OpenAI/Anthropic keys and default model. |

## Standalone CLI

The `pocanator.py` script provides the original command-line workflow.

> The CLI reads its OpenAI key from the **`openaikey`** environment variable (the
> web app uses `OPENAI_API_KEY`). Set `openaikey` in your `.env` for the CLI.

```bash
# Build an HTML report of advisories
python pocanator.py [--pages N] [--only-with-commits] [--query "search query"]

# Analyze a single advisory
python pocanator.py --gpthack https://github.com/advisories/GHSA-xxxx-xxxx-xxxx
```

- `--pages N` — advisory pages to fetch (1–50)
- `--only-with-commits` — only advisories that have fixing commits
- `--query` — custom search (default: `rce type:reviewed`)

**Output files**

- `github_advisory_report.html` — interactive report of fetched advisories
- `GHSA-xxxx-xxxx-xxxx_analysis.md` — analysis written when using `--gpthack`

## Configuration

Copy `.env.example` to `.env` and set the values. Key variables:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | web | Django secret key — set a strong value |
| `DEBUG` | web | `True` for local dev; `False` in production |
| `ALLOWED_HOSTS` | web | Comma-separated hostnames |
| `ANTHROPIC_API_KEY` | web | Anthropic (Claude) key for analysis / PoC |
| `OPENAI_API_KEY` | web | OpenAI key for analysis / PoC |
| `openaikey` | CLI | OpenAI key for `pocanator.py` |
| `GITHUB_TOKEN` | both | Optional — raises GitHub rate limits |

See `pocanator/settings.py` for the full list (model selection, token limits,
proxy settings, etc.).

## Project layout

```
apps/
  advisories/   # fetch + store GitHub Security Advisories
  patches/      # commits, file changes, and the diff viewer
  analysis/     # LLM analysis engine
    providers/  #   pluggable OpenAI / Anthropic providers + model catalog
  pocs/         # educational PoC generation
  users/        # accounts, profiles, per-user API keys
pocanator/      # Django project (settings, urls, wsgi/asgi)
pocanator.py    # standalone CLI
docs/           # design + implementation notes
```

Run the test suite with:

```bash
python manage.py test
```

## Documentation

Design and implementation notes live in [`docs/`](docs/), including the
multi-provider + caching design and the Sprint 1 analysis/diff design under
`docs/superpowers/specs/`.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Please also
read the [Code of Conduct](CODE_OF_CONDUCT.md) and the responsible-use policy in
[SECURITY.md](SECURITY.md). New work follows a test-driven workflow; keep
`python manage.py test` green.

## License

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for
attribution.
