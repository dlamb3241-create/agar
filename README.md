
# AGA Grading — PRO Build (Render-ready)

**Features**
- AI pre-check (fast heuristic, Render-friendly)
- Orders -> cert numbers, hashed cert URLs
- QR code PNGs, label PNGs, certificate PDFs
- SQLite on Render Disk (`/data/aga.db`) with env override
- Live stats API + homepage ticker
- Recently Graded grid
- Pop Report with heatmap coloring
- Registry page + API
- Submit Again autofill
- Tagline under logo
- Health endpoint `/health`

**Deploy on Render**
1. Push this folder to a new Git repo.
2. Create Web Service → connect repo.
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app`
5. Render will create a Disk and env vars from `render.yaml` automatically.
6. Make sure your service has a health check path `/health` configured.

**Assets**
- Replace `static/img/card1..4.jpg` with your own if desired.  
- Cert PDFs, labels, and QRs are stored under `static/certs|labels|qrcodes`.

**Security**
- Hashed cert URLs: `/c/<cert>/<hash>` built from `CERT_SALT`. Change `CERT_SALT` in env after deploy.

**Stripe**
- Not wired by request. Add your checkout before hitting `/api/order` if needed.
