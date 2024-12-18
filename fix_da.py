import json

DATABASE_FILE = "data.json"

def clean_data():
    if not os.path.exists(DATABASE_FILE):
        print("File not found!")
        return

    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        users = json.load(f)

    # แก้ไขข้อมูลให้ทุก object มี key 'email'
    cleaned_users = []
    for user in users:
        if 'email' in user:
            cleaned_users.append(user)

    # เขียนข้อมูลกลับไป
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cleaned_users, f, ensure_ascii=False, indent=4)
    print("Cleaned data saved successfully.")

clean_data()