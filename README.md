# POCanator

**POCanator** is a platform for analyzing GitHub Security Advisories, extracting
the commits that fix them, and generating **educational** proof-of-concept (PoC)
material. It uses OpenAI models to explain vulnerabilities, assess patches, and
produce security-education content for defenders and researchers.

It ships as a **Django web application** plus an optional **standalone CLI**.

> ⚠️ **For authorized security research, defensive security, and education
> only.** Read [SECURITY.md](SECURITY.md) before use. You are responsible for
> using this tool lawfully and only against systems you own or are explicitly
> authorized to test.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## Features

- Fetch GitHub Security Advisories by search query
- Extract the commits/patches associated with each advisory
- Generate interactive HTML reports of advisories and their commits
- Filter to advisories that have fixing commits (richer input for analysis)
- Analyze advisories with OpenAI: vulnerability type, severity, patch
  effectiveness, and PoC feasibility
- Generate **educational** PoC examples with multi-stage prompting
- Framework-specific secure-coding guidance (Django, Node.js, and more)

### PoC generation approach

- **Multi-stage prompting** — vulnerability understanding → exploitation design
  → implementation → documentation
- **Example-guided generation** — concrete patterns for RCE, XSS, and SQLi
- **Framework-specific guidance** — secure alternatives shown alongside
  vulnerable patterns

## Requirements

- Python **3.10** (pinned deps, notably `lxml==4.9.3`, build cleanly on 3.10)
- An OpenAI API key (for analysis / PoC features)
- Optionally, Docker + Docker Compose

## Quick start (web platform)

### Local

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
#   edit .env: set OPENAI_API_KEY, SECRET_KEY, etc.

python manage.py migrate --run-syncdb
python manage.py createsuperuser   # or use the helper in start_local.sh
python manage.py runserver
```

Visit http://127.0.0.1:8000/. The provided `start_local.sh` automates the steps
above (and seeds an `admin`/`admin` superuser for local dev — change this).

### Docker

```bash
cp .env.example .env   # edit with your configuration
docker compose up -d --build
```

Then open http://localhost:8000/.

## Web platform overview

- **Advisory management** — import advisories from GitHub, browse, search, and
  view details.
- **Analysis** — generate AI-powered analyses with patch breakdowns and impact
  summaries.
- **Educational PoC generation** — request annotated code examples for a target
  language/framework, with explanations of the vulnerable pattern and secure
  fix.
- **Best practices** — framework-specific secure-coding guidance.

## Standalone CLI

The `pocanator.py` script provides the original command-line workflow.

> The CLI reads its OpenAI key from the **`openaikey`** environment variable
> (the web app uses `OPENAI_API_KEY`). Set `openaikey` in your `.env` when using
> the CLI.

Generate an HTML report of advisories:

```bash
python pocanator.py [--pages N] [--only-with-commits] [--query "search query"]
```

- `--pages N` — number of advisory pages to fetch (1–50)
- `--only-with-commits` — only advisories that have fixing commits
- `--query` — custom search (default: `rce type:reviewed`)

Analyze a single advisory with OpenAI:

```bash
python pocanator.py --gpthack https://github.com/advisories/GHSA-xxxx-xxxx-xxxx
```

This fetches the advisory and related commits, retrieves up to 3 patch diffs,
and produces a report covering the vulnerability explanation, patch analysis,
impact, a patch-effectiveness score, PoC feasibility, and a metrics table.

Example:

```bash
python pocanator.py --pages 5 --only-with-commits --query "sql injection type:reviewed"
```

### CLI output files

- `github_advisory_report.html` — interactive report of fetched advisories
- `GHSA-xxxx-xxxx-xxxx_analysis.md` — analysis written when using `--gpthack`

## Configuration

Copy `.env.example` to `.env` and set the values. Key variables:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | web | Django secret key (set a strong value) |
| `DEBUG` | web | `True` for local dev; set `False` in production |
| `ALLOWED_HOSTS` | web | Comma-separated hostnames |
| `OPENAI_API_KEY` | web | OpenAI key for analysis / PoC generation |
| `openaikey` | CLI | OpenAI key for `pocanator.py` |
| `GITHUB_TOKEN` | both | Optional, raises GitHub rate limits |

See `pocanator/settings.py` for the full list (model selection, token limits,
proxy settings, etc.).

## Documentation

Additional design and implementation notes live in [`docs/`](docs/), including
the PoC generation overview, data models, and the Django setup guide.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Please also
read the [Code of Conduct](CODE_OF_CONDUCT.md) and the responsible-use policy in
[SECURITY.md](SECURITY.md).

## License

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for
attribution.
