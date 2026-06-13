import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import urllib.request
import urllib.error
import json
import datetime
import random

import hashlib

import os
import base64

# ==============================================================================
# ⚠️ FIREBASE CONFIGURATION & SECURITY
# If you migrate your database to a new Firebase project, replace these settings.
# ==============================================================================
PROJECT_ID = "stock-manager-70efc"
API_KEY = "AIzaSyBt3Q4K0mFtP2xGvHnJkLdR7sBqEuWwYM"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
MASTER_PASSWORD_HASH = "f3e4aac20bc59a9b6ffe711ec90bb3f54cd26c8bd4f0687ee15212e878f46a36"

# 🔑 ADD YOUR SECURE FIREBASE LOGIN HERE:
# If you put your Firebase authentication email and password here, the app will 
# authenticate automatically. If left blank, it will prompt you on startup 
# and save it securely in a local computer file so nobody else can see it.
FIREBASE_AUTH_EMAIL = ""
FIREBASE_AUTH_PASSWORD = ""

# Session token for firebase requests
firebase_id_token = None

# XOR symmetric cipher with base64 wrapper for storing non-public passwords in Firestore
def encrypt_password(password, master_password):
    cipher = "".join(chr(ord(c) ^ ord(master_password[i % len(master_password)])) for i, c in enumerate(password))
    return base64.b64encode(cipher.encode('utf-8')).decode('utf-8')

def decrypt_password(ciphertext, master_password):
    try:
        raw = base64.b64decode(ciphertext.encode('utf-8')).decode('utf-8')
        return "".join(chr(ord(c) ^ ord(master_password[i % len(master_password)])) for i, c in enumerate(raw))
    except:
        return "Decryption Error"

class FirebasePermissionError(Exception):
    pass

class FirestoreClient:
    @staticmethod
    def show_firebase_rules_error():
        help_text = (
            "Access Denied (HTTP 403: Forbidden)\n\n"
            "This error means your Firebase Database Security Rules are blocking writes.\n"
            "To resolve this, please update your rules in the Firebase Console:\n\n"
            "1. Go to console.firebase.google.com\n"
            "2. Select your project: 'stock-manager-70efc'\n"
            "3. Click 'Firestore Database' -> 'Rules' tab\n"
            "4. Replace the existing rules with:\n\n"
            "rules_version = '2';\n"
            "service cloud.firestore {\n"
            "  match /databases/{database}/documents {\n"
            "    match /{document=**} {\n"
            "      allow read, write: if request.auth != null;\n"
            "    }\n"
            "  }\n"
            "}\n\n"
            "5. Click 'Publish' and wait 30 seconds."
        )
        dialog = tk.Toplevel()
        dialog.title("How to Resolve HTTP 403 Error")
        dialog.geometry("550x480")
        dialog.configure(bg="#12131a")
        dialog.attributes("-topmost", True)
        
        title_label = tk.Label(dialog, text="⚠️ Firebase Rules Error (HTTP 403)", font=("Segoe UI", 12, "bold"), bg="#12131a", fg="#ff4d4d")
        title_label.pack(pady=10)
        
        txt = tk.Text(dialog, bg="#1a1d2e", fg="#eef0fa", font=("Consolas", 10), wrap="word", borderwidth=0)
        txt.pack(expand=True, fill="both", padx=20, pady=10)
        txt.insert("1.0", help_text)
        txt.config(state="disabled")
        
        btn = tk.Button(dialog, text="Close", command=dialog.destroy, bg="#1f2235", fg="#eef0fa", activebackground="#2d314d", borderwidth=0, padding=8, font=('Segoe UI', 10, 'bold'))
        btn.pack(pady=15)

    @staticmethod
    def get_collection(collection_name):
        try:
            url = f"{BASE_URL}/{collection_name}?key={API_KEY}"
            req = urllib.request.Request(url)
            if firebase_id_token:
                req.add_header('Authorization', f'Bearer {firebase_id_token}')
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                docs = []
                for doc in data.get('documents', []):
                    doc_id = doc['name'].split('/')[-1]
                    fields = doc.get('fields', {})
                    parsed = {'id': doc_id}
                    for k, v in fields.items():
                        if 'stringValue' in v:
                            parsed[k] = v['stringValue']
                        elif 'integerValue' in v:
                            parsed[k] = int(v['integerValue'])
                        elif 'booleanValue' in v:
                            parsed[k] = v['booleanValue']
                    docs.append(parsed)
                return docs
        except urllib.error.HTTPError as e:
            if e.code == 403:
                FirestoreClient.show_firebase_rules_error()
                raise FirebasePermissionError("Forbidden")
            if e.code == 404:
                return []
            raise e

    @staticmethod
    def add_document(collection_name, doc_id, data):
        fields = {}
        for k, v in data.items():
            if isinstance(v, str):
                fields[k] = {"stringValue": v}
            elif isinstance(v, int):
                fields[k] = {"integerValue": str(v)}
            elif isinstance(v, bool):
                fields[k] = {"booleanValue": v}
                
        payload = {"fields": fields}
        url = f"{BASE_URL}/{collection_name}?documentId={doc_id}&key={API_KEY}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST')
        req.add_header('Content-Type', 'application/json')
        if firebase_id_token:
            req.add_header('Authorization', f'Bearer {firebase_id_token}')
        try:
            with urllib.request.urlopen(req) as response:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 403:
                FirestoreClient.show_firebase_rules_error()
                raise FirebasePermissionError("Forbidden")
            if e.code == 409: # Conflict, patch instead
                url = f"{BASE_URL}/{collection_name}/{doc_id}?key={API_KEY}"
                req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='PATCH')
                req.add_header('Content-Type', 'application/json')
                if firebase_id_token:
                    req.add_header('Authorization', f'Bearer {firebase_id_token}')
                try:
                    with urllib.request.urlopen(req) as response:
                        return True
                except urllib.error.HTTPError as ex:
                    if ex.code == 403:
                        FirestoreClient.show_firebase_rules_error()
                        raise FirebasePermissionError("Forbidden")
                    raise ex
            raise e

    @staticmethod
    def update_document(collection_name, doc_id, data):
        fields = {}
        for k, v in data.items():
            if isinstance(v, str):
                fields[k] = {"stringValue": v}
            elif isinstance(v, int):
                fields[k] = {"integerValue": str(v)}
            elif isinstance(v, bool):
                fields[k] = {"booleanValue": v}
        payload = {"fields": fields}
        url = f"{BASE_URL}/{collection_name}/{doc_id}?key={API_KEY}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='PATCH')
        req.add_header('Content-Type', 'application/json')
        if firebase_id_token:
            req.add_header('Authorization', f'Bearer {firebase_id_token}')
        try:
            with urllib.request.urlopen(req) as response:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 403:
                FirestoreClient.show_firebase_rules_error()
                raise FirebasePermissionError("Forbidden")
            raise e

    @staticmethod
    def delete_document(collection_name, doc_id):
        url = f"{BASE_URL}/{collection_name}/{doc_id}?key={API_KEY}"
        req = urllib.request.Request(url, method='DELETE')
        if firebase_id_token:
            req.add_header('Authorization', f'Bearer {firebase_id_token}')
        try:
            with urllib.request.urlopen(req) as response:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 403:
                FirestoreClient.show_firebase_rules_error()
                raise FirebasePermissionError("Forbidden")
            raise e
        except Exception as e:
            print(f"Error deleting: {e}")
            return False

class AdminCommanderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Yamunaji Inventory Controller")
        self.geometry("1024x720")
        self.configure(bg="#12131a")
        
        # UI Styling
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('.', background='#12131a', foreground='#eef0fa', font=('Segoe UI', 10))
        self.style.configure('TFrame', background='#12131a')
        self.style.configure('TLabel', background='#12131a', foreground='#eef0fa')
        self.style.configure('TButton', background='#1f2235', foreground='#eef0fa', borderwidth=0, padding=8, font=('Segoe UI', 10, 'bold'))
        self.style.map('TButton', background=[('active', '#2d314d')])
        self.style.configure('Treeview', background='#1a1d2e', foreground='#eef0fa', fieldbackground='#1a1d2e', rowheight=28)
        self.style.map('Treeview', background=[('selected', '#4f7aff')], foreground=[('selected', '#ffffff')])
        self.style.configure('Treeview.Heading', background='#22263f', foreground='#eef0fa', font=('Segoe UI', 10, 'bold'))
        
        self.current_frame = None
        self.show_login_screen()

    def show_login_screen(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.current_frame = ttk.Frame(self)
        self.current_frame.pack(expand=True, fill='both')

        login_box = ttk.Frame(self.current_frame, padding=40)
        login_box.place(relx=0.5, rely=0.5, anchor='center')

        ttk.Label(login_box, text="🔑", font=("Segoe UI", 48)).pack(pady=(0, 10))
        ttk.Label(login_box, text="Yamunaji Controller", font=("Segoe UI", 20, "bold")).pack(pady=(0, 5))
        ttk.Label(login_box, text="Sign in to your Firebase account", font=("Segoe UI", 10), foreground="#8891b5").pack(pady=(0, 16))

        # Firebase Auth credentials
        ttk.Label(login_box, text="Firebase Email:").pack(anchor='w')
        self.email_entry = ttk.Entry(login_box, width=34, font=("Segoe UI", 11))
        self.email_entry.pack(pady=(2, 10))

        ttk.Label(login_box, text="Firebase Password:").pack(anchor='w')
        self.fb_pass_entry = ttk.Entry(login_box, show="*", width=34, font=("Segoe UI", 11))
        self.fb_pass_entry.pack(pady=(2, 10))

        ttk.Label(login_box, text="Master Password (Yamunaji_0791):").pack(anchor='w')
        self.pass_entry = ttk.Entry(login_box, show="*", width=34, font=("Segoe UI", 11))
        self.pass_entry.pack(pady=(2, 10))
        self.pass_entry.bind("<Return>", lambda e: self.verify_login())

        self.login_status = ttk.Label(login_box, text="", foreground="#ff4d4d", font=("Segoe UI", 9))
        self.login_status.pack(pady=(0, 5))

        btn = ttk.Button(login_box, text="Sign In & Unlock →", command=self.verify_login)
        btn.pack(pady=5, fill='x')

        ttk.Label(login_box, text="💡 Your Firebase email and password are saved locally\nand never uploaded to GitHub.", 
                  font=("Segoe UI", 8), foreground="#454d6e", justify="center").pack(pady=(10, 0))

        # Pre-fill from saved credentials or FIREBASE_AUTH_EMAIL constant
        saved = self._load_saved_credentials()
        if FIREBASE_AUTH_EMAIL:
            self.email_entry.insert(0, FIREBASE_AUTH_EMAIL)
        elif saved.get("email"):
            self.email_entry.insert(0, saved["email"])
        if FIREBASE_AUTH_PASSWORD:
            self.fb_pass_entry.insert(0, FIREBASE_AUTH_PASSWORD)
        elif saved.get("password"):
            self.fb_pass_entry.insert(0, saved["password"])

    def _get_credentials_file(self):
        """Return path to local credentials file (next to the script, ignored by git)."""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".firebase_auth.json")

    def _load_saved_credentials(self):
        try:
            path = self._get_credentials_file()
            if os.path.exists(path):
                with open(path, "r") as f:
                    return json.load(f)
        except:
            pass
        return {}

    def _save_credentials(self, email, password):
        try:
            path = self._get_credentials_file()
            with open(path, "w") as f:
                json.dump({"email": email, "password": password}, f)
        except Exception as e:
            print("Could not save credentials:", e)

    def firebase_sign_in(self, email, password):
        """Sign in to Firebase Auth and store the ID token globally."""
        global firebase_id_token
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
        payload = json.dumps({"email": email, "password": password, "returnSecureToken": True}).encode()
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req) as r:
                data = json.loads(r.read().decode())
                firebase_id_token = data.get("idToken")
                return True
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err = json.loads(body).get("error", {}).get("message", "Unknown error")
            except:
                err = body
            return err
        except Exception as e:
            return str(e)

    def verify_login(self):
        email = self.email_entry.get().strip()
        fb_pass = self.fb_pass_entry.get().strip()
        entered_pass = self.pass_entry.get().strip()

        if not email or not fb_pass or not entered_pass:
            self.login_status.config(text="⚠ Please fill in all three fields.")
            return

        # 1. Check master password locally
        entered_hash = hashlib.sha256(entered_pass.encode()).hexdigest()
        if entered_hash != MASTER_PASSWORD_HASH:
            self.login_status.config(text="✕ Incorrect Master Password.")
            self.pass_entry.delete(0, 'end')
            return

        # 2. Sign in to Firebase Auth to get ID token
        self.login_status.config(text="Connecting to Firebase…", foreground="#f5a623")
        self.update()
        result = self.firebase_sign_in(email, fb_pass)
        if result is not True:
            self.login_status.config(text=f"✕ Firebase login failed: {result}", foreground="#ff4d4d")
            return

        # 3. Save credentials locally (never pushed to GitHub)
        self._save_credentials(email, fb_pass)
        self.master_password = entered_pass
        self.login_status.config(text="✓ Signed in successfully!", foreground="#22d46a")
        self.after(600, self.show_main_app)

    def show_main_app(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.current_frame = ttk.Frame(self)
        self.current_frame.pack(expand=True, fill='both')

        # Notebook for Tabs
        self.notebook = ttk.Notebook(self.current_frame)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # Tab 1: Inventory Management
        self.inv_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inv_frame, text="📦 Stock Inventory")
        self.setup_inventory_tab()

        # Tab 2: Record Transaction (Sales/Purchases)
        self.tx_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tx_frame, text="✍️ Record Purchase/Sale")
        self.setup_transactions_tab()

        # Tab 3: Transaction Logs
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="📜 History Logs")
        self.setup_logs_tab()

        # Tab 4: Web Admin Users
        self.users_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.users_frame, text="👥 Web Admins")
        self.setup_users_tab()

        # Tab 5: Shipping & Orders
        self.tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_frame, text="🚚 Tasks & Shipping")
        self.setup_tasks_tab()

    # --- TABS SETUP ---

    def setup_inventory_tab(self):
        # Top frame for selection
        sel_frame = ttk.Frame(self.inv_frame)
        sel_frame.pack(fill='x', pady=10)

        ttk.Label(sel_frame, text="Category:", font=("Segoe UI", 12, "bold")).pack(side='left', padx=10)
        self.inv_cat_cb = ttk.Combobox(sel_frame, values=["Machines", "Toners", "Trays"], state="readonly", width=15)
        self.inv_cat_cb.current(0)
        self.inv_cat_cb.pack(side='left', padx=10)
        self.inv_cat_cb.bind("<<ComboboxSelected>>", lambda e: self.load_inventory())

        ttk.Button(sel_frame, text="🔄 Refresh", command=self.load_inventory).pack(side='right', padx=10)
        ttk.Button(sel_frame, text="➕ Add New Type", command=self.add_inventory_item).pack(side='right', padx=10)
        ttk.Button(sel_frame, text="✏️ Edit Selected", command=self.edit_inventory_item).pack(side='right', padx=10)
        ttk.Button(sel_frame, text="🗑️ Delete Selected", command=self.delete_inventory_item).pack(side='right')

        # Treeview frame
        self.tree_frame = ttk.Frame(self.inv_frame)
        self.tree_frame.pack(expand=True, fill='both', padx=10, pady=10)

        self.inv_tree = ttk.Treeview(self.tree_frame, show="headings")
        self.inv_tree.pack(side='left', expand=True, fill='both')

        scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.inv_tree.yview)
        scroll.pack(side='right', fill='y')
        self.inv_tree.configure(yscrollcommand=scroll.set)

        self.load_inventory()

    def load_inventory(self):
        category = self.inv_cat_cb.get()
        # Clear Treeview
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        # Configure columns
        if category == "Machines":
            columns = ("ID", "Brand", "Model", "Type", "Condition", "Warehouse", "Qty", "Notes", "Trays")
            self.inv_tree["columns"] = columns
            for col in columns:
                self.inv_tree.heading(col, text=col)
                self.inv_tree.column(col, width=100)
            
            try:
                data = FirestoreClient.get_collection("machines")
                for d in data:
                    self.inv_tree.insert("", "end", values=(
                        d.get("id", ""),
                        d.get("brand", "Canon"),
                        d.get("model", ""),
                        d.get("machineType", ""),
                        d.get("condition", ""),
                        d.get("goDown", "g1"),
                        d.get("qty", 0),
                        d.get("notes", ""),
                        d.get("trayCompatibility", "")
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load machines: {e}")

        elif category == "Toners":
            columns = ("ID", "Toner Name", "Compatible Models", "Box Pack Qty", "RC Qty", "Warehouse")
            self.inv_tree["columns"] = columns
            for col in columns:
                self.inv_tree.heading(col, text=col)
                self.inv_tree.column(col, width=150)
            
            try:
                data = FirestoreClient.get_collection("toners")
                for d in data:
                    self.inv_tree.insert("", "end", values=(
                        d.get("id", ""),
                        d.get("tonerName", ""),
                        d.get("compatibleModels", ""),
                        d.get("boxPackQty", 0),
                        d.get("rcQty", 0),
                        d.get("goDown", "g1")
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load toners: {e}")

        elif category == "Trays":
            columns = ("ID", "Model", "Type", "Compatible Models", "Condition", "Qty", "Warehouse")
            self.inv_tree["columns"] = columns
            for col in columns:
                self.inv_tree.heading(col, text=col)
                self.inv_tree.column(col, width=130)
            
            try:
                data = FirestoreClient.get_collection("trays")
                for d in data:
                    self.inv_tree.insert("", "end", values=(
                        d.get("id", ""),
                        d.get("model", ""),
                        d.get("type", ""),
                        d.get("compatibleModel", ""),
                        d.get("condition", ""),
                        d.get("qty", 0),
                        d.get("goDown", "g1")
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load trays: {e}")

    def add_inventory_item(self):
        category = self.inv_cat_cb.get()
        dialog = tk.Toplevel(self)
        dialog.title(f"Add New {category[:-1]}")
        dialog.geometry("400x500")
        dialog.configure(bg="#12131a")
        dialog.transient(self)
        dialog.grab_set()

        entries = {}
        
        # Build form based on category
        if category == "Machines":
            fields = [
                ("Brand", ["Canon", "HP", "Kyocera", "Konica Minolta", "Xerox"]),
                ("Model", "entry"),
                ("Machine Type", ["Black & White", "Color"]),
                ("Condition", ["Box Pack", "RC"]),
                ("Warehouse", "entry"),
                ("Quantity", "entry"),
                ("Tray Compatibility", "entry"),
                ("Notes", "entry")
            ]
        elif category == "Toners":
            fields = [
                ("Toner Name", "entry"),
                ("Compatible Models", "entry"),
                ("Box Pack Qty", "entry"),
                ("RC Qty", "entry"),
                ("Warehouse", "entry")
            ]
        else: # Trays
            fields = [
                ("Model (Name)", "entry"),
                ("Type", ["Two Tray", "Trolley Only", "Other"]),
                ("Compatible Model", "entry"),
                ("Condition", ["Box Pack", "RC"]),
                ("Quantity", "entry"),
                ("Warehouse", "entry")
            ]

        for label, ftype in fields:
            ttk.Label(dialog, text=f"{label}:").pack(pady=(10, 2))
            if isinstance(ftype, list):
                cb = ttk.Combobox(dialog, values=ftype, state="readonly")
                cb.current(0)
                cb.pack()
                entries[label] = cb
            else:
                entry = ttk.Entry(dialog, width=30)
                entry.pack()
                if label == "Warehouse":
                    entry.insert(0, "g1")
                elif label in ["Quantity", "Box Pack Qty", "RC Qty"]:
                    entry.insert(0, "0")
                entries[label] = entry

        def save():
            # Validate and format data
            raw_data = {}
            for k, val in entries.items():
                raw_data[k] = val.get().strip()

            if category == "Machines":
                if not raw_data["Model"]:
                    messagebox.showerror("Error", "Model is required")
                    return
                doc_id = raw_data["Model"].replace(" ", "_").lower()
                data = {
                    "brand": raw_data["Brand"],
                    "model": raw_data["Model"],
                    "machineType": raw_data["Machine Type"],
                    "condition": raw_data["Condition"],
                    "goDown": raw_data["Warehouse"] or "g1",
                    "qty": int(raw_data["Quantity"] or 0),
                    "trayCompatibility": raw_data["Tray Compatibility"],
                    "notes": raw_data["Notes"]
                }
            elif category == "Toners":
                if not raw_data["Toner Name"]:
                    messagebox.showerror("Error", "Toner Name is required")
                    return
                doc_id = raw_data["Toner Name"].replace(" ", "_").lower()
                data = {
                    "tonerName": raw_data["Toner Name"],
                    "compatibleModels": raw_data["Compatible Models"],
                    "boxPackQty": int(raw_data["Box Pack Qty"] or 0),
                    "rcQty": int(raw_data["RC Qty"] or 0),
                    "goDown": raw_data["Warehouse"] or "g1"
                }
            else: # Trays
                if not raw_data["Model (Name)"]:
                    messagebox.showerror("Error", "Model (Name) is required")
                    return
                doc_id = raw_data["Model (Name)"].replace(" ", "_").lower()
                data = {
                    "model": raw_data["Model (Name)"],
                    "type": raw_data["Type"],
                    "compatibleModel": raw_data["Compatible Model"],
                    "condition": raw_data["Condition"],
                    "qty": int(raw_data["Quantity"] or 0),
                    "goDown": raw_data["Warehouse"] or "g1"
                }

            try:
                FirestoreClient.add_document(category.lower(), doc_id, data)
                self.load_inventory()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save item: {e}")

        ttk.Button(dialog, text="Save Item", command=save).pack(pady=20)

    def edit_inventory_item(self):
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an item to edit")
            return
        
        category = self.inv_cat_cb.get()
        item_vals = self.inv_tree.item(selected[0])['values']
        doc_id = item_vals[0]
        
        dialog = tk.Toplevel(self)
        dialog.title(f"Edit {category[:-1]}")
        dialog.geometry("400x500")
        dialog.configure(bg="#12131a")
        dialog.transient(self)
        dialog.grab_set()

        entries = {}
        
        # Build form with pre-filled values
        if category == "Machines":
            fields = [
                ("Brand", ["Canon", "HP", "Kyocera", "Konica Minolta", "Xerox"], item_vals[1]),
                ("Model", "entry", item_vals[2]),
                ("Machine Type", ["Black & White", "Color"], item_vals[3]),
                ("Condition", ["Box Pack", "RC"], item_vals[4]),
                ("Warehouse", "entry", item_vals[5]),
                ("Quantity", "entry", item_vals[6]),
                ("Tray Compatibility", "entry", item_vals[8]),
                ("Notes", "entry", item_vals[7])
            ]
        elif category == "Toners":
            fields = [
                ("Toner Name", "entry", item_vals[1]),
                ("Compatible Models", "entry", item_vals[2]),
                ("Box Pack Qty", "entry", item_vals[3]),
                ("RC Qty", "entry", item_vals[4]),
                ("Warehouse", "entry", item_vals[5])
            ]
        else: # Trays
            fields = [
                ("Model (Name)", "entry", item_vals[1]),
                ("Type", ["Two Tray", "Trolley Only", "Other"], item_vals[2]),
                ("Compatible Model", "entry", item_vals[3]),
                ("Condition", ["Box Pack", "RC"], item_vals[4]),
                ("Quantity", "entry", item_vals[5]),
                ("Warehouse", "entry", item_vals[6])
            ]

        for item in fields:
            label = item[0]
            ftype = item[1]
            curr_val = item[2]
            
            ttk.Label(dialog, text=f"{label}:").pack(pady=(10, 2))
            if isinstance(ftype, list):
                cb = ttk.Combobox(dialog, values=ftype, state="readonly")
                try:
                    cb.current(ftype.index(curr_val))
                except:
                    cb.current(0)
                cb.pack()
                entries[label] = cb
            else:
                entry = ttk.Entry(dialog, width=30)
                entry.pack()
                entry.insert(0, str(curr_val))
                entries[label] = entry

        def save():
            raw_data = {}
            for k, val in entries.items():
                raw_data[k] = val.get().strip()

            if category == "Machines":
                data = {
                    "brand": raw_data["Brand"],
                    "model": raw_data["Model"],
                    "machineType": raw_data["Machine Type"],
                    "condition": raw_data["Condition"],
                    "goDown": raw_data["Warehouse"],
                    "qty": int(raw_data["Quantity"] or 0),
                    "trayCompatibility": raw_data["Tray Compatibility"],
                    "notes": raw_data["Notes"]
                }
            elif category == "Toners":
                data = {
                    "tonerName": raw_data["Toner Name"],
                    "compatibleModels": raw_data["Compatible Models"],
                    "boxPackQty": int(raw_data["Box Pack Qty"] or 0),
                    "rcQty": int(raw_data["RC Qty"] or 0),
                    "goDown": raw_data["Warehouse"]
                }
            else: # Trays
                data = {
                    "model": raw_data["Model (Name)"],
                    "type": raw_data["Type"],
                    "compatibleModel": raw_data["Compatible Model"],
                    "condition": raw_data["Condition"],
                    "qty": int(raw_data["Quantity"] or 0),
                    "goDown": raw_data["Warehouse"]
                }

            try:
                FirestoreClient.update_document(category.lower(), doc_id, data)
                self.load_inventory()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update item: {e}")

        ttk.Button(dialog, text="Save Changes", command=save).pack(pady=20)

    def delete_inventory_item(self):
        selected = self.inv_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an item to delete")
            return
        
        category = self.inv_cat_cb.get()
        item_vals = self.inv_tree.item(selected[0])['values']
        doc_id = item_vals[0]
        name = item_vals[1] if category == "Toners" else item_vals[2]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {category[:-1]} '{name}'?"):
            try:
                FirestoreClient.delete_document(category.lower(), doc_id)
                self.load_inventory()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete item: {e}")

    # --- TRANSACTIONS TAB ---

    def setup_transactions_tab(self):
        # Grid frame
        grid_frame = ttk.Frame(self.tx_frame, padding=20)
        grid_frame.pack(expand=True, fill='both')

        # Type of Transaction (Sale / Purchase)
        ttk.Label(grid_frame, text="Transaction Type:", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky='w', pady=10)
        self.tx_type_var = tk.StringVar(value="Purchase")
        ttk.Radiobutton(grid_frame, text="📥 Purchase (Add Stock)", variable=self.tx_type_var, value="Purchase", command=self.on_tx_type_change).grid(row=0, column=1, sticky='w', pady=10)
        ttk.Radiobutton(grid_frame, text="📤 Sale (Remove Stock)", variable=self.tx_type_var, value="Sale", command=self.on_tx_type_change).grid(row=0, column=2, sticky='w', pady=10)

        # Category of Item
        ttk.Label(grid_frame, text="Item Category:", font=("Segoe UI", 12, "bold")).grid(row=1, column=0, sticky='w', pady=10)
        self.tx_cat_var = tk.StringVar(value="Machines")
        self.tx_cat_cb = ttk.Combobox(grid_frame, values=["Machines", "Toners", "Trays"], state="readonly", textvariable=self.tx_cat_var)
        self.tx_cat_cb.current(0)
        self.tx_cat_cb.grid(row=1, column=1, columnspan=2, sticky='w', pady=10)
        self.tx_cat_cb.bind("<<ComboboxSelected>>", lambda e: self.populate_tx_items())

        # Select Item
        ttk.Label(grid_frame, text="Select Item Model:", font=("Segoe UI", 12, "bold")).grid(row=2, column=0, sticky='w', pady=10)
        self.tx_item_cb = ttk.Combobox(grid_frame, state="readonly", width=40)
        self.tx_item_cb.grid(row=2, column=1, columnspan=2, sticky='w', pady=10)

        # Quantity
        ttk.Label(grid_frame, text="Quantity:", font=("Segoe UI", 12, "bold")).grid(row=3, column=0, sticky='w', pady=10)
        self.tx_qty_entry = ttk.Entry(grid_frame, width=15)
        self.tx_qty_entry.insert(0, "1")
        self.tx_qty_entry.grid(row=3, column=1, sticky='w', pady=10)

        # Dynamic parameter: Import Country / Party Name
        self.tx_party_label = ttk.Label(grid_frame, text="Imported From (Country):", font=("Segoe UI", 12, "bold"))
        self.tx_party_label.grid(row=4, column=0, sticky='w', pady=10)
        
        self.tx_country_cb = ttk.Combobox(grid_frame, values=["Korea", "USA", "Local", "Other"], state="readonly")
        self.tx_country_cb.current(0)
        self.tx_country_cb.grid(row=4, column=1, sticky='w', pady=10)

        self.tx_party_entry = ttk.Entry(grid_frame, width=30)
        
        # Date
        ttk.Label(grid_frame, text="Transaction Date:", font=("Segoe UI", 12, "bold")).grid(row=5, column=0, sticky='w', pady=10)
        self.tx_date_entry = ttk.Entry(grid_frame, width=20)
        self.tx_date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        self.tx_date_entry.grid(row=5, column=1, sticky='w', pady=10)

        # Price/Notes
        ttk.Label(grid_frame, text="Price / Notes:", font=("Segoe UI", 12, "bold")).grid(row=6, column=0, sticky='w', pady=10)
        self.tx_price_entry = ttk.Entry(grid_frame, width=40)
        self.tx_price_entry.grid(row=6, column=1, columnspan=2, sticky='w', pady=10)

        # Submit Button
        ttk.Button(grid_frame, text="💾 Save Transaction", command=self.save_transaction).grid(row=7, column=0, columnspan=3, pady=30)

        self.populate_tx_items()

    def on_tx_type_change(self):
        txtype = self.tx_type_var.get()
        if txtype == "Purchase":
            self.tx_party_label.config(text="Imported From (Country):")
            self.tx_party_entry.grid_forget()
            self.tx_country_cb.grid(row=4, column=1, sticky='w', pady=10)
        else:
            self.tx_party_label.config(text="Sold To (Party Name):")
            self.tx_country_cb.grid_forget()
            self.tx_party_entry.grid(row=4, column=1, sticky='w', pady=10)

    def populate_tx_items(self):
        cat = self.tx_cat_var.get()
        try:
            self.tx_items_list = FirestoreClient.get_collection(cat.lower())
            vals = []
            for item in self.tx_items_list:
                if cat == "Machines":
                    vals.append(f"{item.get('brand')} {item.get('model')} ({item.get('condition')})")
                elif cat == "Toners":
                    vals.append(item.get('tonerName'))
                else: # Trays
                    vals.append(f"{item.get('model')} ({item.get('type')}) - {item.get('condition')}")
            self.tx_item_cb["values"] = vals
            if vals:
                self.tx_item_cb.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch items list: {e}")

    def save_transaction(self):
        txtype = self.tx_type_var.get()
        cat = self.tx_cat_var.get()
        item_index = self.tx_item_cb.current()
        
        if item_index < 0:
            messagebox.showerror("Error", "Please select an item")
            return
        
        selected_item = self.tx_items_list[item_index]
        qty = int(self.tx_qty_entry.get().strip() or 0)
        date = self.tx_date_entry.get().strip()
        price_notes = self.tx_price_entry.get().strip()
        
        if qty <= 0:
            messagebox.showerror("Error", "Quantity must be greater than zero")
            return

        tx_id = f"tx_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(10,99)}"
        
        # Build transaction log object
        tx_data = {
            "date": date,
            "qty": qty,
            "price": price_notes
        }

        # 1. Update the appropriate stock quantity in Firestore
        updated_inv_data = {}
        if cat == "Machines":
            curr_qty = selected_item.get("qty", 0)
            new_qty = (curr_qty + qty) if txtype == "Purchase" else (curr_qty - qty)
            if new_qty < 0:
                messagebox.showerror("Error", "Not enough stock in inventory to complete this sale")
                return
            updated_inv_data["qty"] = new_qty
            tx_data["machineId"] = selected_item["id"]
            tx_data["model"] = selected_item.get("model")
            
        elif cat == "Toners":
            # For toners, sales/purchases can be Box Pack or RC. Let's ask via a dialog
            tone_cond = messagebox.askyesno("Toner Condition", "Is this Box Pack? (Yes = Box Pack, No = RC)")
            cond_key = "boxPackQty" if tone_cond else "rcQty"
            curr_qty = selected_item.get(cond_key, 0)
            new_qty = (curr_qty + qty) if txtype == "Purchase" else (curr_qty - qty)
            if new_qty < 0:
                messagebox.showerror("Error", f"Not enough {cond_key} stock in inventory")
                return
            updated_inv_data[cond_key] = new_qty
            tx_data["tonerId"] = selected_item["id"]
            tx_data["tonerName"] = selected_item.get("tonerName")
            tx_data["condition"] = "Box Pack" if tone_cond else "RC"
            
        else: # Trays
            curr_qty = selected_item.get("qty", 0)
            new_qty = (curr_qty + qty) if txtype == "Purchase" else (curr_qty - qty)
            if new_qty < 0:
                messagebox.showerror("Error", "Not enough stock in inventory to complete this sale")
                return
            updated_inv_data["qty"] = new_qty
            tx_data["trayId"] = selected_item["id"]
            tx_data["model"] = selected_item.get("model")

        # Set Party or Country
        if txtype == "Purchase":
            tx_data["fromCountry"] = self.tx_country_cb.get()
        else:
            tx_data["toParty"] = self.tx_party_entry.get().strip()

        # Collection name for Logs
        col_suffix = "Purchases" if txtype == "Purchase" else "Sales"
        log_col = f"{cat[:-1].lower()}{col_suffix}" # machinePurchases, machineSales, etc.

        try:
            # 2. Add log entry
            FirestoreClient.add_document(log_col, tx_id, tx_data)
            # 3. Update inventory
            FirestoreClient.update_document(cat.lower(), selected_item["id"], updated_inv_data)
            
            messagebox.showinfo("Success", f"Transaction recorded successfully and stock updated to {new_qty}!")
            self.load_inventory()
            self.load_logs()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute transaction: {e}")

    # --- HISTORY LOGS TAB ---

    def setup_logs_tab(self):
        top_frame = ttk.Frame(self.logs_frame)
        top_frame.pack(fill='x', pady=10)

        ttk.Label(top_frame, text="Log Collection:", font=("Segoe UI", 12, "bold")).pack(side='left', padx=10)
        self.log_type_cb = ttk.Combobox(top_frame, values=[
            "Machine Purchases", "Machine Sales",
            "Toner Purchases", "Toner Sales",
            "Tray Purchases", "Tray Sales"
        ], state="readonly", width=20)
        self.log_type_cb.current(0)
        self.log_type_cb.pack(side='left', padx=10)
        self.log_type_cb.bind("<<ComboboxSelected>>", lambda e: self.load_logs())

        ttk.Button(top_frame, text="🔄 Refresh", command=self.load_logs).pack(side='right', padx=10)

        # Table
        self.log_tree_frame = ttk.Frame(self.logs_frame)
        self.log_tree_frame.pack(expand=True, fill='both', padx=10, pady=10)

        self.log_tree = ttk.Treeview(self.log_tree_frame, show="headings")
        self.log_tree.pack(side='left', expand=True, fill='both')

        scroll = ttk.Scrollbar(self.log_tree_frame, orient="vertical", command=self.log_tree.yview)
        scroll.pack(side='right', fill='y')
        self.log_tree.configure(yscrollcommand=scroll.set)

        self.load_logs()

    def load_logs(self):
        selected = self.log_type_cb.get()
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        # Format collection ID
        # "Machine Purchases" -> "machinePurchases"
        parts = selected.split()
        col_name = f"{parts[0].lower()[:-1]}{parts[1]}"
        if parts[0] == "Trays":
            col_name = f"tray{parts[1]}"
            
        columns = ("Date", "ID", "Item Model/Name", "Qty", "Price/Notes", "Source/Destination")
        self.log_tree["columns"] = columns
        for col in columns:
            self.log_tree.heading(col, text=col)
            self.log_tree.column(col, width=120)

        try:
            logs = FirestoreClient.get_collection(col_name)
            # Sort by date descending
            logs = sorted(logs, key=lambda x: x.get('date', ''), reverse=True)
            for l in logs:
                item_name = l.get("model", l.get("tonerName", l.get("trayId", "")))
                source_dest = l.get("fromCountry", l.get("toParty", "N/A"))
                self.log_tree.insert("", "end", values=(
                    l.get("date", ""),
                    l.get("id", ""),
                    item_name,
                    l.get("qty", 0),
                    l.get("price", ""),
                    source_dest
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load logs: {e}")

    # --- WEB USERS TAB ---

    def setup_users_tab(self):
        top_frame = ttk.Frame(self.users_frame)
        top_frame.pack(fill='x', pady=10)

        ttk.Label(top_frame, text="Manage Website Admin Accounts", font=("Segoe UI", 14, "bold")).pack(side='left', padx=10)
        ttk.Button(top_frame, text="🔄 Refresh", command=self.load_users).pack(side='right', padx=10)
        ttk.Button(top_frame, text="➕ Add New Account", command=self.add_user).pack(side='right', padx=10)
        ttk.Button(top_frame, text="🔑 Change Master Password", command=self.change_master_password).pack(side='right', padx=10)

        columns = ("Username / Email", "Password", "Created")
        self.users_tree = ttk.Treeview(self.users_frame, columns=columns, show='headings')
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=180)
        self.users_tree.pack(expand=True, fill='both', padx=10, pady=10)

        bottom_frame = ttk.Frame(self.users_frame)
        bottom_frame.pack(fill='x', pady=10)
        ttk.Button(bottom_frame, text="🗑️ Remove Selected Account", command=self.remove_user).pack(side='left', padx=10)
        ttk.Label(bottom_frame, text="Passwords shown are decrypted using your master password and are stored securely in Firebase.",
                  font=("Segoe UI", 8), foreground="#454d6e").pack(side='left', padx=10)

        self.load_users()

    def load_users(self):
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        try:
            users = FirestoreClient.get_collection("adminUsers")
            for u in users:
                # Decrypt password for display using master password
                ciphertext = u.get('passwordEncrypted', '')
                if ciphertext and hasattr(self, 'master_password'):
                    display_pw = decrypt_password(ciphertext, self.master_password)
                else:
                    display_pw = u.get('password', '(encrypted)')
                self.users_tree.insert('', 'end', values=(
                    u.get('username', u['id']),
                    display_pw,
                    u.get('createdAt', 'N/A')
                ))
        except Exception as e:
            messagebox.showerror("Network Error", f"Failed to load users: {e}")

    def firebase_create_user(self, email, password):
        """Create a user in Firebase Authentication."""
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
        payload = json.dumps({"email": email, "password": password, "returnSecureToken": False}).encode()
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req) as r:
                data = json.loads(r.read().decode())
                return data.get("localId"), None
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err = json.loads(body).get("error", {}).get("message", "Unknown error")
            except:
                err = body
            return None, err

    def firebase_delete_user(self, uid):
        """Delete a user from Firebase Authentication by UID."""
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:delete?key={API_KEY}"
        payload = json.dumps({"idToken": firebase_id_token, "localId": uid}).encode()
        # Use Admin-style deletion via ID token if available
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req) as r:
                return True, None
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                err = json.loads(body).get("error", {}).get("message", "")
            except:
                err = body
            return False, err

    def add_user(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add New Web Admin")
        dialog.geometry("340x280")
        dialog.configure(bg="#12131a")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Email (used for login):").pack(pady=(15, 2))
        email_entry = ttk.Entry(dialog, width=32)
        email_entry.pack()

        ttk.Label(dialog, text="Password:").pack(pady=(10, 2))
        password_entry = ttk.Entry(dialog, width=32)
        password_entry.pack()

        status_label = ttk.Label(dialog, text="", foreground="#ff4d4d", font=("Segoe UI", 9))
        status_label.pack(pady=(5, 0))

        def save():
            user_email = email_entry.get().strip()
            pw = password_entry.get().strip()
            if not user_email or not pw:
                status_label.config(text="All fields required")
                return
            if len(pw) < 6:
                status_label.config(text="Password must be at least 6 characters")
                return

            status_label.config(text="Creating user…", foreground="#f5a623")
            dialog.update()

            # Create user in Firebase Authentication
            uid, err = self.firebase_create_user(user_email, pw)
            if err:
                status_label.config(text=f"Auth error: {err}", foreground="#ff4d4d")
                return

            # Compute hash (for web login) and encrypt (for display in controller)
            pw_hash = hashlib.sha256(pw.encode()).hexdigest()
            pw_enc = encrypt_password(pw, self.master_password)
            username = user_email.split('@')[0]  # use email prefix as display name

            data = {
                "username": user_email,
                "passwordHash": pw_hash,
                "passwordEncrypted": pw_enc,
                "uid": uid or "",
                "createdAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            try:
                FirestoreClient.add_document("adminUsers", username, data)
                status_label.config(text="✓ User created!", foreground="#22d46a")
                self.load_users()
                dialog.after(800, dialog.destroy)
            except Exception as e:
                status_label.config(text=f"Firestore error: {e}", foreground="#ff4d4d")

        ttk.Button(dialog, text="Create User", command=save).pack(pady=15)

    def remove_user(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a user to remove")
            return

        item = self.users_tree.item(selected[0])
        username = item['values'][0]

        if messagebox.askyesno("Confirm", f"Permanently remove '{username}'?\n\nThis will instantly revoke their web app access."):
            try:
                # Fetch the UID from Firestore record so we can delete from Firebase Auth too
                users = FirestoreClient.get_collection("adminUsers")
                target = next((u for u in users if u.get('username') == username or u.get('id') == username), None)
                uid = target.get('uid', '') if target else ''

                # Delete from Firestore (web app detects this and force-logs them out)
                doc_id = username.split('@')[0] if '@' in username else username
                FirestoreClient.delete_document("adminUsers", doc_id)

                # Also delete from Firebase Authentication if UID is known
                if uid:
                    self.firebase_delete_user(uid)

                messagebox.showinfo("Removed", f"User '{username}' has been removed.\nThey will be logged out instantly from the web app.")
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

    def change_master_password(self):
        dialog = tk.Toplevel(self)
        dialog.title("Change Master Password")
        dialog.geometry("350x280")
        dialog.configure(bg="#12131a")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Current Master Password:").pack(pady=(15, 2))
        curr_entry = ttk.Entry(dialog, show="*")
        curr_entry.pack()

        ttk.Label(dialog, text="New Master Password:").pack(pady=(10, 2))
        new_entry = ttk.Entry(dialog, show="*")
        new_entry.pack()

        ttk.Label(dialog, text="Confirm New Password:").pack(pady=(10, 2))
        confirm_entry = ttk.Entry(dialog, show="*")
        confirm_entry.pack()

        def save():
            curr_pw = curr_entry.get().strip()
            new_pw = new_entry.get().strip()
            conf_pw = confirm_entry.get().strip()

            if curr_pw != self.master_password:
                messagebox.showerror("Error", "Current master password incorrect")
                return
            if not new_pw:
                messagebox.showerror("Error", "New password cannot be empty")
                return
            if new_pw != conf_pw:
                messagebox.showerror("Error", "New passwords do not match")
                return

            try:
                # Re-encrypt all user passwords with the new master password key
                users = FirestoreClient.get_collection("adminUsers")
                for u in users:
                    ciphertext = u.get('passwordEncrypted', '')
                    if ciphertext:
                        decrypted = decrypt_password(ciphertext, curr_pw)
                    else:
                        decrypted = u.get('password', '')
                    if decrypted and decrypted != "Decryption Error":
                        new_enc = encrypt_password(decrypted, new_pw)
                        doc_id = u.get('username', u['id']).split('@')[0] if '@' in u.get('username', '') else u.get('id', '')
                        FirestoreClient.update_document("adminUsers", doc_id, {"passwordEncrypted": new_enc})

                # Save new master hash to Firestore
                new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
                FirestoreClient.add_document("systemConfig", "auth", {"masterHash": new_hash})

                self.master_password = new_pw
                messagebox.showinfo("Success", "Master password updated and all accounts re-encrypted!")
                self.load_users()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update master password: {e}")

        ttk.Button(dialog, text="Update Password", command=save).pack(pady=20)

    # --- TASKS & SHIPPING TAB ---

    def setup_tasks_tab(self):
        # Two sub panels
        left_panel = ttk.LabelFrame(self.tasks_frame, text="🚚 Shipping Tasks (shippingTodos)", padding=10)
        left_panel.pack(side='left', expand=True, fill='both', padx=5, pady=5)

        right_panel = ttk.LabelFrame(self.tasks_frame, text="🛒 Purchase Order Tasks (orderTodos)", padding=10)
        right_panel.pack(side='right', expand=True, fill='both', padx=5, pady=5)

        # Shipping Tasks layout
        columns_ship = ("ID", "Party Name", "Model", "Qty", "Status")
        self.ship_tree = ttk.Treeview(left_panel, columns=columns_ship, show='headings')
        for col in columns_ship:
            self.ship_tree.heading(col, text=col)
            self.ship_tree.column(col, width=90)
        self.ship_tree.pack(expand=True, fill='both')

        ship_btns = ttk.Frame(left_panel)
        ship_btns.pack(fill='x', pady=5)
        ttk.Button(ship_btns, text="✔️ Mark Shipped", command=self.complete_shipping_task).pack(side='left', padx=5)
        ttk.Button(ship_btns, text="❌ Delete Task", command=self.delete_shipping_task).pack(side='left')

        # Order Tasks layout
        columns_order = ("ID", "Customer Name", "Machine Model", "Toner Model", "Qty", "Status")
        self.order_tree = ttk.Treeview(right_panel, columns=columns_order, show='headings')
        for col in columns_order:
            self.order_tree.heading(col, text=col)
            self.order_tree.column(col, width=80)
        self.order_tree.pack(expand=True, fill='both')

        order_btns = ttk.Frame(right_panel)
        order_btns.pack(fill='x', pady=5)
        ttk.Button(order_btns, text="✔️ Complete Order", command=self.complete_order_task).pack(side='left', padx=5)
        ttk.Button(order_btns, text="❌ Cancel Order", command=self.delete_order_task).pack(side='left')

        # Load both
        self.load_tasks()

    def load_tasks(self):
        for item in self.ship_tree.get_children():
            self.ship_tree.delete(item)
        for item in self.order_tree.get_children():
            self.order_tree.delete(item)

        try:
            shipping = FirestoreClient.get_collection("shippingTodos")
            for s in shipping:
                self.ship_tree.insert("", "end", values=(
                    s.get("id", ""),
                    s.get("partyName", ""),
                    s.get("model", ""),
                    s.get("qty", 0),
                    s.get("status", "Pending")
                ))
            
            orders = FirestoreClient.get_collection("orderTodos")
            for o in orders:
                self.order_tree.insert("", "end", values=(
                    o.get("id", ""),
                    o.get("customerName", ""),
                    o.get("machineModel", ""),
                    o.get("tonerModel", ""),
                    o.get("qty", 0),
                    o.get("status", "Pending")
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tasks: {e}")

    def complete_shipping_task(self):
        selected = self.ship_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a shipping task")
            return
        task = self.ship_tree.item(selected[0])['values']
        task_id = task[0]
        
        # Complete by adding to shippingInfo and updating status to Shipped
        try:
            FirestoreClient.update_document("shippingTodos", task_id, {"status": "Shipped"})
            # Also add to shippingInfo (history)
            ship_info = {
                "id": task_id,
                "partyName": task[1],
                "model": task[2],
                "qty": int(task[3]),
                "status": "Shipped",
                "shippedDate": datetime.date.today().strftime("%Y-%m-%d")
            }
            FirestoreClient.add_document("shippingInfo", task_id, ship_info)
            messagebox.showinfo("Success", "Task marked as Shipped!")
            self.load_tasks()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update task: {e}")

    def delete_shipping_task(self):
        selected = self.ship_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a task to delete")
            return
        task_id = self.ship_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", "Delete this shipping task?"):
            try:
                FirestoreClient.delete_document("shippingTodos", task_id)
                self.load_tasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

    def complete_order_task(self):
        selected = self.order_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an order task")
            return
        task = self.order_tree.item(selected[0])['values']
        task_id = task[0]
        
        try:
            FirestoreClient.update_document("orderTodos", task_id, {"status": "Completed"})
            order_info = {
                "id": task_id,
                "customerName": task[1],
                "machineModel": task[2],
                "tonerModel": task[3],
                "qty": int(task[4]),
                "status": "Completed",
                "completedDate": datetime.date.today().strftime("%Y-%m-%d")
            }
            FirestoreClient.add_document("orderHistory", task_id, order_info)
            messagebox.showinfo("Success", "Order marked as Completed!")
            self.load_tasks()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update order: {e}")

    def delete_order_task(self):
        selected = self.order_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select an order to cancel/delete")
            return
        task_id = self.order_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", "Cancel and delete this order?"):
            try:
                FirestoreClient.delete_document("orderTodos", task_id)
                self.load_tasks()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

if __name__ == "__main__":
    app = AdminCommanderApp()
    app.mainloop()
