# Contributing to POCanator

Thanks for your interest in contributing! This project welcomes issues and pull
requests. By participating you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md) and the responsible-use policy in
[SECURITY.md](SECURITY.md).

## Ground rules

- Keep contributions aligned with the project's purpose: **defensive security
  and education**. We do not accept changes whose primary purpose is to weaponize
  the tool (e.g., targeting live systems, evasion, or mass exploitation).
- Be respectful and constructive in all interactions.

## Development setup

POCanator is a Django 4.2 application (Python 3.10) with an optional standalone
CLI.

```bash
# from the repository root
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# configure environment
cp .env.example .env
#   edit .env and set OPENAI_API_KEY (web app) / openaikey (CLI)

# database + run
python manage.py migrate --run-syncdb
python manage.py runserver
```

The app will be available at http://127.0.0.1:8000/.

> **Note on Python version:** the pinned dependencies (notably `lxml==4.9.3`)
> build cleanly on Python 3.10. Newer Python versions may require bumping those
> pins.

## Making changes

1. Fork the repository and create a topic branch:
   `git checkout -b feature/short-description`
2. Make your change. Keep commits focused and write clear messages.
3. Run Django's checks before pushing:
   ```bash
   python manage.py check
   python manage.py test
   ```
4. Open a pull request describing **what** changed and **why**. Link any
   related issues.

## Reporting bugs and requesting features

Open a GitHub issue with:

- A clear description and steps to reproduce (for bugs).
- Expected vs. actual behavior.
- Environment details (OS, Python version).

For security issues **in POCanator itself**, follow the private reporting
process in [SECURITY.md](SECURITY.md) instead of opening a public issue.

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE), consistent with the rest of the project.
