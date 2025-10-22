
import os, io, sqlite3, hashlib
from datetime import datetime
from flask import Flask, render_template, request, jsonify, url_for, redirect
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

DB_PATH = os.environ.get("DB_PATH", "/data/aga.db")  # Use Render Disk
CERT_SALT = os.environ.get("CERT_SALT", "change-me")

app = Flask(__name__, template_folder="templates", static_folder="static")

# --------------- DB ---------------
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cert TEXT UNIQUE,
        hash TEXT,
        name TEXT,
        email TEXT,
        service TEXT,
        title TEXT,
        grade TEXT,
        sub_centering TEXT,
        sub_corners TEXT,
        sub_edges TEXT,
        sub_surface TEXT,
        created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pops(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT,
        grade TEXT,
        count INTEGER
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registry(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cert TEXT,
        display_name TEXT,
        note TEXT,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# --------------- Utils ---------------
def make_cert():
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rand = os.urandom(3).hex().upper()
    return f"AGA{stamp}{rand}"

def cert_hash(cert: str):
    h = hashlib.sha256((CERT_SALT + cert).encode()).hexdigest()[:10]
    return h

def normalize_key(title: str):
    t = (title or "").strip()
    return t if t else "Unknown"

def ensure_dirs():
    os.makedirs(os.path.join(app.static_folder, "qrcodes"), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, "labels"), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, "certs"), exist_ok=True)

def qr_png(text, out_path):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(out_path)

def label_png(cert, title, name, service, out_path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 900, 500
    bg = (245, 245, 245)
    red = (220, 38, 38)
    dark = (20, 25, 35)
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except:
        font_title = None; font_text = None; font_small = None

    d.rectangle([20,20,W-20,H-20], outline=red, width=6)
    d.text((40,40), "Authentic Grading Authority", fill=dark, font=font_title)
    d.text((40,110), f"Cert: {cert}", fill=dark, font=font_text)
    d.text((40,150), f"Card: {title or 'N/A'}", fill=dark, font=font_text)
    d.text((40,190), f"Customer: {name}", fill=dark, font=font_text)
    d.text((40,230), f"Service: {service}", fill=dark, font=font_text)
    d.text((40,420), "Place this label inside the package.", fill=dark, font=font_small)

    # QR
    try:
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(cert)
        qr.make(fit=True)
        qim = qr.make_image().convert("RGB").resize((200,200))
        im.paste(qim, (W-240, 60))
    except Exception:
        pass

    im.save(out_path, "PNG")

def cert_pdf(cert, title, grade, subs, created_at, out_path):
    # Generate a simple certificate PDF
    c = canvas.Canvas(out_path, pagesize=letter)
    width, height = letter
    c.setTitle(f"AGA Certificate {cert}")
    # Header
    c.setFillColorRGB(0.86, 0.15, 0.15)
    c.rect(0, height-80, width, 80, fill=1, stroke=0)
    c.setFillColorRGB(1,1,1)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(40, height-50, "Authentic Grading Authority")
    # Body
    c.setFillColorRGB(0,0,0)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, height-120, f"Certificate: {cert}")
    c.setFont("Helvetica", 14)
    c.drawString(40, height-150, f"Card: {title or 'N/A'}")
    c.drawString(40, height-170, f"Grade: {grade}")
    c.drawString(40, height-190, f"Subgrades: C {subs.get('centering','')} • Co {subs.get('corners','')} • E {subs.get('edges','')} • S {subs.get('surface','')}")
    c.drawString(40, height-210, f"Issued: {created_at}")
    # Footer QR
    qr_path = os.path.join(app.static_folder, "qrcodes", f"{cert}.png")
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width-180, 60, 120, 120, mask='auto')
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColorRGB(0.4,0.4,0.4)
    c.drawString(40, 40, "Verify this certificate by scanning the QR code or visiting the AGA website.")
    c.save()

def update_pop(conn, key, grade):
    cur = conn.cursor()
    cur.execute("SELECT id, count FROM pops WHERE key=? AND grade=?", (key, grade))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE pops SET count=? WHERE id=?", (row["count"]+1, row["id"]))
    else:
        cur.execute("INSERT INTO pops(key, grade, count) VALUES (?,?,?)", (key, grade, 1))
    conn.commit()

# --------------- Routes ---------------
@app.route("/")
def home():
    # stats + recent
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM orders")
    total = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as g FROM orders WHERE grade='Gem Mint 10'")
    gem10 = cur.fetchone()["g"]
    cur.execute("SELECT cert, title, grade, created_at FROM orders ORDER BY id DESC LIMIT 10")
    recent = cur.fetchall()
    conn.close()
    return render_template("index.html", total=total, gem10=gem10, recent=recent)

@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

@app.route("/submit")
def submit_view():
    # autofill via query params
    return render_template("submit.html", q=request.args)

@app.route("/lookup")
def lookup_view():
    return render_template("lookup.html")

@app.route("/registry")
def registry_view():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT r.display_name, r.note, r.created_at, o.cert, o.title, o.grade FROM registry r JOIN orders o ON r.cert=o.cert ORDER BY r.id DESC LIMIT 50")
    rows = cur.fetchall()
    conn.close()
    return render_template("registry.html", rows=rows)

@app.route("/pop-report")
def pop_report_view():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT key, grade, count FROM pops ORDER BY key, grade")
    rows = cur.fetchall()
    conn.close()
    return render_template("pop.html", rows=rows)

# -------- APIs --------
@app.route("/api/stats")
def api_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM orders")
    total = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as g FROM orders WHERE grade='Gem Mint 10'")
    gem10 = cur.fetchone()["g"]
    conn.close()
    return jsonify({"ok": True, "total": total, "gem10": gem10})

