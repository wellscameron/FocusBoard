import streamlit as st
import json
from pathlib import Path
import bcrypt
from datetime import datetime
class UserAuth:
    def __init__(self):
        self.users_dir = Path("users")
        self.users_dir.mkdir(exist_ok=True)
        self.users_file = self.users_dir / "users.json"
        self._load_users()

    def _load_users(self):
        if self.users_file.exists():
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}
            self._save_users()

    def _save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f)

    def register_user(self, username, password):
        if username in self.users:
            return False, "Username already exists"
        
        salt = bcrypt.gensalt()
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        self.users[username] = {
            'password': hashed_pw.decode('utf-8'),
            'created_at': str(datetime.now())
        }
        self._save_users()
        return True, "Registration successful"

    def login_user(self, username, password):
        if username not in self.users:
            return False, "Invalid username or password"
        
        stored_pw = self.users[username]['password'].encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), stored_pw):
            return True, "Login successful"
        return False, "Invalid username or password" 