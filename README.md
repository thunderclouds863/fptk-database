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
| `INITIAL_ADMIN_PASSWORD` | recovery only | Creates an `admin` account when no active admin exists (and no user named `admin`). The admin must change it at first login. Remove it afterwards. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | for password recovery | Outgoing mail for "Lupa password". `SMTP_SECURITY` = `starttls` (default), `ssl` or `none`. |
| `APP_BASE_URL` | for password recovery | Public URL of the app, used in reset links (e.g. `https://fptk.example.com`). |
| `R2_*` | for file storage | Cloudflare R2 credentials (see `core/r2_storage.py`). |

Without SMTP settings the "Lupa password" page tells users to contact an admin; admins can
issue a one-time temporary password from **Pengguna**. Users need an email set in **Pengguna**
to use self-service recovery.

## First run (no administrator yet)

On an empty database the login page shows "Aplikasi belum disiapkan" and a **Pengaturan awal**
button instead of the login form. There is no public registration.

1. Open **Pengaturan awal**. The server writes a one-time setup code to its log (stderr), e.g.
   Streamlit Community Cloud → *Manage app* → *Logs*. The code is never shown in the browser.
2. Enter the code and the first administrator's username, name, optional email and password.

The code is valid for 60 minutes, single use, and voided after 5 wrong entries ("Buat kode baru"
issues a new one, at most once a minute). Only its SHA-256 hash is stored. Once an administrator
exists, setup is closed permanently. If every administrator is later lost, use
`INITIAL_ADMIN_PASSWORD` (above) as the deliberate server-side recovery path.

## When the database is unavailable

Instead of a stack trace, users see a short message with a code; details go to the server log only.

| Code | Meaning | Check |
|---|---|---|
| `DB-CONFIG` | `DATABASE_URL` missing or malformed | Deployment secrets / env |
| `DB-AUTH` | Database rejected the credentials | Username/password in `DATABASE_URL` |
| `DB-UNREACHABLE` | Server not responding | Host, network, database paused/sleeping |
| `DB-INIT` | Target database missing or schema setup failed | Database name, permissions, server log |

## Accounts & security

- Seeded recruiter accounts have no usable password until an admin issues a temporary one.
- Temporary passwords and old default passwords (`password123`, `admin123`, `it12345`) force a
  password change at the next login.
- Logins lock for 15 minutes after 5 failed attempts for a username (also for unknown usernames,
  so the message does not reveal which accounts exist).
- Schema changes are additive and applied automatically at startup (`core/database.py`).

## Tests

```bash
pip install pytest aiosmtpd
python -m pytest tests
# Optionally against a throwaway Postgres (never production):
TEST_DATABASE_URL="postgresql://user:pass@localhost:5432/fptk_test?sslmode=disable" python -m pytest tests
```
