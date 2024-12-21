from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.utils import secure_filename
import os
import json
import qrcode
from io import BytesIO
import base64
from twilio.rest import Client  # ต้องติดตั้ง twilio ก่อนใช้: pip install twilio
import geocoder

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

DATABASE_FILE = "data.json"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        # ใช้ secure_filename เพื่อทำให้ชื่อไฟล์ปลอดภัย
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return 'File uploaded successfully', 200
    return 'No file uploaded', 400
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # ตั้งค่าการส่ง SMS (เก็บใน environment)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+1234567890")
RECIPIENT_PHONE_NUMBER = os.getenv("RECIPIENT_PHONE_NUMBER", "+0987654321")
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



    # Helper functions
def load_users():
        if not os.path.exists(DATABASE_FILE):
            return []
        with open(DATABASE_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)


def save_users(users):
        with open(DATABASE_FILE, 'w', encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)


class User(UserMixin):
        def __init__(self, email, name, user_id):
            self.id = email
            self.name = name
            self.user_id = user_id


@login_manager.user_loader
def load_user(email):
        users = load_users()
        user = next((u for u in users if u['email'] == email), None)
        if user:
            return User(email=user['email'], name=user['name'], user_id=user['id'])
        return None


@app.route("/home")
def index():
        return render_template("index.html", user={"name": "John Doe"})


@app.route("/", methods=['GET', 'POST'])
def register_and_login():
        if request.method == 'POST':
            action = request.form['action']  # ตรวจสอบว่าผู้ใช้ต้องการ "register" หรือ "login"
            users = load_users()

            if action == "register":
                # รับข้อมูลจากฟอร์ม
                name = request.form['name']
                email = request.form['email']
                password = request.form['password']
                relative_name = request.form['relative_name']
                relative_phone = request.form['relative_phone']
                medical_condition = request.form.get('medical_condition', '')

                # รับไฟล์ภาพโปรไฟล์ที่ผู้ใช้แนบ
                profile_picture = request.files.get('profile_picture')
                profile_picture_filename = None
                if profile_picture:
                    # ตรวจสอบว่าผู้ใช้อัปโหลดไฟล์และบันทึกภาพลงโฟลเดอร์ 'static/uploads'
                    profile_picture_filename = os.path.join(UPLOAD_FOLDER, profile_picture.filename)
                    profile_picture.save(profile_picture_filename)
                    if 'profile_picture' in request.files:
                        profile_picture_file = request.files['profile_picture']
                        if profile_picture_file and allowed_file(profile_picture_file.filename):
                            filename = secure_filename(profile_picture_file.filename)
                            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            profile_picture_file.save(filepath)
                            profile_picture = filepath  # บันทึกเส้นทางไปยังไฟล์
                        else:
                            profile_picture = ''
                    else:
                        profile_picture = ''


                # ตรวจสอบว่ามีอีเมลซ้ำในฐานข้อมูลหรือไม่
                existing_user = next((u for u in users if u['email'] == email), None)
                if existing_user:
                    flash("บัญชีนี้มีอยู่แล้ว โปรดลองล็อกอิน", 'danger')
                else:
                    # เพิ่มผู้ใช้ใหม่ในฐานข้อมูล
                    new_user = {
                        "id": str(len(users) + 1),
                        "name": name,
                        "email": email,
                        "password": password,
                        "relative_name": relative_name,
                        "relative_phone": relative_phone,
                        "medical_condition": medical_condition,
                        "location": {"latitude": 13.7563, "longitude": 100.5018},  # พิกัดเริ่มต้น
                        "profile_picture": profile_picture_filename  # เก็บ path ของภาพโปรไฟล์
                    }
                    users.append(new_user)
                    save_users(users)  # บันทึกข้อมูลผู้ใช้ลงไฟล์ฐานข้อมูล

                    # ล็อกอินผู้ใช้หลังจากสมัครสำเร็จ
                    login_user(User(email=new_user['email'], name=new_user['name'], user_id=new_user['id']))
                    return redirect(url_for('location_page'))

            elif action == "login":
                # รับข้อมูลล็อกอิน
                email = request.form['email']
                password = request.form['password']

                # ตรวจสอบอีเมลและรหัสผ่าน
                user = next((u for u in users if u['email'] == email and u['password'] == password), None)
                if user:
                    login_user(User(email=user['email'], name=user['name'], user_id=user['id']))
                    return redirect(url_for('location_page'))
                else:
                    flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง", 'danger')

        # แสดงหน้าแบบฟอร์มสมัคร/ล็อกอิน
        return render_template("register_login.html")


@app.route("/location")
@login_required
def location_page():
        users = load_users()
        user_data = next((u for u in users if u['email'] == current_user.id), None)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data("https://your-website-url.com")
        qr.make(fit=True)
        buffered = BytesIO()
        qr.make_image(fill='black', back_color='white').save(buffered, format="PNG")
        qr_code_img = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return render_template("location.html", user=user_data, qr_code_img=qr_code_img)


@app.route("/logout")
def logout():
        logout_user()
        return redirect(url_for('register_and_login'))


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=3000)