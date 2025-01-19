from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import json
from twilio.rest import Client

app = Flask(__name__)
socketio = SocketIO(app, engineio_logger=True)  # ใช้ logger สำหรับดู logs ของ socket

# Configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB Limit

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'register_and_login'

# Constants
DATABASE_FILE = "data.json"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class User(UserMixin):
    def __init__(self, email, name, user_id):
        self.id = email
        self.name = name
        self.user_id = user_id

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_users():
    if not os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return []
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_users(users):
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

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
        action = request.form.get('action')
        users = load_users()

        if action == "register":
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            relative_phone = request.form.get('relative_phone')
            medical_condition = request.form.get('medical_condition')

            if any(u['email'] == email for u in users):
                flash('อีเมลนี้ถูกใช้งานแล้ว', 'danger')
                return redirect(url_for('register_and_login'))

            profile_picture = request.files.get('profile_picture')
            profile_picture_path = None

            if profile_picture and allowed_file(profile_picture.filename):
                filename = secure_filename(f"{email}_{profile_picture.filename}")
                profile_picture_path = os.path.join('uploads', filename)
                profile_picture.save(os.path.join('static', profile_picture_path))

            new_user = {
                "id": str(len(users) + 1),
                "name": name,
                "email": email,
                "password": password,
                "relative_phone": relative_phone,
                "medical_condition": medical_condition,
                "location": {"latitude": None, "longitude": None},
                "profile_picture": profile_picture_path
            }

            users.append(new_user)
            save_users(users)

            user = User(email=new_user['email'], name=new_user['name'], user_id=new_user['id'])
            login_user(user)
            flash('ลงทะเบียนสำเร็จ!', 'success')
            return redirect(url_for('location_page'))

        elif action == "login":
            email = request.form.get('email')
            password = request.form.get('password')

            user = next((u for u in users if u['email'] == email and u['password'] == password), None)
            if user:
                login_user(User(email=user['email'], name=user['name'], user_id=user['id']))
                flash('เข้าสู่ระบบสำเร็จ!', 'success')
                return redirect(url_for('location_page'))
            else:
                flash('อีเมลหรือรหัสผ่านไม่ถูกต้อง', 'danger')

    return render_template('register_login.html')

@app.route("/location")
@login_required
def location_page():
    users = load_users()
    user_data = next((u for u in users if u['email'] == current_user.id), None)
    return render_template('location.html', user=user_data)

@socketio.on('update_location')
def handle_location_update(data):
    users = load_users()
    user = next((u for u in users if u['email'] == current_user.id), None)

    if user:
        user['location']['latitude'] = data['latitude']
        user['location']['longitude'] = data['longitude']
        save_users(users)

        send_notification_to_relative(user)

        emit('location_updated', {
            'user_id': user['id'],
            'latitude': data['latitude'],
            'longitude': data['longitude']
        }, broadcast=True)

def send_notification_to_relative(user):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        google_maps_url = f"https://www.google.com/maps?q={user['location']['latitude']},{user['location']['longitude']}"
        message = client.messages.create(
            body=f"อัพเดทตำแหน่งล่าสุดของ {user['name']}: {google_maps_url}",
            from_=TWILIO_PHONE_NUMBER,
            to=user['relative_phone']
        )
    except Exception as e:
        print(f"Failed to send SMS: {e}")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('ออกจากระบบสำเร็จ', 'success')
    return redirect(url_for('register_and_login'))

if __name__ == "__main__":
        # ใช้ Eventlet
        import eventlet
        eventlet.monkey_patch()  # Monkey patch เพื่อรองรับ WebSocket
        from eventlet import wsgi
        wsgi.server(eventlet.listen(('0.0.0.0', int(os.environ.get("PORT", 3000)))), app)



