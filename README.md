# University Equipment Borrowing & Return Management System

## GitHub Pages (no Render required for live inventory)

The deployed `index.html` is a **read-only Oracle inventory dashboard**. It loads equipment and, when available, category names from `https://oracleapex.com/ords/dawood/` directly in the browser. It includes equipment search and status/category filters. It does **not** load borrowers or loan records, nor does it send any POST/PUT/PATCH/DELETE requests. No API secrets belong in the HTML.

**Important:** Browser access requires ORDS to send a compatible `Access-Control-Allow-Origin` header for the GitHub Pages origin. A JSON endpoint opening in a browser tab proves server-side GET works, but does not prove cross-origin `fetch` from GitHub Pages works. Configure CORS in Oracle ORDS if the website shows a CORS/network error.

For secure Borrow/Return, use the existing authenticated Oracle APEX application. The repository also has an optional Flask app which can support write operations **only when hosted** and configured with server-side credentials. GitHub Pages cannot run Flask. No Render account is required for the read-only site.

---


This Flask website has been adapted to the exact Oracle table and column names in the supplied `Website.sql` file.

## 1. Database schema used

The app expects these four existing Oracle tables:

- `UEB_CATEGORIES` — `CATEGORYID`, `CATEGORYNAME`, `DESCRIPTION`
- `UEB_EQUIPMENT` — `EQUIPMENTID`, `CATEGORYID`, `EQUIPMENTNAME`, `MODEL`, `SERIALNUMBER`, `PURCHASEDATE`, `CONDITION`, `STATUS`
- `UEB_BORROWERS` — `BORROWERID`, `NAME`, `EMAIL`, `PHONE`, `BORROWERTYPE`, `DEPARTMENT`, `ROLE`
- `UEB_BORROWING_RECORDS` — `BORROWID`, `EQUIPMENTID`, `BORROWERID`, `ISSUEDATE`, `DUEDATE`, `RETURNDATE`, `RETURNCONDITION`, `LOANSTATUS`, `REMARKS`

The accepted values follow your SQL: borrower types `Student`, `Teacher`, `Staff`; borrower roles `Admin`, `LabStaff`, `Borrower`; equipment conditions `Good`, `Damaged`, `Missing`; equipment statuses `Available`, `Borrowed`, `Maintenance`; loan statuses `Borrowed`, `Returned`, `Missing`; return conditions `Good`, `Damaged`.

`database/Website.sql` is a copy of the SQL file you supplied. If you have already run it successfully in your APEX SQL Workshop, do not run it again because the tables already exist. It contains seed rows as well as table, constraint, index and trigger definitions.

## 2. How the website connects

The Flask app talks to Oracle through ORDS REST endpoints. It uses the actual no-underscore Oracle column names in JSON requests and normalizes ORDS response field names for the website templates. The workspace owner provided these custom ORDS module paths (rather than default AutoREST table paths):

- `https://oracleapex.com/ords/dawood/categories/`
- `https://oracleapex.com/ords/dawood/equipment/`
- `https://oracleapex.com/ords/dawood/borrowers/`
- `https://oracleapex.com/ords/dawood/borrowing-records/`

An equipment API JSON response was supplied as a screenshot; that establishes a working public read endpoint but **does not** establish permission to write, browser CORS support, or that all four endpoints are available. Test each one individually. No secrets are required for public GET requests; authenticated POST/PUT/DELETE requests require backend-only ORDS credentials.

For this Oracle workspace, set `ORDS_BASE_URL=https://oracleapex.com/ords/dawood/`. Keep write credentials in server-side environment variables, never in GitHub Pages JavaScript. This Flask app must run on a Python-capable host (for example, Render); GitHub Pages alone only serves the static `index.html` and cannot run Flask.

## 3. Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this project folder.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in the values.
5. Run `python app.py`.
6. Open `http://127.0.0.1:5000`.

Required environment values:

- `SECRET_KEY`: long random secret used to sign browser sessions.
- `ORDS_BASE_URL`: the base URL for your schema's ORDS REST endpoints, ending in the schema alias path.
- `ORDS_BEARER_TOKEN`: bearer token, if you configured OAuth; otherwise use the username/password variables only if your ORDS setup explicitly supports Basic authentication.
- `ADMIN_USERNAME` and `ADMIN_PASSWORD`: website admin login.
- `STAFF_USERNAME` and `STAFF_PASSWORD`: website staff login (optional).
- `VIEWER_USERNAME` and `VIEWER_PASSWORD`: website read-only login (optional).

Never share or commit `.env`, passwords, OAuth tokens or secret keys. The login credentials are configured separately in the hosting environment; they are not automatically authenticated against the `ROLE` column in `UEB_BORROWERS`.

## 4. GitHub and Render deployment

1. Create a private GitHub repository and upload the contents of this folder.
2. In Render, create a Web Service and connect that repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add the environment variables from `.env.example` in Render's Environment settings.
6. Deploy, then test the live URL.

Free hosting availability and limits can change. A free web service may sleep when idle; treat this as a student project/demo deployment, not production-grade university infrastructure.

## 5. Website functions

- Dashboard totals for equipment, available items, borrowed items and overdue loans.
- Add, edit and delete categories, equipment and borrowers (delete is admin-only).
- Issue equipment only when its current status is `Available` and condition is `Good`.
- Return a borrowed item and record `Good` or `Damaged` condition.
- Borrowing history and overdue report.
- Flask login roles: admin, staff and viewer.

The Oracle trigger in your SQL updates equipment status when a loan is inserted or its loan status changes. The unique function-based index prevents a second active `Borrowed`/`Missing` record for the same equipment. The website also checks availability before issuing; the database remains the final authority.

## 6. Important limitations before real use

This is a student-project starter, not a security-audited production system. The publicly hosted `index.html` is a separate static UI and is **not** the Flask app; its direct browser writes must not be used for real transactions. Deploy the authenticated Flask app as the management portal. It uses environment-configured website logins rather than individual hashed user accounts. Add CSRF protection, per-user authentication, audit logging, backups, and least-privilege ORDS credentials before any real institutional deployment. ORDS AutoREST endpoints and authentication have not been tested against your personal APEX workspace yet, so the deployed website is not confirmed connected until we test it with your workspace configuration.

## 7. Deployment status

The repository contains a Flask backend, but it is not deployed by GitHub Pages. After connecting a Render service, set the environment variables privately, then verify `GET /health` and test read operations, followed by an authorized issue/return test on sample equipment. Do not run SQL table-creation scripts again on the populated workspace.
