from flask import Flask, request, jsonify
from pymongo import MongoClient
import json
import os
import time
import signal
import glob

app = Flask(__name__)
PORT = 5050
app.static_folder = "public"

# Ensure the static folder exists
os.makedirs(app.static_folder, exist_ok=True)

# Create form.html in the static folder
form_html = """<!DOCTYPE html>
<html>
<head>
    <title>Add User</title>
</head>
<body>
    <h1>Add New User</h1>
    <form action="/addUser" method="POST">
        <div>
            <label for="name">Name:</label>
            <input type="text" id="name" name="name" required>
        </div>
        <div>
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" required>
        </div>
        <div>
            <label for="age">Age:</label>
            <input type="number" id="age" name="age">
        </div>
        <button type="submit">Add User</button>
    </form>
</body>
</html>"""

# Write the form HTML to the static folder
with open(os.path.join(app.static_folder, 'form.html'), 'w') as f:
    f.write(form_html)

MONGO_URL = "mongodb://admin:qwerty@mongo:27017"
client = MongoClient(MONGO_URL)
S3_MOUNT_POINT = os.environ.get('S3_MOUNT_POINT', '/s3data')
BACKUP_DIR = f"{S3_MOUNT_POINT}/backups"

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)

# Initialize database
db = client["apnacollege-db"]
users_collection = db["users"]

# Function to backup data to S3
def backup_data():
    try:
        timestamp = int(time.time())
        backup_file = f"{BACKUP_DIR}/users_backup_latest.json"
        
        # Get all users from MongoDB
        users = list(users_collection.find({}))
        
        # Convert ObjectId to string for JSON serialization
        for user in users:
            if '_id' in user:
                user['_id'] = str(user['_id'])
        
        # Write to backup file in S3 mount
        with open(backup_file, 'w') as f:
            json.dump(users, f)
            
        # Also create timestamped version for history
        with open(f"{BACKUP_DIR}/users_backup_{timestamp}.json", 'w') as f:
            json.dump(users, f)
            
        print(f"Backup created at {backup_file}")
    except Exception as e:
        print(f"Backup error: {str(e)}")

# Function to restore data from S3
def restore_data():
    try:
        # Try to use the latest backup file first
        latest_backup = f"{BACKUP_DIR}/users_backup_latest.json"
        
        # If latest doesn't exist, try to find any timestamped backups
        if not os.path.exists(latest_backup):
            backup_files = glob.glob(f"{BACKUP_DIR}/users_backup_*.json")
            if not backup_files:
                print("No backup files found")
                return
            latest_backup = max(backup_files, key=os.path.getctime)
        
        print(f"Found backup: {latest_backup}")
        
        # Read backup file
        with open(latest_backup, 'r') as f:
            users = json.load(f)
        
        # Clear existing data and insert from backup
        if users:
            users_collection.delete_many({})  # Clear existing data
            users_collection.insert_many(users)
            print(f"Restored {len(users)} users from backup")
        else:
            print("Backup file empty or invalid")
            
    except Exception as e:
        print(f"Restore error: {str(e)}")

# Handle SIGTERM gracefully (for Docker container stops)
def handle_sigterm(signum, frame):
    print("Container is shutting down, creating backup...")
    backup_data()
    exit(0)

# Register signal handler for graceful shutdown
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# Periodic backup function
def setup_periodic_backup():
    import threading
    
    def backup_thread():
        while True:
            time.sleep(300)  # Backup every 5 minutes
            backup_data()
    
    thread = threading.Thread(target=backup_thread, daemon=True)
    thread.start()

# GET all users
@app.route("/getUsers", methods=["GET"])
def get_users():
    print('Connected successfully to server')
    
    data = list(users_collection.find({}))
    
    # Convert ObjectId to string for JSON serialization
    for item in data:
        if '_id' in item:
            item['_id'] = str(item['_id'])
    
    return jsonify(data)

# POST new user
@app.route("/addUser", methods=["POST"])
def add_user():
    user_obj = request.form.to_dict()
    print(user_obj)
    
    print('Connected successfully to server')
    
    data = users_collection.insert_one(user_obj)
    print(data)
    print("data inserted in DB")
    
    # Backup data immediately when a user is added
    backup_data()
    
    return "User added successfully"

# Add the form route
@app.route("/form", methods=["GET"])
def show_form():
    return app.send_static_file('form.html')

# Manual backup endpoint
@app.route("/backup", methods=["GET"])
def trigger_backup():
    backup_data()
    return "Backup created successfully"

# Manual restore endpoint
@app.route("/restore", methods=["GET"])
def trigger_restore():
    restore_data()
    return "Restore completed"

# Add a root route to handle / requests
@app.route("/", methods=["GET"])
def root():
    return "API is running. Use /getUsers to get users and /addUser to add a user. Use /backup to trigger a backup and /restore to restore from S3. Visit /form to add a user through a web form."

if __name__ == "__main__":
    # Always restore data at startup
    restore_data()
    
    # Setup periodic backups
    setup_periodic_backup()
    
    app.run(host="0.0.0.0", port=PORT)
    print(f"server running on port {PORT}")