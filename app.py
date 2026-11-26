import os
import re
from datetime import date, datetime
from functools import wraps
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "unsafe-dev-key-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=3600,
)

# ORDS AutoREST resources for the exact table names in Website.sql.
# These are the ORDS module paths provided by the workspace owner.
# They are different from Oracle AutoREST's default UEB_* table paths.
TABLES = {
    "categories": "categories/",
    "equipment": "equipment/",
    "borrowers": "borrowers/",
    "loans": "borrowing-records/",
}

# Website-friendly field names mapped to the actual Oracle column names.
# The uploaded schema uses BORROWERID, EQUIPMENTID, ISSUE_DATE? No: its
# identifiers are unseparated (BORROWERID, EQUIPMENTID, ISSUEDATE, etc.).
COLUMN_NAMES = {
    "categories": {"category_id": "CATEGORYID", "category_name": "CATEGORYNAME", "description": "DESCRIPTION"},
    "equipment": {"equipment_id": "EQUIPMENTID", "category_id": "CATEGORYID", "equipment_name": "EQUIPMENTNAME", "model": "MODEL", "serial_number": "SERIALNUMBER", "purchase_date": "PURCHASEDATE", "condition": "CONDITION", "status": "STATUS"},
    "borrowers": {"borrower_id": "BORROWERID", "name": "NAME", "email": "EMAIL", "phone": "PHONE", "borrower_type": "BORROWERTYPE", "department": "DEPARTMENT", "role": "ROLE"},
    "loans": {"borrow_id": "BORROWID", "equipment_id": "EQUIPMENTID", "borrower_id": "BORROWERID", "issue_date": "ISSUEDATE", "due_date": "DUEDATE", "return_date": "RETURNDATE", "return_condition": "RETURNCONDITION", "loan_status": "LOANSTATUS", "remarks": "REMARKS"},
}


def normalized_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def normalize_record(table, record):
    """Convert ORDS column names (e.g. borrowerid) to template names."""
    reverse = {normalized_key(column): field for field, column in COLUMN_NAMES[table].items()}
    result = {}
    for key, value in record.items():
        if normalized_key(key) == "links":
            continue
        field = reverse.get(normalized_key(key))
        if field:
            result[field] = value
    return result


def oracle_payload(table, form_values):
    """Translate website field names to the exact Oracle column identifiers."""
    mapping = COLUMN_NAMES[table]
    return {mapping[key]: value for key, value in form_values.items() if key in mapping and value is not None}


class OrdsError(RuntimeError):
    pass


class OrdsClient:
    def __init__(self):
        self.base = os.getenv("ORDS_BASE_URL", "").strip()
        self.token = os.getenv("ORDS_BEARER_TOKEN", "").strip()
        self.username = os.getenv("ORDS_USERNAME", "").strip()
        self.password = os.getenv("ORDS_PASSWORD", "").strip()
        if not self.base:
            raise OrdsError("ORDS_BASE_URL is not configured.")
        if not self.base.endswith("/"):
            self.base += "/"
        # Public GET endpoints can be read without a token; protected writes must
        # never be sent by this backend without its own ORDS credentials.

    def call(self, method, resource, payload=None, params=None):
        if method.upper() not in ("GET", "HEAD") and not (self.token or (self.username and self.password)):
            raise OrdsError("ORDS write credentials are not configured. Configure authenticated ORDS access on the server.")
        headers = {"Accept": "application/json"}
        auth = None
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            auth = (self.username, self.password)
        if payload is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = requests.request(
                method, urljoin(self.base, resource), json=payload, params=params,
                headers=headers, auth=auth, timeout=20
            )
            if response.status_code >= 400:
                raise OrdsError(f"ORDS returned HTTP {response.status_code}: {response.text[:500]}")
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return {}
        except requests.RequestException as exc:
            raise OrdsError(f"Could not reach Oracle ORDS: {exc}") from exc

    def list(self, table):
        data = self.call("GET", TABLES[table])
        rows = data.get("items", []) if isinstance(data, dict) else []
        return [normalize_record(table, row) for row in rows]

    def get(self, table, row_id):
        data = self.call("GET", f"{TABLES[table]}{row_id}")
        return normalize_record(table, data if isinstance(data, dict) else {})

    def create(self, table, payload):
        return self.call("POST", TABLES[table], oracle_payload(table, payload))

    def update(self, table, row_id, payload):
        return self.call("PUT", f"{TABLES[table]}{row_id}", oracle_payload(table, payload))

    def delete(self, table, row_id):
        return self.call("DELETE", f"{TABLES[table]}{row_id}")


def db():
    return OrdsClient()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to perform that action.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.errorhandler(OrdsError)
