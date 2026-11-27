# FPTK & Sourcing System

Streamlit-based web application for FPTK and Sourcing management.

## Run locally

```bash
pip install -r requirements.txt
DEMO_MODE=1 streamlit run demo_app.py   # SQLite demo data; demo_admin / demo123
streamlit run app.py                    # production mode, needs DATABASE_URL
```

## Configuration

Set as environment variables (`.env`) or Streamlit secrets.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes (prod) | Postgres URL (or `[connections.postgresql] url` in secrets) |
| `INITIAL_ADMIN_PASSWORD` | first run only | Creates the `admin` account when no admin exists. The admin must change it at first login. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | for password recovery | Outgoing mail for "Lupa password". `SMTP_SECURITY` = `starttls` (default), `ssl` or `none`. |
| `APP_BASE_URL` | for password recovery | Public URL of the app, used in reset links (e.g. `https://fptk.example.com`). |
| `R2_*` | for file storage | Cloudflare R2 credentials (see `core/r2_storage.py`). |

Without SMTP settings the "Lupa password" page tells users to contact an admin; admins can
issue a one-time temporary password from **Pengguna**. Users need an email set in **Pengguna**
to use self-service recovery.

## Accounts & security

- Seeded recruiter accounts have no usable password until an admin issues a temporary one.
- Temporary passwords and old default passwords (`password123`, `admin123`, `it12345`) force a
  password change at the next login.
- Accounts lock for 15 minutes after 5 failed logins.
- Schema changes are additive and applied automatically at startup (`core/database.py`).

## Tests

```bash
pip install pytest aiosmtpd
python -m pytest tests
```
