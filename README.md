# University Equipment Borrowing & Return Management System

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

The Flask app talks to Oracle through ORDS REST endpoints. It uses the actual no-underscore Oracle column names in JSON requests and normalizes ORDS response field names for the website templates. The expected AutoREST resource paths are:

- `<ORDS_BASE_URL>/ueb_categories/`
- `<ORDS_BASE_URL>/ueb_equipment/`
- `<ORDS_BASE_URL>/ueb_borrowers/`
- `<ORDS_BASE_URL>/ueb_borrowing_records/`

You must enable REST access for these tables in your Oracle APEX/ORDS workspace and configure authentication that your workspace supports. The exact ORDS URL and authentication method depend on your workspace. Do not assume the endpoint is working until you test it.

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

This is a student-project starter, not a security-audited production system. It uses environment-configured website logins rather than individual hashed user accounts. Add CSRF protection, per-user authentication, audit logging, backups, and least-privilege ORDS credentials before any real institutional deployment. ORDS AutoREST endpoints and authentication have not been tested against your personal APEX workspace yet, so the deployed website is not confirmed connected until we test it with your workspace configuration.
