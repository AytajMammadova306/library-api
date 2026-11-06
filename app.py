import os
import re
import sqlite3
from datetime import date, timedelta
from routes.loans import loans_bp
from flask import Flask, jsonify, request

app = Flask(__name__)

app.register_blueprint(loans_bp)

def init_db():
    conn = sqlite3.connect("library.db")
    conn.executescript(
        """
        DROP TABLE IF EXISTS books;
        DROP TABLE IF EXISTS members;
        DROP TABLE IF EXISTS loans;
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, author TEXT, isbn TEXT, available INTEGER DEFAULT 1
        );
        CREATE TABLE members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT UNIQUE, type TEXT
        );
        CREATE TABLE loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER, member_id INTEGER, due_date TEXT,
            returned INTEGER DEFAULT 0, fine REAL DEFAULT 0,
            fine_paid INTEGER DEFAULT 0, renewals INTEGER DEFAULT 0,
            checked_out TEXT
        );
        """
    )
    books = [
        ("Clean Code", "Robert C. Martin", "9780132350884", 1),
        ("The Pragmatic Programmer", "Andrew Hunt", "9780135957059", 1),
        ("Design Patterns", "Erich Gamma", "9780201633610", 1),
        ("Refactoring", "Martin Fowler", "9780134757599", 1),
        ("Code Complete", "Steve McConnell", "9780735619678", 0),
    ]
    conn.executemany("INSERT INTO books (title, author, isbn, available) VALUES (?, ?, ?, ?)", books)
    members = [
        ("Sam Rivera", "sam@campus.edu", "student"),
        ("Dr. Noor Aziz", "noor@campus.edu", "staff"),
        ("Alex Chen", "alex@campus.edu", "student"),
    ]
    conn.executemany("INSERT INTO members (name, email, type) VALUES (?, ?, ?)", members)
    today = date.today()
    conn.execute(
        "INSERT INTO loans (book_id, member_id, due_date, checked_out) VALUES (5, 3, ?, ?)",
        ((today - timedelta(days=5)).isoformat(), (today - timedelta(days=19)).isoformat()),
    )
    conn.commit()
    conn.close()


# ---------- helpers ----------


def check(value, kind):
    if kind == "email":
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value)) is not None
    elif kind == "isbn":
        digits = str(value).replace("-", "")
        return digits.isdigit() and len(digits) in (10, 13)
    elif kind == "date":
        try:
            date.fromisoformat(str(value))
            return True
        except ValueError:
            return False
    elif kind == "member_type":
        return value in ("student", "staff")
    return False





# ---------- books ----------


@app.route("/books", methods=["GET"])
def list_books():
    conn = sqlite3.connect("library.db")
    if request.args.get("available") == "true":
        rows = conn.execute("SELECT * FROM books WHERE available = 1").fetchall()
    else:
        rows = conn.execute("SELECT * FROM books").fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({"id": r[0], "title": r[1], "author": r[2], "isbn": r[3], "available": bool(r[4])})
    return jsonify(result)


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    conn = sqlite3.connect("library.db")
    r = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    if r is None:
        return jsonify({"error": "book not found"}), 404
    return jsonify({"id": r[0], "title": r[1], "author": r[2], "isbn": r[3], "available": bool(r[4])})


