import os, io, sqlite3, hashlib
from datetime import datetime
from flask import Flask, render_template, request, jsonify, url_for
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Use local DB for Render free plan (no permission issues)
DB_PATH = os.environ.get("DB_PATH", "aga.db")
CERT_SALT = os.environ.get("CERT_SALT", "change-me")

app = Flask(__name__, template_folder="templates", static_folder="static")

# ------------------ DATABASE SETUP ------------------
def get_db():
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

# ------------------ HELPERS ------------------
def make_cert():
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rand = os.urandom(3).hex().upper()
    return f"AGA{stamp}{rand}"

def cert_hash(cert):
    return hashlib.sha256((CERT_SALT + cert).encode()).hexdigest()[:10]

def ensure_dirs():
    for d in ["static/qrcodes","static/labels","static/certs"]:
        os.makedirs(d, exist_ok=True)

def qr_png(text, out_path):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(out_path)

def label_png(cert, title, name, service, out_path):
    W, H = 900, 500
    im = Image.new("RGB", (W, H), (245,245,245))
    d = ImageDraw.Draw(im)
    red = (220,38,38)
    dark = (20,25,35)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except:
        font_title = font_text = None
    d.rectangle([20,20,W-20,H-20], outline=red, width=6)
    d.text((40,40),"Authentic Grading Authority",fill=dark,font=font_title)
    d.text((40,110),f"Cert: {cert}",fill=dark,font=font_text)
    d.text((40,150),f"Card: {title}",fill=dark,font=font_text)
    d.text((40,190),f"Customer: {name}",fill=dark,font=font_text)
    d.text((40,230),f"Service: {service}",fill=dark,font=font_text)
    qr = qrcode.QRCode(box_size=4,border=2)
    qr.add_data(cert)
    qr.make(fit=True)
    im_qr = qr.make_image().convert("RGB").resize((200,200))
    im.paste(im_qr,(W-240,60))
    im.save(out_path,"PNG")

def cert_pdf(cert, title, grade, subs, created_at, out_path):
    c = canvas.Canvas(out_path, pagesize=letter)
    width, height = letter
    c.setTitle(f"AGA Certificate {cert}")
    c.setFillColorRGB(0.86,0.15,0.15)
    c.rect(0,height-80,width,80,fill=1,stroke=0)
    c.setFillColorRGB(1,1,1)
    c.setFont("Helvetica-Bold",26)
    c.drawString(40,height-50,"Authentic Grading Authority")
    c.setFillColorRGB(0,0,0)
    c.setFont("Helvetica",14)
    c.drawString(40,height-120,f"Certificate: {cert}")
    c.drawString(40,height-140,f"Card: {title}")
    c.drawString(40,height-160,f"Grade: {grade}")
    c.drawString(40,height-180,f"Subgrades: {subs}")
    c.drawString(40,height-200,f"Issued: {created_at}")
    qr_path=f"static/qrcodes/{cert}.png"
    if os.path.exists(qr_path):
        c.drawImage(qr_path,width-180,60,120,120,mask='auto')
    c.save()

# ------------------ MAIN ROUTES ------------------
@app.route("/")
def home():
    conn=get_db()
    cur=conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM orders")
    total=cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) as g FROM orders WHERE grade='Gem Mint 10'")
    gem10=cur.fetchone()["g"]
    cur.execute("SELECT cert,title,grade,created_at FROM orders ORDER BY id DESC LIMIT 10")
    recent=cur.fetchall()
    conn.close()
    return render_template("index.html",total=total,gem10=gem10,recent=recent)

@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

@app.route("/submit")
def submit_view():
    return render_template("submit.html")

@app.route("/lookup")
def lookup_view():
    return render_template("lookup.html")

@app.route("/pop-report")
def pop_report_view():
    return render_template("pop.html")

@app.route("/registry")
def registry_view():
    return render_template("registry.html")

# ------------------ API ROUTES ------------------
@app.route("/api/grade", methods=["POST"])
def api_grade():
    if "image" not in request.files:
        return jsonify({"ok":False,"error":"No image"}),400
    f=request.files["image"]
    img=Image.open(io.BytesIO(f.read())).convert("RGB")
    small=img.resize((256,256))
    edges=small.filter(ImageFilter.FIND_EDGES).convert("L")
    val=int(sum(edges.getdata())/(256*256)/10)
    val=max(70,min(99,val))
    if val>92:g="Gem Mint 10"
    elif val>88:g="Mint 9"
    elif val>84:g="NM-MT 8"
    else:g="NM 7"
    subs={"centering":str(val-2),"corners":str(val-3),"edges":str(val-4),"surface":str(val-5)}
    return jsonify({"ok":True,"grade":g,"subgrades":subs})

@app.route("/api/order", methods=["POST"])
def api_order():
    data=request.get_json(force=True)
    name=data.get("name"); email=data.get("email"); service=data.get("service"); title=data.get("title")
    grade=data.get("grade","Pending"); subs=data.get("subgrades",{})
    if not name or not email or not service:
        return jsonify({"ok":False,"error":"Missing fields"}),400
    cert=make_cert(); h=cert_hash(cert); created=datetime.utcnow().isoformat()
    ensure_dirs()
    conn=get_db(); cur=conn.cursor()
    cur.execute("""INSERT INTO orders(cert,hash,name,email,service,title,grade,sub_centering,sub_corners,sub_edges,sub_surface,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cert,h,name,email,service,title,grade,
                 subs.get("centering",""),subs.get("corners",""),
                 subs.get("edges",""),subs.get("surface",""),created))
    conn.commit(); conn.close()
    qr_path=f"static/qrcodes/{cert}.png"; label_path=f"static/labels/{cert}.png"; pdf_path=f"static/certs/{cert}.pdf"
    qr_png(f"/cert/{cert}",qr_path)
    label_png(cert,title,name,service,label_path)
    cert_pdf(cert,title,grade,subs,created,pdf_path)
    return jsonify({
        "ok":True,
        "cert":cert,
        "hash":h,
        "cert_url":url_for("cert_page",cert=cert,_external=True),
        "qr_url":url_for("static",filename=f"qrcodes/{cert}.png",_external=True),
        "label_url":url_for("static",filename=f"labels/{cert}.png",_external=True),
        "pdf_url":url_for("static",filename=f"certs/{cert}.pdf",_external=True)
    })

@app.route("/cert/<cert>")
def cert_page(cert):
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT * FROM orders WHERE cert=?",(cert,))
    row=cur.fetchone(); conn.close()
    if not row: return render_template("cert_not_found.html"),404
    return render_template("cert.html",o=row,
        qr_url=url_for("static",filename=f"qrcodes/{cert}.png"),
        label_url=url_for("static",filename=f"labels/{cert}.png"),
        pdf_url=url_for("static",filename=f"certs/{cert}.pdf"))

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

# ------------------ MAIN ------------------
if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
