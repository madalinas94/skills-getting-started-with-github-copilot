"""Date demonstrative: un an de activitate pentru o firmă de accesorii IT."""

import calendar
import random
import sqlite3
from datetime import date

from .calc import shift_month

PRODUCTS = [
    ("Mouse wireless Logitech M185", 89),
    ("Tastatură mecanică Redragon", 249),
    ("Căști gaming HyperX Cloud", 399),
    ("Webcam Full HD 1080p", 219),
    ("Hub USB-C 7 în 1", 179),
    ("SSD extern 1TB Samsung", 459),
    ("Încărcător GaN 65W", 159),
    ("Cablu HDMI 2.1 2m", 49),
    ("Mousepad XXL RGB", 99),
    ("Suport laptop aluminiu", 139),
    ("Stick USB 128GB", 69),
    ("Boxe Bluetooth JBL Go", 189),
]

EMPLOYEES = [
    # nume, rol, angajat cu câte luni în urmă, [(luni în urmă, brut)]
    ("Andrei Popescu", "Responsabil vânzări", 30, [(30, 6200), (7, 6900)]),
    ("Ioana Marin", "Vânzări online", 20, [(20, 5200), (3, 5800)]),
    ("Mihai Dumitru", "Depozit și livrări", 18, [(18, 4600)]),
    ("Elena Stan", "Suport clienți", 14, [(14, 4800), (5, 5100)]),
    ("Radu Ionescu", "Achiziții", 26, [(26, 6000)]),
    ("Cristina Georgescu", "Marketing", 4, [(4, 5500)]),
]

SEASON = {1: 0.85, 2: 0.82, 3: 0.92, 4: 0.95, 5: 0.97, 6: 0.93,
          7: 0.9, 8: 0.96, 9: 1.04, 10: 1.12, 11: 1.35, 12: 1.28}


def month_start(ym: str) -> str:
    return f"{ym}-01"


def load_demo_data(conn: sqlite3.Connection, today: date | None = None) -> None:
    """Șterge datele existente și încarcă 13 luni de activitate fictivă."""
    today = today or date.today()
    rng = random.Random(2026)
    this_month = today.strftime("%Y-%m")

    for table in ("salary_history", "employees", "sales", "expenses"):
        conn.execute(f"DELETE FROM {table}")

    for name, role, hired_ago, salaries in EMPLOYEES:
        hire = month_start(shift_month(this_month, -hired_ago))
        cursor = conn.execute(
            "INSERT INTO employees(name, role, hire_date) VALUES (?, ?, ?)", (name, role, hire)
        )
        for months_ago, gross in salaries:
            note = "Salariu inițial" if months_ago == hired_ago else "Mărire salariu"
            conn.execute(
                "INSERT INTO salary_history(employee_id, gross, effective_from, note) "
                "VALUES (?, ?, ?, ?)",
                (cursor.lastrowid, gross, month_start(shift_month(this_month, -months_ago)), note),
            )

    for offset in range(-12, 1):
        ym = shift_month(this_month, offset)
        year, month = (int(part) for part in ym.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        if ym == this_month:
            last_day = today.day
        growth = 1 + (offset + 12) * 0.012
        factor = SEASON[month] * growth
        revenue = 0.0

        for day in range(1, last_day + 1):
            current = date(year, month, day)
            if current.weekday() == 6:
                continue
            if current.weekday() == 5:
                amount = round(rng.uniform(4200, 6800) * factor, 2)
                conn.execute(
                    "INSERT INTO sales(date, description, amount) VALUES (?, ?, ?)",
                    (current.isoformat(), "Vânzări magazin — total zi", amount),
                )
                revenue += amount
                continue
            for _ in range(rng.randint(9, 15)):
                product, price = rng.choices(
                    PRODUCTS, weights=[9, 5, 4, 4, 6, 3, 6, 8, 5, 4, 7, 4]
                )[0]
                quantity = rng.choices([1, 2, 3, 5, 10], weights=[50, 22, 12, 9, 7])[0]
                amount = round(price * quantity * rng.uniform(0.95, 1.0) * factor, 2)
                conn.execute(
                    "INSERT INTO sales(date, description, product, quantity, amount) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (current.isoformat(), f"Comandă {product}", product, quantity, amount),
                )
                revenue += amount

        def expense(day: int, category: str, description: str, amount: float) -> None:
            if day <= last_day:
                conn.execute(
                    "INSERT INTO expenses(date, category, description, amount) "
                    "VALUES (?, ?, ?, ?)",
                    (date(year, month, day).isoformat(), category, description, round(amount, 2)),
                )

        winter = month in (11, 12, 1, 2)
        busy = month in (11, 12)

        # Cheltuieli fixe, în fiecare lună
        expense(3, "Chirie", "Chirie spațiu comercial și depozit", 6500)
        expense(5, "Contabilitate", "Servicii contabilitate", 1200)
        expense(6, "Internet și telefonie", "Abonament internet fibră și telefoane mobile", 460)
        expense(7, "Software și abonamente", "Program facturare, Microsoft 365, hosting site",
                rng.uniform(620, 700))
        expense(9, "Asigurări", "Asigurare marfă, spațiu și auto", 380)
        expense(11, "Medicina muncii și SSM", "Contract SSM și medicina muncii", 180)

        # Cheltuieli variabile, legate de activitate
        expense(8, "Marfă / furnizori", "Factură distribuitor accesorii", revenue * 0.27)
        expense(20, "Marfă / furnizori", "Factură distribuitor periferice", revenue * 0.22)
        expense(12, "Utilități", "Curent, apă, gaz", rng.uniform(1000, 1400) if winter
                else rng.uniform(650, 900))
        transport = rng.uniform(1400, 2200) * (1.6 if offset == 0 else 1)
        expense(15, "Transport", "Curierat livrări clienți", transport)
        expense(16, "Combustibil și auto", "Combustibil și întreținere mașină firmă",
                rng.uniform(1100, 1700))
        expense(10, "Marketing", "Reclame online și promovare",
                rng.uniform(1800, 2800) * (1.8 if busy else 1))
        expense(28, "Comisioane bancare și POS", "Comisioane POS și transferuri bancare",
                revenue * 0.006 + 85)
        expense(18, "Ambalaje și consumabile", "Cutii, folie, etichete pentru colete",
                revenue * 0.007)
        expense(22, "Protocol și deplasări", "Întâlniri furnizori și deplasări",
                rng.uniform(250, 800))
        expense(25, "Altele", "Cheltuieli diverse", rng.uniform(150, 450))

        # Cheltuieli ocazionale
        if rng.random() < 0.3:
            expense(14, "Echipamente IT și mobilier", "Laptop, imprimantă sau mobilier birou",
                    rng.uniform(1800, 5500))
        if rng.random() < 0.45:
            expense(19, "Mentenanță și reparații", "Reparații spațiu și service echipamente",
                    rng.uniform(300, 1400))
        if rng.random() < 0.25:
            expense(21, "Training și cursuri", "Curs vânzări / marketing online",
                    rng.uniform(700, 1900))
        if month in (3, 9):
            expense(26, "Taxe locale și autorizații", "Impozit clădire și auto (semestrial)", 1850)
        if month == 1:
            expense(13, "Taxe locale și autorizații", "Taxă firmă și autorizație funcționare", 650)
            expense(17, "Medicina muncii și SSM", "Control medical anual angajați", 900)
