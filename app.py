from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import os, json
import pandas as pd
from db_config import get_connection
from werkzeug.utils import secure_filename
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
USER_FILE = 'users.json'

def get_users():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w') as f: json.dump({}, f)
    with open(USER_FILE) as f:
        return json.load(f)

def fetch_df():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM dbo.MLS_Master_Data1", conn)
    conn.close()
    return df

@app.route('/')
def home():
    if "user" not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        users = get_users()
        if email in users and users[email] == password:
            session["user"] = email
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        users = get_users()
        if email in users:
            flash('User already exists')
        else:
            users[email] = password
            with open(USER_FILE, 'w') as f: json.dump(users, f)
            flash('Signup successful! Please log in.')
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop("user", None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template('dashboard.html')

@app.route('/api/districts')
def api_districts():
    df = fetch_df()
    districts = df['District_Name'].dropna().unique().tolist()
    return jsonify(sorted(districts))

@app.route('/api/mandals')
def api_mandals():
    district = request.args.get('district')
    df = fetch_df()
    mandals = df[df['District_Name'] == district]['Mandal_Name'].dropna().unique().tolist()
    return jsonify(sorted(mandals))

@app.route('/api/mls_point_by_district_mandal')
def api_mls_point_by_district_mandal():
    district = request.args.get('district', '').strip().lower()
    mandal = request.args.get('mandal', '').strip().lower()
    df = fetch_df()
    # Normalize columns for comparison
    df['District_Name_norm'] = df['District_Name'].astype(str).str.strip().str.lower()
    df['Mandal_Name_norm'] = df['Mandal_Name'].astype(str).str.strip().str.lower()
    subset = df[(df['District_Name_norm'] == district) & (df['Mandal_Name_norm'] == mandal)]
    if subset.empty:
        return jsonify({"error": "No MLS Point found for this District & Mandal"}), 404
    data = subset.iloc[0].to_dict()
    return jsonify(data)

@app.route('/detail/<mls_code>', methods=['GET', 'POST'])
def mls_detail(mls_code):
    if "user" not in session:
        return redirect(url_for("login"))
    df = fetch_df()
    row = df[df['MLS_Point_Code'] == mls_code]
    if row.empty: return "MLS Point Not Found", 404
    info = row.iloc[0].to_dict()
    # Edit handling (simulate in-memory for demo)
    if request.method == 'POST':
        # Here you'd update the DB with the POSTed fields
        flash('Changes saved (demo; add real DB update logic here)')
        return redirect(url_for('mls_detail', mls_code=mls_code))
    img_paths = []
    for cam in range(1, 9):  # Up to 8 camera IPs
        ip_img = f"{mls_code}_cam{cam}.jpg"
        if os.path.exists(os.path.join(UPLOAD_FOLDER, ip_img)):
            img_paths.append((cam, url_for('static', filename=f"uploads/{ip_img}")))
        else:
            img_paths.append((cam, None))
    return render_template('mls_detail.html', info=info, mls_code=mls_code, img_paths=img_paths)

@app.route('/upload_camera/<mls_code>/<int:cam>', methods=['POST'])
def upload_camera(mls_code, cam):
    file = request.files.get('ipimage')
    if file:
        filename = secure_filename(f"{mls_code}_cam{cam}.jpg")
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        flash(f'Camera {cam} image uploaded!')
    return redirect(url_for('mls_detail', mls_code=mls_code))

@app.route('/ekyc/<mls_code>/<role>', methods=['POST'])
def ekyc_point(mls_code, role):
    # "role" is either 'incharge' or 'deo'
    flash(f"eKYC process triggered for {role.upper()} (Demo!)")
    return redirect(url_for('mls_detail', mls_code=mls_code))

@app.route('/download_pdf/<mls_code>')
def download_pdf(mls_code):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    df = fetch_df()
    row = df[df['MLS_Point_Code'] == mls_code]
    buffer = BytesIO()
    if row.empty:
        buffer.write(b"Not Found"); buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="NotFound.pdf", mimetype='application/pdf')
    c = canvas.Canvas(buffer, pagesize=letter)
    info = row.iloc[0].to_dict()
    y = 750
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"MLS Point Dashboard")
    y -= 25
    c.setFont("Helvetica", 11)
    for k, v in info.items():
        c.drawString(50, y, f"{k}: {v}")
        y -= 15
        if y < 60:
            c.showPage(); y = 750
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"MLS_{mls_code}_dashboard.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