@app.route("/books", methods=["POST"])
def create_book():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("author"):
        return jsonify({"error": "title and author are required"}), 400
    if not check(data.get("isbn"), "isbn"):
        return jsonify({"error": "invalid isbn"}), 400
    conn = sqlite3.connect("library.db")
    cur = conn.execute(
        "INSERT INTO books (title, author, isbn, available) VALUES (?, ?, ?, 1)",
        (data["title"], data["author"], data["isbn"]),
    )
    conn.commit()
    r = conn.execute("SELECT * FROM books WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify({"id": r[0], "title": r[1], "author": r[2], "isbn": r[3], "available": bool(r[4])}), 201


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    conn = sqlite3.connect("library.db")
    r = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if r is None:
        conn.close()
        return jsonify({"error": "book not found"}), 404
    if r[4] == 0:
        conn.close()
        return jsonify({"error": "book is on loan"}), 409
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    return "", 204


# ---------- members ----------


@app.route("/members", methods=["GET"])
def list_members():
    conn = sqlite3.connect("library.db")
    rows = conn.execute("SELECT * FROM members").fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({"id": r[0], "name": r[1], "email": r[2], "type": r[3]})
    return jsonify(result)


@app.route("/members/<int:member_id>", methods=["GET"])
def get_member(member_id):
    conn = sqlite3.connect("library.db")
    r = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    conn.close()
    if r is None:
        return jsonify({"error": "member not found"}), 404
    return jsonify({"id": r[0], "name": r[1], "email": r[2], "type": r[3]})


@app.route("/members", methods=["POST"])
def create_member():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if not check(data.get("email"), "email"):
        return jsonify({"error": "invalid email"}), 400
    member_type = data.get("type", "student")
    if not check(member_type, "member_type"):
        return jsonify({"error": "type must be student or staff"}), 400
    conn = sqlite3.connect("library.db")
    existing = conn.execute("SELECT * FROM members WHERE email = ?", (data["email"],)).fetchone()
    if existing is not None:
        conn.close()
        return jsonify({"error": "email already registered"}), 409
    cur = conn.execute(
        "INSERT INTO members (name, email, type) VALUES (?, ?, ?)",
        (data["name"], data["email"], member_type),
    )
    conn.commit()
    r = conn.execute("SELECT * FROM members WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify({"id": r[0], "name": r[1], "email": r[2], "type": r[3]}), 201

@app.route("/members/<int:member_id>", methods=["DELETE"])
def delete_member(member_id):
    conn = sqlite3.connect("library.db")
    r = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if r is None:
        conn.close()
        return jsonify({"error": "member not found"}), 404
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    return "", 204


@app.route("/members/<int:member_id>/loans", methods=["GET"])
def member_loans(member_id):
    conn = sqlite3.connect("library.db")
    m = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if m is None:
        conn.close()
        return jsonify({"error": "member not found"}), 404
    rows = conn.execute("SELECT * FROM loans WHERE member_id = ?", (member_id,)).fetchall()
    conn.close()
    owed = 0
    open_loans = 0
    loans = []
    for loan in rows:
        if loan[4] == 0:
            open_loans += 1
            days_late = (date.today() - date.fromisoformat(loan[3])).days
            if days_late > 0:
                owed += days_late * 0.5
        elif loan[6] == 0:
            owed += loan[5]
        loans.append(
            {
                "id": loan[0],
                "book_id": loan[1],
                "due_date": loan[3],
                "returned": bool(loan[4]),
                "fine": money(loan[5]),
                "fine_paid": bool(loan[6]),
            }
        )
    if m[3] == "staff":
        remaining = 5 - open_loans
    else:
        remaining = 3 - open_loans
    return jsonify({"loans": loans, "total_owed": money(owed), "loans_remaining": remaining})



# ---------- reports ----------


@app.route("/reports/overdue", methods=["GET"])
def report_overdue():
    conn = sqlite3.connect("library.db")
    rows = conn.execute(
        """
        SELECT loans.id, books.title, members.name, loans.due_date
        FROM loans
        JOIN books ON books.id = loans.book_id
        JOIN members ON members.id = loans.member_id
        WHERE loans.returned = 0
        """
    ).fetchall()
    conn.close()
    items = []
    total = 0
    for r in rows:
        days_late = (date.today() - date.fromisoformat(r[3])).days
        if days_late > 0:
            fine = days_late * 0.5
            total += fine
            items.append(
                {"loan_id": r[0], "title": r[1], "member": r[2], "days_late": days_late, "fine": money(fine)}
            )
    return jsonify({"items": items, "total_fines": money(total)})


@app.route("/reports/summary", methods=["GET"])
def report_summary():
    conn = sqlite3.connect("library.db")
    total_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    rows = conn.execute("SELECT * FROM loans").fetchall()
    conn.close()
    on_loan = 0
    outstanding = 0
    for loan in rows:
        if loan[4] == 0:
            on_loan += 1
            days_late = (date.today() - date.fromisoformat(loan[3])).days
            outstanding += max(0, days_late) * 0.50
        elif loan[6] == 0:
            outstanding += loan[5]
    return jsonify({"total_books": total_books, "on_loan": on_loan, "fines_outstanding": money(outstanding)})


if not os.path.exists("library.db"):
    init_db()
