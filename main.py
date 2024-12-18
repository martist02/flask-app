from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # --- ตั้งค่าการส่ง SMS ---
TWILIO_ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"  # ใส่ SID ของ Twilio
TWILIO_AUTH_TOKEN = "YOUR_TWILIO_AUTH_TOKEN"    # ใส่ Auth Token ของ Twilio
TWILIO_PHONE_NUMBER = "+1234567890"            # ใส่เบอร์ Twilio
RECIPIENT_PHONE_NUMBER = "+0987654321"         # เบอร์ปลายทาง (ญาติผู้ป่วย)

    # Helper function to load and save users
def load_users():
        if not os.path.exists(DATABASE_FILE):
            return []
        with open(DATABASE_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)

def save_users(users):
        with open(DATABASE_FILE, 'w', encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)

    # User class for Flask-Login
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

@app.route("/", methods=['GET', 'POST'])
def register_and_login():
        if request.method == 'POST':
            action = request.form['action']
            users = load_users()

            if action == "register":
                name = request.form['name']
                email = request.form['email']
                password = request.form['password']
                relative_name = request.form['relative_name']
                relative_phone = request.form['relative_phone']
                medical_condition = request.form.get('medical_condition', '')
                profile_picture = request.form.get('profile_picture', '')  # Optional image file path

                # ตรวจสอบหาผู้ใช้ที่มีอีเมลนี้
                existing_user = next((u for u in users if u['email'] == email), None)
                if existing_user:
                    flash("บัญชีนี้มีอยู่แล้ว โปรดลองล็อกอิน", 'danger')
                else:
                    # สร้างผู้ใช้ใหม่
                    new_user = {
                        "id": str(len(users) + 1),
                        "name": name,
                        "email": email,
                        "password": password,
                        "relative_name": relative_name,
                        "relative_phone": relative_phone,
                        "medical_condition": medical_condition,
                        "location": {"latitude": 13.7563, "longitude": 100.5018},  # Default location
                        "profile_picture": profile_picture
                    }
                    users.append(new_user)
                    save_users(users)

                    login_user(User(email=new_user['email'], name=new_user['name'], user_id=new_user['id']))
                    return redirect(url_for('location_page'))

            elif action == "login":
                email = request.form['email']
                password = request.form['password']
                user = next((u for u in users if u['email'] == email and u['password'] == password), None)

                if user:
                    login_user(User(email=user['email'], name=user['name'], user_id=user['id']))
                    return redirect(url_for('location_page'))
                else:
                    flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง", 'danger')

        return render_template("register_login.html")

@app.route("/location")
@login_required
def location_page():
        users = load_users()
        user_data = next((u for u in users if u['email'] == current_user.id), None)

        # เพิ่มฟังก์ชันให้ดึงตำแหน่งจาก client-side โดยการใช้ JavaScript
        user_info = {
            'name': user_data['name'],
            'relative_name': user_data['relative_name'],
            'relative_phone': user_data['relative_phone'],
            'medical_condition': user_data['medical_condition'],
            'location': user_data['location']
        }

        # สร้าง URL สำหรับไปที่เว็บไซต์ที่คุณต้องการ
        website_url = "https://your-website-url.com"  # เพิ่ม URL ของเว็บไซต์

        # สร้าง QR Code ให้ผู้ใช้เข้าเว็บไซต์
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(website_url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_img = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return render_template("location.html", user=user_data, qr_code_img=qr_code_img, website_url=website_url)

@app.route("/update_location", methods=['POST'])
@login_required
def update_location():
        data = request.get_json()  # รับข้อมูล JSON
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if latitude is None or longitude is None:
            return jsonify({"message": "Missing latitude or longitude"}), 400

        # อัปเดตตำแหน่งผู้ใช้
        users = load_users()
        user_data = next((u for u in users if u['email'] == current_user.id), None)

        if user_data:
            user_data['location'] = {"latitude": latitude, "longitude": longitude}
            save_users(users)
            return jsonify({"message": "Location updated successfully"}), 200
        else:
            return jsonify({"message": "User not found"}), 404

    # ฟังก์ชันส่ง SMS
def send_sms(location):
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=f"ผู้ใช้อยู่ที่ตำแหน่ง: {location['latitude']}, {location['longitude']}",
                from_=TWILIO_PHONE_NUMBER,
                to=RECIPIENT_PHONE_NUMBER,
            )
            return f"ข้อความส่งสำเร็จ: {message.sid}"
        except Exception as e:
            return f"การส่งข้อความล้มเหลว: {str(e)}"

@app.route("/scan_qr", methods=["POST"])
def scan_qr():
        location = get_location()
        sms_response = send_sms(location)
        response_data = {
            "message": "QR Code scanned successfully!",
            "location": location,
            "sms_status": sms_response,
        }
        return jsonify(response_data)

    # ฟังก์ชันดึงตำแหน่งจาก IP
def get_location():
        g = geocoder.ip("me")  # ใช้ IP เพื่อดึงพิกัด
        if g.latlng:
            return {"latitude": g.latlng[0], "longitude": g.latlng[1]}
        return {"latitude": None, "longitude": None}

    # ลงชื่อออก
@app.route('/logout')
def logout():
        logout_user()
        return redirect(url_for('register_and_login'))

if __name__ == '__main__':
        app.run(debug=True)