import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import urllib.request
import urllib.error
import json
import datetime

PROJECT_ID = "stock-manager-70efc"
API_KEY = "AIzaSyBt3Q4K0mFtP2xGvHnJkLdR7sBqEuWwYM"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
MASTER_PASSWORD = "Yamunaji_0791"

class FirestoreClient:
    @staticmethod
    def get_collection(collection_name):
        try:
            req = urllib.request.Request(f"{BASE_URL}/{collection_name}?key={API_KEY}")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                docs = []
                for doc in data.get('documents', []):
                    # extract fields
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
        try:
            with urllib.request.urlopen(req) as response:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 409: # Already exists, we need to PATCH
                url = f"{BASE_URL}/{collection_name}/{doc_id}?key={API_KEY}"
                req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='PATCH')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req) as response:
                    return True
            raise e

    @staticmethod
    def delete_document(collection_name, doc_id):
        url = f"{BASE_URL}/{collection_name}/{doc_id}?key={API_KEY}"
        req = urllib.request.Request(url, method='DELETE')
        try:
            with urllib.request.urlopen(req) as response:
                return True
        except Exception as e:
            print(f"Error deleting: {e}")
            return False

class AdminCommanderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Yamunaji Admin Commander")
        self.geometry("800x600")
        self.configure(bg="#1e1e1e")
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('.', background='#1e1e1e', foreground='#ffffff')
        self.style.configure('TFrame', background='#1e1e1e')
        self.style.configure('TLabel', background='#1e1e1e', foreground='#ffffff', font=('Segoe UI', 10))
        self.style.configure('TButton', background='#333333', foreground='#ffffff', borderwidth=0, padding=6)
        self.style.map('TButton', background=[('active', '#444444')])
        self.style.configure('Treeview', background='#2d2d2d', foreground='#ffffff', fieldbackground='#2d2d2d', borderwidth=0)
        self.style.map('Treeview', background=[('selected', '#0078d7')])
        self.style.configure('Treeview.Heading', background='#333333', foreground='#ffffff', font=('Segoe UI', 10, 'bold'))

        self.current_frame = None
        self.show_login_screen()

    def show_login_screen(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.current_frame = ttk.Frame(self)
        self.current_frame.pack(expand=True, fill='both')

        login_box = ttk.Frame(self.current_frame, padding=40)
        login_box.place(relx=0.5, rely=0.5, anchor='center')

        ttk.Label(login_box, text="🖨️", font=("Segoe UI", 40)).pack(pady=(0, 10))
        ttk.Label(login_box, text="Yamunaji Commander", font=("Segoe UI", 18, "bold")).pack(pady=(0, 5))
        ttk.Label(login_box, text="Enter Master Password to access").pack(pady=(0, 20))

        self.pass_entry = ttk.Entry(login_box, show="*", width=30, font=("Segoe UI", 12))
        self.pass_entry.pack(pady=10)
        self.pass_entry.bind("<Return>", lambda e: self.verify_login())

        btn = ttk.Button(login_box, text="Unlock →", command=self.verify_login)
        btn.pack(pady=10, fill='x')

    def verify_login(self):
        if self.pass_entry.get() == MASTER_PASSWORD:
            self.show_main_app()
        else:
            messagebox.showerror("Error", "Incorrect Master Password")
            self.pass_entry.delete(0, 'end')

    def show_main_app(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.current_frame = ttk.Frame(self)
        self.current_frame.pack(expand=True, fill='both')

        # Notebook for tabs
        notebook = ttk.Notebook(self.current_frame)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # Users Tab
        users_frame = ttk.Frame(notebook)
        notebook.add(users_frame, text="👥 Web Users")
        self.setup_users_tab(users_frame)

        # Inventory Tab
        inventory_frame = ttk.Frame(notebook)
        notebook.add(inventory_frame, text="🖨️ Inventory Status")
        self.setup_inventory_tab(inventory_frame)

    def setup_users_tab(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill='x', pady=10)

        ttk.Label(top_frame, text="Manage Website Admins", font=("Segoe UI", 14, "bold")).pack(side='left', padx=10)
        ttk.Button(top_frame, text="🔄 Refresh", command=self.load_users).pack(side='right', padx=10)
        ttk.Button(top_frame, text="➕ Add User", command=self.add_user).pack(side='right')

        # Table
        columns = ("Username", "Password", "Created")
        self.users_tree = ttk.Treeview(parent, columns=columns, show='headings')
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=150)
        self.users_tree.pack(expand=True, fill='both', padx=10, pady=10)

        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill='x', pady=10)
        ttk.Button(bottom_frame, text="🗑️ Remove Selected User", command=self.remove_user).pack(side='left', padx=10)

        self.load_users()

    def load_users(self):
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        try:
            users = FirestoreClient.get_collection("adminUsers")
            for u in users:
                self.users_tree.insert('', 'end', values=(u.get('username', u['id']), u.get('password', '***'), u.get('createdAt', 'N/A')))
        except Exception as e:
            messagebox.showerror("Network Error", f"Failed to load users: {e}")

    def add_user(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add New User")
        dialog.geometry("300x200")
        dialog.configure(bg="#1e1e1e")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Username:").pack(pady=(15, 5))
        username_entry = ttk.Entry(dialog)
        username_entry.pack()

        ttk.Label(dialog, text="Password:").pack(pady=(15, 5))
        password_entry = ttk.Entry(dialog)
        password_entry.pack()

        def save():
            user = username_entry.get().strip()
            pw = password_entry.get().strip()
            if not user or not pw:
                messagebox.showerror("Error", "All fields required")
                return
            
            data = {
                "username": user,
                "password": pw,
                "createdAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            try:
                FirestoreClient.add_document("adminUsers", user, data)
                self.load_users()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add user: {e}")

        ttk.Button(dialog, text="Save", command=save).pack(pady=20)

    def remove_user(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a user to remove")
            return
        
        item = self.users_tree.item(selected[0])
        username = item['values'][0]
        
        if messagebox.askyesno("Confirm", f"Remove user '{username}' permanently?"):
            try:
                FirestoreClient.delete_document("adminUsers", username)
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

    def setup_inventory_tab(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill='x', pady=10)

        ttk.Label(top_frame, text="Quick Inventory Overview", font=("Segoe UI", 14, "bold")).pack(side='left', padx=10)
        ttk.Button(top_frame, text="🔄 Refresh", command=self.load_inventory).pack(side='right', padx=10)

        self.inv_text = tk.Text(parent, bg="#2d2d2d", fg="#ffffff", font=("Consolas", 12), borderwidth=0)
        self.inv_text.pack(expand=True, fill='both', padx=10, pady=10)

        self.load_inventory()

    def load_inventory(self):
        self.inv_text.delete(1.0, tk.END)
        self.inv_text.insert(tk.END, "Loading from Firebase...\n")
        self.update_idletasks()
        
        try:
            machines = FirestoreClient.get_collection("machines")
            toners = FirestoreClient.get_collection("toners")
            trays = FirestoreClient.get_collection("trays")
            
            self.inv_text.delete(1.0, tk.END)
            self.inv_text.insert(tk.END, f"--- MACHINES ({len(machines)}) ---\n")
            for m in machines:
                self.inv_text.insert(tk.END, f"{m.get('model', 'Unknown')} | {m.get('machineType', '')} | Qty: {m.get('qty', 0)}\n")
                
            self.inv_text.insert(tk.END, f"\n--- TONERS ({len(toners)}) ---\n")
            for t in toners:
                self.inv_text.insert(tk.END, f"{t.get('tonerName', 'Unknown')} | Qty: {t.get('qty', 0)}\n")

            self.inv_text.insert(tk.END, f"\n--- TRAYS ({len(trays)}) ---\n")
            for t in trays:
                self.inv_text.insert(tk.END, f"{t.get('model', 'Unknown')} ({t.get('type', '')}) | Qty: {t.get('qty', 0)}\n")

        except Exception as e:
            self.inv_text.insert(tk.END, f"\nError loading inventory: {e}")

if __name__ == "__main__":
    app = AdminCommanderApp()
    app.mainloop()
