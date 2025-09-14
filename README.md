# ERISA Challenge — Claims Management (Django)

A minimal, production-ready Django app for managing ERISA claims.  
Includes searchable/paginated claim lists, detail views, inline notes, CSV import, and a Render/Postgres deployment setup.

## Demo
- **Live app:** https://erisa-challenge.onrender.com/
- **Public repo:** https://github.com/harishnaidumaddala/erisa-challenge

> Create a regular demo user for reviewers (non-admin) and list it here once created.

---

## Features
- **Claims**: list, sort, search (claim id / patient / payer / status), pagination, detail page
- **Notes**: add inline notes on a claim (auth required)
- **CSV Import**: staff-only CSV upload page and a robust management command
- **Auth**: login/logout, basic permissions (only authenticated users can post notes)
- **DX/UX**: partial templates for snappy updates; clean dark theme with easy color presets
- **Deployable**: Render + Postgres + WhiteNoise static serving; environment-driven settings

---

## Tech Stack
- **Backend**: Django 4.2
- **DB**: Postgres (Render) / SQLite (local)
- **Server**: Gunicorn + UvicornWorker (ASGI)
- **Static**: WhiteNoise (Brotli compression)
- **Config**: `dj-database-url`, `.env` file

**requirements.txt (minimal)**
```
Django==4.2.24
gunicorn==22.0.0
uvicorn==0.30.6
whitenoise[brotli]==6.7.0
dj-database-url==2.2.0
psycopg2-binary==2.9.9
```

---

## Project Structure (high level)
```
erisa_challenge/
  settings.py
  urls.py
  wsgi.py
  asgi.py
claims/
  models.py        # Claim, Note
  views.py
  forms.py
  urls.py
  management/commands/load_claims.py  # CSV loader (see below)
templates/
  base.html
  registration/    # login template(s)
  claims/
    claim_list.html
    claim_detail.html
    csv_upload.html
    partials/
      note_item.html
static/
  css/theme.css     # optional theme switcher
requirements.txt
manage.py
```

---

## Data Model (summary)
- **Claim**
  - `claim_number` (unique), `claimant`, `payer`, `status`
  - `billed_amount`, `paid_amount` (Decimal), `service_date` (Date)
- **Note**
  - FK to Claim, `body`, `created_by` (User), `created_at`

---

## Quick Start (local)

### 1) Prerequisites
- Python **3.12**
- Git

### 2) Setup
```bash
git clone https://github.com/harishnaidumaddala/erisa-challenge.git
cd erisa-challenge
  
python -m venv .venv
# Windows
. .venv/Scripts/activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # create this file if not present (see below)
python manage.py migrate
```

### 3) (Optional) Load demo data
Choose one:

**Fixtures**
```bash
python manage.py loaddata fixtures/seed.json
```

**CSV management command**
```bash
python manage.py load_claims data/claims.csv
```
CSV headers (example):  
`claim_number,claimant,payer,status,billed_amount,paid_amount,service_date`

### 4) Run
```bash
python manage.py runserver
```
- App: http://127.0.0.1:8000/
- Admin (after you create one): http://127.0.0.1:8000/admin/
```bash
python manage.py createsuperuser
```

---

## Environment Variables

Create `.env` in the project root:

```env
# .env.example
SECRET_KEY=changeme-super-secret
DEBUG=1                      # 1=on (local), 0=off (prod)
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

> On Render you **don’t** set `DEBUG=1`. Render sets `RENDER_EXTERNAL_HOSTNAME` automatically; settings read it into `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

---

## CSV Loader Command

**File:** `claims/management/commands/load_claims.py`  
**Usage:**
```bash
python manage.py load_claims path/to/claims.csv
```
- Enforces decimal/date parsing.
- Uses `update_or_create(claim_number=...)` for idempotent imports.
- Logs per-row failures and continues.

---

## Tests (basic)
```bash
python manage.py test
```
Add/extend tests for:
- List filtering by query/status
- Note creation (auth required)
- CSV import happy/edge cases

---

## Deployment (Render)

**Build Command**
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

**Start Command** (ASGI preferred)
```
gunicorn erisa_challenge.asgi:application -k uvicorn.workers.UvicornWorker
```
*(Fallback WSGI: `gunicorn erisa_challenge.wsgi:application`)*

**Environment Variables (Render)**
- `DATABASE_URL` = Postgres **Internal** URL from your Render database
- `SECRET_KEY` = strong random string
- `PYTHON_VERSION` = `3.12.5`

**Settings highlights**
- `whitenoise.middleware.WhiteNoiseMiddleware` after `SecurityMiddleware`
- `STATIC_ROOT = BASE_DIR / "staticfiles"`
- `STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"`
- `dj_database_url.config(..., conn_max_age=600)`
- Append `RENDER_EXTERNAL_HOSTNAME` to `ALLOWED_HOSTS`
- Set `CSRF_TRUSTED_ORIGINS = ["https://<render-hostname>"]`

**After first deploy**
```bash
# In Render Shell
python manage.py createsuperuser
```

---

## Screenshots
Add screenshots in `/docs` and embed them here:
```md
![Claims list](docs/claims_list.png)
```

---

## Submission Checklist
- [ ] Public GitHub repo with `README.md` and `requirements.txt`
- [ ] Data loader available (`load_claims` or fixtures)
- [ ] Clear setup/run instructions + `.env.example`
- [ ] Render deployment working (demo URL opens in incognito)
- [ ] Demo user (non-admin) created and listed here
- [ ] Basic tests pass locally

---

## Troubleshooting

**DisallowedHost**  
Ensure your settings append `RENDER_EXTERNAL_HOSTNAME` to `ALLOWED_HOSTS`. Redeploy.

**Static files 404**  
Check WhiteNoise middleware, `STATIC_ROOT`, and that `collectstatic` ran in the build.

**DB connection errors**  
Use the **Internal Database URL**; put the web service and DB in the same region.

**`metadata-generation-failed` during build**  
Use `psycopg2-binary` (not `psycopg2`), set `PYTHON_VERSION=3.12.5`, and avoid `backports.zoneinfo` (not needed on Python ≥ 3.9).

---

## License
MIT — feel free to use and adapt.

---

## Acknowledgments
Built for the ERISA Challenge to demonstrate pragmatic Django patterns: environment-driven settings, simple CSV import, and a clean path to deployment.