def handle_ords_error(error):
    flash(str(error), "danger")
    return redirect(request.referrer or url_for("dashboard"))


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        supplied_user = request.form.get("username", "")
        supplied_password = request.form.get("password", "")
        for role in ("admin", "staff", "viewer"):
            configured_user = os.getenv(f"{role.upper()}_USERNAME", "")
            configured_password = os.getenv(f"{role.upper()}_PASSWORD", "")
            if configured_user and configured_password and supplied_user == configured_user and supplied_password == configured_password:
                session.clear()
                session["user"] = configured_user
                session["role"] = role
                session.permanent = True
                return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard():
    client = db()
    equipment = client.list("equipment")
    loans = client.list("loans")
    today = date.today()
    available = sum(1 for e in equipment if str(e.get("status", "")).upper() == "AVAILABLE")
    borrowed = sum(1 for e in equipment if str(e.get("status", "")).upper() == "BORROWED")
    overdue = sum(1 for loan in loans if not loan.get("return_date") and loan.get("due_date") and date.fromisoformat(str(loan["due_date"])[:10]) < today)
    return render_template("dashboard.html", total=len(equipment), available=available,
                           borrowed=borrowed, overdue=overdue, recent=loans[:8])


@app.get("/<table>")
@login_required
def list_page(table):
    if table not in TABLES:
        return "Not found", 404
    return render_template("list.html", table=table, items=db().list(table))


@app.route("/<table>/new", methods=["GET", "POST"])
@roles_required("admin", "staff")
def create_page(table):
    if table not in ("categories", "equipment", "borrowers"):
        return "Not found", 404
    if request.method == "POST":
        values = {key: value.strip() for key, value in request.form.items() if value.strip()}
        db().create(table, values)
        flash("Record created.", "success")
        return redirect(url_for("list_page", table=table))
    return render_template("edit.html", table=table, item={})


@app.route("/<table>/<int:row_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "staff")
def edit_page(table, row_id):
    if table not in ("categories", "equipment", "borrowers"):
        return "Not found", 404
    client = db()
    if request.method == "POST":
        values = {key: value.strip() for key, value in request.form.items() if value.strip()}
        client.update(table, row_id, values)
        flash("Record updated.", "success")
        return redirect(url_for("list_page", table=table))
    return render_template("edit.html", table=table, item=client.get(table, row_id))


@app.post("/<table>/<int:row_id>/delete")
@roles_required("admin")
def delete_page(table, row_id):
    if table not in ("categories", "equipment", "borrowers"):
        return "Not found", 404
    db().delete(table, row_id)
    flash("Record deleted.", "success")
    return redirect(url_for("list_page", table=table))


@app.route("/issue", methods=["GET", "POST"])
@roles_required("admin", "staff")
def issue():
    client = db()
    if request.method == "POST":
        equipment_id = int(request.form["equipment_id"])
        borrower_id = int(request.form["borrower_id"])
        issue_date = request.form.get("issue_date") or date.today().isoformat()
        due_date = request.form["due_date"]
        if date.fromisoformat(due_date) < date.fromisoformat(issue_date):
            flash("Due date cannot be earlier than issue date.", "danger")
            return redirect(url_for("issue"))
        equipment = client.get("equipment", equipment_id)
        if str(equipment.get("status", "")).upper() != "AVAILABLE" or str(equipment.get("condition", "")).upper() != "GOOD":
            flash("Only equipment with Status = Available and Condition = Good can be issued.", "danger")
            return redirect(url_for("issue"))
        client.create("loans", {
            "equipment_id": equipment_id, "borrower_id": borrower_id,
            "issue_date": issue_date, "due_date": due_date, "loan_status": "Borrowed"
        })
        flash("Equipment issued successfully.", "success")
        return redirect(url_for("dashboard"))
    equipment = client.list("equipment")
    borrowers = client.list("borrowers")
    return render_template("issue.html", equipment=equipment, borrowers=borrowers, today=date.today().isoformat())


@app.route("/return", methods=["GET", "POST"])
@roles_required("admin", "staff")
def return_equipment():
    client = db()
    active = [loan for loan in client.list("loans") if str(loan.get("loan_status", "")).lower() in ("borrowed", "missing") and not loan.get("return_date")]
    if request.method == "POST":
        borrow_id = int(request.form["borrow_id"])
        loan = client.get("loans", borrow_id)
        if loan.get("return_date") or str(loan.get("loan_status", "")).lower() != "borrowed":
            flash("This loan is not currently eligible for return.", "warning")
            return redirect(url_for("return_equipment"))
        condition = request.form["return_condition"].title()
        values = {
            "equipment_id": loan.get("equipment_id"),
            "borrower_id": loan.get("borrower_id"),
            "issue_date": str(loan.get("issue_date", ""))[:10],
            "due_date": str(loan.get("due_date", ""))[:10],
            "return_date": date.today().isoformat(),
            "return_condition": condition,
            "loan_status": "Returned",
            "remarks": request.form.get("remarks", "").strip(),
        }
        client.update("loans", borrow_id, values)
        flash("Return recorded. Your Oracle trigger updates the equipment condition and status.", "success")
        return redirect(url_for("return_equipment"))
    return render_template("return.html", loans=active)


@app.get("/reports/overdue")
@login_required
def overdue_report():
    today = date.today()
    loans = db().list("loans")
    items = [loan for loan in loans if not loan.get("return_date") and loan.get("due_date") and date.fromisoformat(str(loan["due_date"])[:10]) < today]
    return render_template("report.html", items=items, today=today.isoformat())


@app.get("/admin")
@roles_required("admin")
def administration():
    return render_template("admin.html")


if __name__ == "__main__":
    app.run(debug=True)