@app.route("/api/grade", methods=["POST"])
def api_grade():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "No image provided"}), 400
    file = request.files["image"]
    try:
        img = Image.open(io.BytesIO(file.read())).convert("RGB")
    except Exception:
        return jsonify({"ok": False, "error": "Invalid image"}), 400

    # Fast heuristic
    small = img.resize((256,256))
    edges = small.filter(ImageFilter.FIND_EDGES).convert("L")
    sharp_val = int(sum(edges.getdata()) / (256*256) / 10)
    sharp_val = max(70, min(99, sharp_val))
    if sharp_val > 92: grade = "Gem Mint 10"
    elif sharp_val > 88: grade = "Mint 9"
    elif sharp_val > 84: grade = "NM-MT 8"
    else: grade = "NM 7"

    return jsonify({"ok": True, "grade": grade,
        "subgrades": {"centering": str(sharp_val-2), "corners": str(sharp_val-3),
                      "edges": str(sharp_val-4), "surface": str(sharp_val-5)}})

@app.route("/api/order", methods=["POST"])
def api_order():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    service = (data.get("service") or "").strip()
    title = (data.get("title") or "").strip()
    grade = (data.get("grade") or "Pending").strip()
    subs = data.get("subgrades") or {}

    if not name or not email or not service:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400

    cnum = make_cert()
    chash = cert_hash(cnum)
    created = datetime.utcnow().isoformat()

    ensure_dirs()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders(cert,hash,name,email,service,title,grade,
        sub_centering,sub_corners,sub_edges,sub_surface,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (cnum, chash, name, email, service, title, grade,
          str(subs.get("centering","")), str(subs.get("corners","")),
          str(subs.get("edges","")), str(subs.get("surface","")), created))
    conn.commit()

    # URLs and assets
    cert_url = url_for("cert_page_hashed", cert=cnum, h=chash, _external=True)
    qr_path = os.path.join(app.static_folder, "qrcodes", f"{cnum}.png")
    label_path = os.path.join(app.static_folder, "labels", f"{cnum}.png")
    pdf_path = os.path.join(app.static_folder, "certs", f"{cnum}.pdf")

    qr_png(cert_url, qr_path)
    label_png(cnum, title, name, service, label_path)
    cert_pdf(cnum, title, grade, subs, created, pdf_path)

    # Pop update if final
    key = normalize_key(title)
    if grade and grade.lower() != "pending":
        cur = conn.cursor()
        cur.execute("SELECT id, count FROM pops WHERE key=? AND grade=?", (key, grade))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE pops SET count=? WHERE id=?", (row['count']+1, row['id']))
        else:
            cur.execute("INSERT INTO pops(key,grade,count) VALUES (?,?,?)",(key,grade,1))
        conn.commit()
    conn.close()

    return jsonify({"ok": True, "cert": cnum, "hash": chash,
        "cert_url": cert_url,
        "qr_url": url_for("static", filename=f"qrcodes/{cnum}.png", _external=True),
        "label_url": url_for("static", filename=f"labels/{cnum}.png", _external=True),
        "pdf_url": url_for("static", filename=f"certs/{cnum}.pdf", _external=True)})

@app.route("/api/registry", methods=["POST"])
def api_registry():
    data = request.get_json(force=True)
    cert = (data.get("cert") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    note = (data.get("note") or "").strip()
    if not cert or not display_name:
        return jsonify({"ok": False, "error": "Missing cert or display_name"}), 400
    # ensure cert exists
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT cert FROM orders WHERE cert=?", (cert,))
    if not cur.fetchone():
        conn.close()
        return jsonify({"ok": False, "error": "Certificate not found"}), 404
    cur.execute("INSERT INTO registry(cert,display_name,note,created_at) VALUES (?,?,?,?)",
                (cert, display_name, note, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# Hashed certificate page
@app.route("/c/<cert>/<h>")
def cert_page_hashed(cert, h):
    if cert_hash(cert) != h:
        return render_template("cert_not_found.html", cert=cert), 404
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE cert=?", (cert,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return render_template("cert_not_found.html", cert=cert), 404
    qr_url = url_for("static", filename=f"qrcodes/{cert}.png")
    label_url = url_for("static", filename=f"labels/{cert}.png")
    pdf_url = url_for("static", filename=f"certs/{cert}.pdf")
    # link to submit again with prefilled values
    submit_again = url_for("submit_view", title=row["title"], service=row["service"])
    return render_template("cert.html", o=row, qr_url=qr_url, label_url=label_url, pdf_url=pdf_url, submit_again=submit_again)

# Simple alias for earlier route shape (optional)
@app.route("/cert/<cert>")
def cert_page(cert):
    return redirect(url_for("cert_page_hashed", cert=cert, h=cert_hash(cert)))

@app.route("/api/lookup")
def api_lookup():
    cert = (request.args.get("cert") or "").strip()
    if not cert:
        return jsonify({"ok": False, "error": "Missing cert parameter"}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE cert=?", (cert,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "Not found"}), 404
    key = normalize_key(row["title"] or "")
    cur.execute("SELECT grade, count FROM pops WHERE key=?", (key,))
    pr = cur.fetchall()
    conn.close()
    pop = {r["grade"]: r["count"] for r in pr}
    return jsonify({
        "ok": True, "cert": row["cert"], "title": row["title"], "grade": row["grade"],
        "name": row["name"], "service": row["service"], "created_at": row["created_at"],
        "subgrades": {"centering": row["sub_centering"], "corners": row["sub_corners"],
                      "edges": row["sub_edges"], "surface": row["sub_surface"]},
        "pop": pop
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200
