{\rtf1\ansi\ansicpg1252\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww12720\viewh7800\viewkind0
\pard\tx566\tx1133\tx1700\tx2267\tx2834\tx3401\tx3968\tx4535\tx5102\tx5669\tx6236\tx6803\pardirnatural\partightenfactor0

\f0\fs24 \cf0 from flask import Flask, render_template, request, redirect, url_for, session, flash\
from datetime import datetime, date\
import sqlite3\
import os\
import logging\
import traceback\
\
app = Flask(__name__)\
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")  # in Render als Env Var setzen!\
DB_FILE = os.getenv("DB_FILE", "umsatz.db")                # in Render optional z. B. /opt/render/project/src/umsatz.db\
\
# ------------------ Logging etwas sprechender ------------------\
logging.basicConfig(level=logging.INFO)\
\
# ------------------ DB-Initialisierung -------------------------\
def init_db():\
    # Erstellt DB-Datei und Tabelle bei Bedarf\
    conn = sqlite3.connect(DB_FILE)\
    c = conn.cursor()\
    c.execute("""\
        CREATE TABLE IF NOT EXISTS umsatz (\
            id INTEGER PRIMARY KEY AUTOINCREMENT,\
            restaurant TEXT,\
            datum TEXT,\
            total REAL,\
            bar REAL,\
            kartenterminal REAL,\
            twint REAL,\
            amex REAL,\
            debitoren REAL,\
            eatch REAL,\
            reka REAL,\
            sonstige REAL,\
            user TEXT\
        )\
    """)\
    c.execute("CREATE INDEX IF NOT EXISTS idx_umsatz_rest_datum ON umsatz(restaurant, datum)")\
    conn.commit()\
    conn.close()\
\
init_db()\
\
# ------------------ Benutzer -----------------------------------\
USERS = \{\
    "admin_sebastiano": \{"password": "admin!2025", "role": "super", "restaurant": None\},\
    "La_Vita":   \{"password": "1234", "role": "input", "restaurant": "Restaurant La Vita"\},\
    "La_Gioia":  \{"password": "1234", "role": "input", "restaurant": "Restaurant La Gioia"\},\
    "Celina":    \{"password": "1234", "role": "input", "restaurant": "Restaurant Celina"\},\
    "Lido":      \{"password": "1234", "role": "input", "restaurant": "Restaurant Lido"\},\
    "Da_Vito":   \{"password": "1234", "role": "input", "restaurant": "Restaurant da Vito"\},\
\}\
\
RESTAURANTS = [\
    "Restaurant La Vita",\
    "Restaurant La Gioia",\
    "Restaurant Celina",\
    "Restaurant Lido",\
    "Restaurant da Vito"\
]\
\
# ------------------ Helpers: Datum ------------------------------\
import pandas as pd\
import calendar\
\
def _parse_user_date(s: str | None):\
    """Versucht ISO (YYYY-MM-DD) und dd.mm.yyyy; gibt pandas.Timestamp oder NaT."""\
    if not s or not str(s).strip():\
        return pd.NaT\
    s = str(s).strip()\
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):\
        try:\
            return pd.to_datetime(s, format=fmt)\
        except Exception:\
            pass\
    return pd.to_datetime(s, dayfirst=True, errors="coerce")\
\
def _month_range(year: int, month: int):\
    last_day = calendar.monthrange(year, month)[1]\
    start = pd.Timestamp(year=year, month=month, day=1)\
    end   = pd.Timestamp(year=year, month=month, day=last_day)\
    return start, end\
\
# ------------------ Auth-Routen --------------------------------\
@app.route("/", methods=["GET", "POST"])\
def login():\
    if request.method == "POST":\
        u = request.form.get("username")\
        p = request.form.get("password")\
        if u in USERS and USERS[u]["password"] == p:\
            session.clear()\
            session["logged_in"] = True\
            session["user"] = u\
            session["role"] = USERS[u]["role"]\
            session["restaurant"] = USERS[u]["restaurant"]\
            return redirect(url_for("dashboard"))\
        return render_template("login.html", error="Falscher Login")\
    return render_template("login.html")\
\
@app.route("/logout")\
def logout():\
    session.clear()\
    return redirect(url_for("login"))\
\
# ------------------ Formular -----------------------------------\
@app.route("/form", methods=["GET", "POST"])\
def form():\
    if not session.get("logged_in"):\
        return redirect(url_for("login"))\
\
    role = session.get("role")\
    user = session.get("user")\
    rfix = session.get("restaurant")\
    restaurants = RESTAURANTS if role == "super" else [rfix]\
\
    if request.method == "POST":\
        rest = request.form.get("restaurant") or rfix\
        now = datetime.now()\
        datum = now.strftime("%d.%m.%Y")\
\
        # Summen\
        def _f(name):\
            try:\
                return float(request.form.get(name) or 0)\
            except Exception:\
                return 0.0\
\
        total = _f("total")\
        bar = _f("bar")\
        kart = _f("kartenterminal")\
        twint = _f("twint")\
        amex = _f("amex")\
        deb = _f("debitoren")\
        eatch = _f("eatch")\
        reka = _f("reka")\
        sonst = _f("sonstige")\
\
        # Validierung Zahlarten = Total (mit kleiner Toleranz)\
        if round(bar+kart+twint+amex+deb+eatch+reka+sonst, 2) != round(total, 2):\
            flash("Fehler: Zahlungsarten entsprechen nicht dem Total.", "danger")\
            return redirect(url_for("form"))\
\
        conn = sqlite3.connect(DB_FILE)\
        c = conn.cursor()\
        c.execute("""\
            INSERT INTO umsatz (restaurant, datum, total, bar, kartenterminal, twint, amex, debitoren, eatch, reka, sonstige, user)\
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)\
        """, (rest, datum, total, bar, kart, twint, amex, deb, eatch, reka, sonst, user))\
        conn.commit()\
        conn.close()\
\
        flash("Eintrag gespeichert.", "success")\
        return redirect(url_for("dashboard"))\
\
    return render_template("form.html", restaurants=restaurants, user=user)\
\
# ------------------ Dashboard -----------------------------------\
@app.route("/dashboard")\
def dashboard():\
    if not session.get("logged_in"):\
        return redirect(url_for("login"))\
\
    user = session.get("user")\
    role = session.get("role")\
    rfix = session.get("restaurant")\
\
    # Filter aus Query\
    filter_typ = request.args.get("filter") or "monat"\
    jahr_str   = request.args.get("jahr")   or datetime.now().strftime("%Y")\
    monat_str  = request.args.get("monat")  or datetime.now().strftime("%m")\
\
    try:\
        jahr_int = int(jahr_str)\
    except Exception:\
        jahr_int = datetime.now().year\
        jahr_str = str(jahr_int)\
\
    try:\
        monat_int = int(monat_str)\
    except Exception:\
        monat_int = datetime.now().month\
        monat_str = f"\{monat_int:02d\}"\
\
    # Start/End bestimmen (als Timestamp, nicht String)\
    if filter_typ == "monat":\
        start_dt, end_dt = _month_range(jahr_int, monat_int)\
    elif filter_typ == "jahres":\
        start_dt = pd.Timestamp(year=jahr_int, month=1, day=1)\
        end_dt   = pd.Timestamp(year=jahr_int, month=12, day=31)\
    elif filter_typ == "quartal1":\
        start_dt = pd.Timestamp(jahr_int, 1, 1);  end_dt = pd.Timestamp(jahr_int, 3, 31)\
    elif filter_typ == "quartal2":\
        start_dt = pd.Timestamp(jahr_int, 4, 1);  end_dt = pd.Timestamp(jahr_int, 6, 30)\
    elif filter_typ == "quartal3":\
        start_dt = pd.Timestamp(jahr_int, 7, 1);  end_dt = pd.Timestamp(jahr_int, 9, 30)\
    elif filter_typ == "quartal4":\
        start_dt = pd.Timestamp(jahr_int,10, 1);  end_dt = pd.Timestamp(jahr_int,12, 31)\
    elif filter_typ == "custom":\
        start_dt = _parse_user_date(request.args.get("start"))\
        end_dt   = _parse_user_date(request.args.get("end"))\
        if pd.isna(start_dt) or pd.isna(end_dt) or end_dt < start_dt:\
            # Fallback: aktueller Monat\
            start_dt, end_dt = _month_range(jahr_int, monat_int)\
            filter_typ = "monat"\
    else:\
        start_dt, end_dt = _month_range(jahr_int, monat_int)\
        filter_typ = "monat"\
\
    # DB lesen\
    conn = sqlite3.connect(DB_FILE)\
    df = pd.read_sql_query("SELECT * FROM umsatz", conn)\
    conn.close()\
\
    # Datumsspalte robust parsen\
    df["Datum"] = pd.to_datetime(df["datum"], format="%d.%m.%Y", errors="coerce")\
    df = df.dropna(subset=["Datum"])\
\
    # F\'fcr Darstellung Strings f\'fcr Start/End (dd.mm.yyyy)\
    start_str = start_dt.strftime("%d.%m.%Y")\
    end_str   = end_dt.strftime("%d.%m.%Y")\
\
    # Auswertungen\
    stats = []\
    last_entries = []\
    monthly = \{r: [0.0]*12 for r in RESTAURANTS\}\
\
    # Welche Restaurants zeigen?\
    restaurants_to_show = RESTAURANTS if role == "super" else [rfix]\
\
    for r in restaurants_to_show:\
        df_r = df[df["restaurant"] == r]\
\
        # Range-Summe\
        dfF = df_r[df_r["Datum"].between(start_dt, end_dt, inclusive="both")]\
        total_summe = round(float(dfF["total"].sum()), 2) if not dfF.empty else 0.0\
        stats.append([r, total_summe])\
\
        # letzter Eintrag\
        if not df_r.empty:\
            l = df_r.sort_values("Datum", ascending=False).iloc[0]\
            last_entries.append((r, l["datum"], float(l["total"])))\
        else:\
            last_entries.append((r, "-", 0.0))\
\
        # Monatsentwicklung ausgew\'e4hltes Jahr\
        for m in range(1, 13):\
            st, en = _month_range(jahr_int, m)\
            sub = df_r[df_r["Datum"].between(st, en, inclusive="both")]\
            monthly[r][m-1] = round(float(sub["total"].sum()), 2) if not sub.empty else 0.0\
\
    gesamt = round(sum(row[1] for row in stats), 2)\
    jahresliste = [str(y) for y in range(2023, 2031)]\
\
    app.logger.info("FILTER=%s | jahr=%s | monat=%s | Zeitraum %s..%s", filter_typ, jahr_str, monat_str, start_dt, end_dt)\
\
    return render_template(\
        "dashboard.html",\
        stats=stats,\
        gesamt=gesamt,\
        year=jahr_str,\
        filter=filter_typ,\
        jahre=jahresliste,\
        jahr_selected=jahr_str,\
        start=start_str,\
        end=end_str,\
        user=user,\
        last_entries=last_entries,\
        monthly=monthly\
    )\
\
# ------------------ Health & Fehlerseiten ----------------------\
@app.route("/health")\
def health():\
    return \{"status": "ok"\}, 200\
\
@app.errorhandler(500)\
def handle_500(e):\
    app.logger.error("Unhandled 500: %s\\n%s", e, traceback.format_exc())\
    return render_template("login.html", error="Interner Fehler. Bitte erneut versuchen."), 500\
\
# ------------------ Dev Start ----------------------------------\
if __name__ == "__main__":\
    app.run(debug=True)\
}