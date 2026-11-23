
import sqlite3, os, sys, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

BASE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
DB = os.path.join(BASE, "goals.db")
FMT = "%d.%m.%Y %H:%M"
STATUSES = ["Создана", "Активна", "Завершена", "Отменена"]

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys=ON")
con.executescript("""
CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
 descr TEXT DEFAULT '', deadline TEXT, status TEXT DEFAULT 'Создана', archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,
 goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE, name TEXT NOT NULL,
 deadline TEXT, done INTEGER DEFAULT 0, done_at TEXT);
""")
con.commit()

def parse(s):
    s = s.strip()
    if not s: return None
    return datetime.strptime(s, FMT)

def iso(s):
    d = parse(s)
    return d.isoformat() if d else None

def show(iso_s):
    return datetime.fromisoformat(iso_s).strftime(FMT) if iso_s else ""

class Dialog(tk.Toplevel):
    def __init__(self, parent, title, fields, values=None, multiline=None, combo=None):
        super().__init__(parent); self.title(title); self.result = None
        self.transient(parent); self.grab_set(); self.resizable(False, False)
        self.w = {}; values = values or {}
        for i, (key, label) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="nw", padx=10, pady=6)
            if key == multiline:
                w = tk.Text(self, width=40, height=5, font=("Segoe UI", 10)); w.insert("1.0", values.get(key, ""))
            elif key == combo:
                w = ttk.Combobox(self, values=STATUSES, state="readonly", width=38); w.set(values.get(key, STATUSES[0]))
            else:
                w = ttk.Entry(self, width=42); w.insert(0, values.get(key, ""))
            w.grid(row=i, column=1, padx=10, pady=6); self.w[key] = w
        self.multiline = multiline
        ttk.Label(self, text="Формат срока: ДД.ММ.ГГГГ ЧЧ:ММ", foreground="#777").grid(row=len(fields), column=1, sticky="w", padx=10)
        b = ttk.Frame(self); b.grid(row=len(fields)+1, column=0, columnspan=2, pady=10)
        ttk.Button(b, text="Сохранить", style="Accent.TButton", command=self.ok).pack(side="left", padx=5)
        ttk.Button(b, text="Отмена", command=self.destroy).pack(side="left", padx=5)
        self.wait_window()
    def ok(self):
        r = {}
        for k, w in self.w.items():
            r[k] = w.get("1.0", "end").strip() if k == self.multiline else w.get().strip()
        if not r.get("name"): messagebox.showerror("Ошибка", "Введите наименование", parent=self); return
        if "deadline" in r:
            try: parse(r["deadline"])
            except ValueError: messagebox.showerror("Ошибка", "Неверный формат срока", parent=self); return
        self.result = r; self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Цель. Код будущего"); self.geometry("1100x680"); self.minsize(900, 560)
        self.configure(bg="#f4f6fb")
        st = ttk.Style(self); st.theme_use("clam")
        st.configure("TFrame", background="#f4f6fb"); st.configure("TLabel", background="#f4f6fb", font=("Segoe UI", 10))
        st.configure("H.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1f3a8a")
        st.configure("TButton", font=("Segoe UI", 10), padding=6)
        st.configure("Accent.TButton", background="#2563eb", foreground="white")
        st.map("Accent.TButton", background=[("active", "#1d4ed8")])
        st.configure("Treeview", rowheight=28, font=("Segoe UI", 10)); st.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        st.configure("Horizontal.TProgressbar", troughcolor="#dbe3f5", background="#16a34a", thickness=18)
        self.show_arch = tk.IntVar(value=0); self.sort_desc = False; self.gid = None
        self.build(); self.refresh(); self.after(500, self.remind); self.after(60000, self.tick)

    def build(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=14, pady=10)
        ttk.Label(top, text="Цель. Код будущего", style="H.TLabel").pack(side="left")
        ttk.Checkbutton(top, text="Показать архив", variable=self.show_arch, command=self.refresh).pack(side="right")
        main = ttk.Frame(self); main.pack(fill="both", expand=True, padx=14)
        left = ttk.Frame(main); left.pack(side="left", fill="both", expand=True)
        gb = ttk.Frame(left); gb.pack(fill="x", pady=(0, 6))
        for t, c in [("+ Новая цель", self.add_goal), ("Изменить", self.edit_goal), ("Копировать", self.copy_goal),
                     ("В архив", self.archive_goal), ("Удалить", self.del_goal)]:
            ttk.Button(gb, text=t, command=c, style="Accent.TButton" if t.startswith("+") else "TButton").pack(side="left", padx=2)
        ttk.Button(gb, text="Сортировка по сроку", command=self.toggle_sort).pack(side="right")
        self.gt = ttk.Treeview(left, columns=("name", "deadline", "status", "prog"), show="headings", selectmode="browse")
        for c, t, w in [("name", "Цель", 220), ("deadline", "Срок", 130), ("status", "Статус", 90), ("prog", "Прогресс", 80)]:
            self.gt.heading(c, text=t); self.gt.column(c, width=w)
        self.gt.pack(fill="both", expand=True); self.gt.bind("<<TreeviewSelect>>", self.on_sel)
        for tag, col in [("late", "#fee2e2"), ("soon", "#fef3c7"), ("done", "#dcfce7")]: self.gt.tag_configure(tag, background=col)
        right = ttk.Frame(main); right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.title_l = ttk.Label(right, text="Выберите цель", style="H.TLabel"); self.title_l.pack(anchor="w")
        self.desc_l = ttk.Label(right, text="", wraplength=470, justify="left"); self.desc_l.pack(anchor="w", pady=4)
        self.pb = ttk.Progressbar(right, maximum=100); self.pb.pack(fill="x", pady=4)
        self.pl = ttk.Label(right, text=""); self.pl.pack(anchor="w")
        tb = ttk.Frame(right); tb.pack(fill="x", pady=6)
        for t, c in [("+ Задача", self.add_task), ("Изменить", self.edit_task), ("Копировать", self.copy_task),
                     ("Выполнено / снять", self.toggle_task), ("Удалить", self.del_task)]:
            ttk.Button(tb, text=t, command=c).pack(side="left", padx=2)
        self.tt = ttk.Treeview(right, columns=("done", "name", "deadline"), show="headings", selectmode="browse")
        for c, t, w in [("done", "", 30), ("name", "Задача", 250), ("deadline", "Срок", 130)]:
            self.tt.heading(c, text=t); self.tt.column(c, width=w)
        self.tt.pack(fill="both", expand=True); self.tt.tag_configure("done", foreground="#16a34a")
        self.tt.tag_configure("late", background="#fee2e2")
        self.code = tk.Text(right, height=6, bg="#0f172a", fg="#4ade80", font=("Consolas", 10), state="disabled")
        self.code.pack(fill="x", pady=(8, 0))

    def stats(self, gid):
        t, d = con.execute("SELECT COUNT(*), COALESCE(SUM(done),0) FROM tasks WHERE goal_id=?", (gid,)).fetchone()
        return t, d

    def refresh(self):
        sel = self.gid
        self.gt.delete(*self.gt.get_children())
        q = "SELECT id,name,deadline,status FROM goals WHERE archived=? ORDER BY deadline IS NULL, deadline " + ("DESC" if self.sort_desc else "ASC")
        now = datetime.now()
        for gid, n, dl, s in con.execute(q, (self.show_arch.get(),)).fetchall():
            t, d = self.stats(gid); p = f"{int(100*d/t)}%" if t else "0%"
            tag = ()
            if s == "Завершена": tag = ("done",)
            elif dl and s != "Отменена":
                dt = datetime.fromisoformat(dl)
                tag = ("late",) if dt < now else (("soon",) if (dt - now).total_seconds() < 86400 else ())
            self.gt.insert("", "end", iid=str(gid), values=(n, show(dl), s, p), tags=tag)
        if sel and self.gt.exists(str(sel)): self.gt.selection_set(str(sel))
        else: self.gid = None; self.on_sel()

    def on_sel(self, e=None):
        s = self.gt.selection(); self.gid = int(s[0]) if s else None
        self.tt.delete(*self.tt.get_children())
        if not self.gid:
            self.title_l.config(text="Выберите цель"); self.desc_l.config(text=""); self.pb["value"] = 0; self.pl.config(text=""); self.set_code([]); return
        n, ds, dl, st = con.execute("SELECT name,descr,deadline,status FROM goals WHERE id=?", (self.gid,)).fetchone()
        self.title_l.config(text=n); self.desc_l.config(text=ds)
        now = datetime.now(); lines = []
        for tid, tn, td, dn in con.execute("SELECT id,name,deadline,done FROM tasks WHERE goal_id=? ORDER BY done, deadline IS NULL, deadline", (self.gid,)):
            tag = ("done",) if dn else ((("late",) if td and datetime.fromisoformat(td) < now else ()))
            self.tt.insert("", "end", iid=str(tid), values=("✔" if dn else "○", tn, show(td)), tags=tag)
        for (tn,) in con.execute("SELECT name FROM tasks WHERE goal_id=? AND done=1 ORDER BY done_at", (self.gid,)): lines.append(f"> {tn}")
        self.set_code(lines)
        t, d = self.stats(self.gid); self.pb["value"] = 100*d/t if t else 0
        self.pl.config(text=f"Выполнено {d} из {t}  |  Статус: {st}  |  Срок: {show(dl) or 'не задан'}")

    def set_code(self, lines):
        self.code.config(state="normal"); self.code.delete("1.0", "end")
        self.code.insert("end", "// Код будущего\n" + "\n".join(lines[-4:]) if lines else "// Код будущего: выполните первый шаг")
        self.code.config(state="disabled")

    def goal_fields(self): return [("name", "Наименование"), ("descr", "Описание"), ("deadline", "Срок"), ("status", "Статус")]
    def add_goal(self):
        r = Dialog(self, "Новая цель", self.goal_fields(), {"status": "Создана"}, "descr", "status").result
        if r: con.execute("INSERT INTO goals(name,descr,deadline,status) VALUES(?,?,?,?)", (r["name"], r["descr"], iso(r["deadline"]), r["status"])); con.commit(); self.refresh()
    def edit_goal(self):
        if not self.gid: return
        n, ds, dl, st = con.execute("SELECT name,descr,deadline,status FROM goals WHERE id=?", (self.gid,)).fetchone()
        r = Dialog(self, "Редактирование цели", self.goal_fields(), {"name": n, "descr": ds, "deadline": show(dl), "status": st}, "descr", "status").result
        if r: con.execute("UPDATE goals SET name=?,descr=?,deadline=?,status=? WHERE id=?", (r["name"], r["descr"], iso(r["deadline"]), r["status"], self.gid)); con.commit(); self.refresh(); self.on_sel()
    def copy_goal(self):
        if not self.gid: return
        n, ds, dl = con.execute("SELECT name,descr,deadline FROM goals WHERE id=?", (self.gid,)).fetchone()
        c = con.execute("INSERT INTO goals(name,descr,deadline,status) VALUES(?,?,?,'Создана')", (n + " (копия)", ds, dl)).lastrowid
        con.execute("INSERT INTO tasks(goal_id,name,deadline) SELECT ?,name,deadline FROM tasks WHERE goal_id=?", (c, self.gid)); con.commit(); self.refresh()
    def archive_goal(self):
        if not self.gid: return
        con.execute("UPDATE goals SET archived=1-archived WHERE id=?", (self.gid,)); con.commit(); self.gid = None; self.refresh()
    def del_goal(self):
        if self.gid and messagebox.askyesno("Удаление", "Удалить цель и все её задачи?"):
            con.execute("DELETE FROM goals WHERE id=?", (self.gid,)); con.commit(); self.gid = None; self.refresh()
    def toggle_sort(self): self.sort_desc = not self.sort_desc; self.refresh()

    def tid(self):
        s = self.tt.selection(); return int(s[0]) if s else None
    def add_task(self):
        if not self.gid: return
        r = Dialog(self, "Новая задача", [("name", "Задача"), ("deadline", "Срок")]).result
        if r: con.execute("INSERT INTO tasks(goal_id,name,deadline) VALUES(?,?,?)", (self.gid, r["name"], iso(r["deadline"]))); con.commit(); self.refresh(); self.on_sel()
    def edit_task(self):
        t = self.tid()
        if not t: return
        n, d = con.execute("SELECT name,deadline FROM tasks WHERE id=?", (t,)).fetchone()
        r = Dialog(self, "Редактирование задачи", [("name", "Задача"), ("deadline", "Срок")], {"name": n, "deadline": show(d)}).result
        if r: con.execute("UPDATE tasks SET name=?,deadline=? WHERE id=?", (r["name"], iso(r["deadline"]), t)); con.commit(); self.refresh(); self.on_sel()
    def copy_task(self):
        t = self.tid()
        if not t: return
        con.execute("INSERT INTO tasks(goal_id,name,deadline) SELECT goal_id,name||' (копия)',deadline FROM tasks WHERE id=?", (t,)); con.commit(); self.refresh(); self.on_sel()
    def toggle_task(self):
        t = self.tid()
        if not t: return
        con.execute("UPDATE tasks SET done=1-done, done_at=? WHERE id=?", (datetime.now().isoformat(), t))
        tot, d = self.stats(self.gid)
        if tot and tot == d: 
            con.execute("UPDATE goals SET status='Завершена' WHERE id=?", (self.gid,)); con.commit(); self.refresh(); self.on_sel()
            messagebox.showinfo("Цель достигнута!", "Все этапы завершены. Это часть вашей истории успеха!"); return
        elif d > 0: con.execute("UPDATE goals SET status='Активна' WHERE id=? AND status IN ('Создана','Завершена')", (self.gid,))
        con.commit(); self.refresh(); self.on_sel()
    def del_task(self):
        t = self.tid()
        if t and messagebox.askyesno("Удаление", "Удалить задачу?"): con.execute("DELETE FROM tasks WHERE id=?", (t,)); con.commit(); self.refresh(); self.on_sel()

    def remind(self):
        lim = datetime.now().timestamp() + 86400; items = []
        for n, g, d in con.execute("SELECT t.name,g.name,t.deadline FROM tasks t JOIN goals g ON g.id=t.goal_id WHERE t.done=0 AND g.archived=0 AND g.status NOT IN ('Отменена','Завершена') AND t.deadline IS NOT NULL"):
            if datetime.fromisoformat(d).timestamp() < lim: items.append(f"{g}: {n} ({show(d)})")
        if items: messagebox.showwarning("Напоминание о сроках", "Срок близок или истёк:\n\n" + "\n".join(items[:12]))
    def tick(self): self.refresh(); self.remind(); self.after(3600000, self.tick)

if __name__ == "__main__":
    App().mainloop()
