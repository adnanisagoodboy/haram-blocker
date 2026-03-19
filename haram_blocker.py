#!/usr/bin/env python3
"""Haram Blocker v1.0 — System-wide content filter for Linux"""

import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog, ttk
import subprocess, hashlib, json, os, re, csv, webbrowser, datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

SCRIPT_DIR   = Path(__file__).parent.resolve()
CONFIG_DIR   = Path.home() / ".config" / "haram_blocker"
CONFIG_FILE  = CONFIG_DIR  / "config.json"
LOG_FILE     = CONFIG_DIR  / "history.json"
DOMAINS_CSV  = SCRIPT_DIR  / "data" / "domains.csv"
ICON_FILE    = SCRIPT_DIR  / "assets" / "icon.png"
HOSTS_FILE   = "/etc/hosts"
MARKER_START = "# === HARAM BLOCKER START ==="
MARKER_END   = "# === HARAM BLOCKER END ==="
GITHUB_URL   = "https://github.com/adnanisagoodboy/haram-blocker"
APP_VERSION  = "1.0"

CATEGORIES = {
    "adult":         ("Adult & 18+ Sites",    "#e05c6e"),
    "gambling":      ("Betting & Gambling",    "#d4a843"),
    "dating":        ("Dating & Hookup Sites", "#d47843"),
    "alcohol_drugs": ("Alcohol & Drug Sites",  "#9b7fe8"),
}

P = {
    "bg":      "#0a0d13",
    "surface": "#0f1420",
    "panel":   "#141c2e",
    "card":    "#1a2338",
    "hover":   "#1f2a42",
    "border":  "#263048",
    "border2": "#1a2235",
    "green":   "#2dd4a0",
    "green_d": "#1fa87e",
    "red":     "#e05c6e",
    "red_d":   "#b8455a",
    "text":    "#c8d6f0",
    "text2":   "#8a9bbf",
    "text3":   "#4a5a7a",
    "accent":  "#3d82f0",
    "white":   "#e8f0ff",
}

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_domains_csv(path):
    result = {k: [] for k in CATEGORIES}
    if not path.exists():
        return result
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith("#"):
                continue
            if len(row) < 2:
                continue
            cat = row[0].strip().lower()
            dom = row[1].strip().lower()\
                      .replace("https://","").replace("http://","").strip("/")
            if cat in result and dom:
                result[cat].append(dom)
    return result

def save_domains_csv(domains, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "domain"])
        w.writerow(["# Format: category,domain — categories: adult | gambling | dating | alcohol_drugs", ""])
        for cat, doms in domains.items():
            w.writerow([f"# {cat}", ""])
            for d in sorted(set(doms)):
                w.writerow([cat, d])

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "password_hash": hash_pw("bismillah"),
        "enabled": False,
        "categories": {k: True for k in CATEGORIES},
        "custom_sites": [],
    }

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            try: return json.load(f)
            except: return []
    return []

def append_log(action, count):
    log = load_log()
    log.append({
        "time":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action":  action,
        "domains": count,
    })
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(log[-200:], f, indent=2)

def all_domains(cfg, base):
    d = []
    for cat, sites in base.items():
        if cfg["categories"].get(cat, True):
            d += sites
    d += cfg.get("custom_sites", [])
    extra = []
    for x in d:
        if not x.startswith("www.") and "/" not in x and "." in x:
            w = "www." + x
            if w not in d:
                extra.append(w)
    return list(set(d + extra))

def run_root(cmd):
    for prefix in [["pkexec"], ["sudo", "-n"], ["sudo"]]:
        try:
            r = subprocess.run(prefix + cmd, capture_output=True, text=True)
            if r.returncode == 0:
                return True, ""
        except FileNotFoundError:
            continue
    return False, "Could not gain root access."

def apply_hosts(cfg, base):
    try:
        with open(HOSTS_FILE, "r") as f:
            content = f.read()
    except PermissionError:
        return False, "Permission denied reading /etc/hosts"
    pattern = re.compile(
        rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n?",
        re.DOTALL)
    content = pattern.sub("", content)
    domains = all_domains(cfg, base)
    if cfg["enabled"]:
        lines = [
            MARKER_START,
            f"# Haram Blocker v{APP_VERSION} — {len(domains)} domains",
        ]
        for d in sorted(domains):
            lines.append(f"0.0.0.0 {d}")
        lines.append(MARKER_END)
        content = content.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n"
    tmp = "/tmp/_hb_hosts"
    with open(tmp, "w") as f:
        f.write(content)
    ok, err = run_root(["cp", tmp, HOSTS_FILE])
    try:
        os.remove(tmp)
    except:
        pass
    if ok:
        for cmd in [["systemctl", "restart", "systemd-resolved"],
                    ["service", "nscd", "restart"]]:
            subprocess.run(["pkexec"] + cmd, capture_output=True)
        append_log("enabled" if cfg["enabled"] else "disabled", len(domains))
    return ok, err

def setup_autostart():
    d = Path.home() / ".config" / "autostart"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "haram_blocker.desktop"
    f.write_text(f"""[Desktop Entry]
Type=Application
Name=Haram Blocker
Exec=python3 {SCRIPT_DIR / "haram_blocker.py"}
Icon={ICON_FILE}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
""")
    return str(f)

def remove_autostart():
    f = Path.home() / ".config" / "autostart" / "haram_blocker.desktop"
    if f.exists():
        f.unlink()

def is_autostart():
    return (Path.home() / ".config" / "autostart" / "haram_blocker.desktop").exists()


class Scrollable(tk.Frame):
    """A vertically scrollable frame."""
    def __init__(self, parent, bg, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                        command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.inner_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>",   self._on_scroll_up)
        self.canvas.bind_all("<Button-5>",   self._on_scroll_down)

    def _on_inner_configure(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self.canvas.itemconfig(self.inner_id, width=e.width)

    def _on_mousewheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _on_scroll_up(self, _):
        self.canvas.yview_scroll(-1, "units")

    def _on_scroll_down(self, _):
        self.canvas.yview_scroll(1, "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg          = load_config()
        self.base_domains = load_domains_csv(DOMAINS_CSV)
        self._pending_import = None

        self.title("Haram Blocker")
        self.geometry("760x680")
        self.minsize(600, 500)
        self.configure(bg=P["bg"])

        if ICON_FILE.exists():
            try:
                img = tk.PhotoImage(file=str(ICON_FILE))
                self.iconphoto(True, img)
            except Exception:
                pass

        self._setup_styles()
        self._build()
        self._refresh_status()

    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TScrollbar",
                    background=P["card"], troughcolor=P["surface"],
                    borderwidth=0, arrowcolor=P["text3"],
                    relief="flat")
        s.map("TScrollbar",
              background=[("active", P["hover"]), ("!active", P["card"])])
        s.configure("Thin.TSeparator", background=P["border2"])

    def _build(self):
        self._topbar()
        outer = tk.Frame(self, bg=P["bg"])
        outer.pack(fill="both", expand=True)
        self._sidebar(outer)
        self._main_area(outer)
        self._statusbar()
        self._pages["home"].tkraise()

    def _topbar(self):
        bar = tk.Frame(self, bg=P["surface"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=P["surface"])
        left.pack(side="left", padx=20, pady=10)
        tk.Label(left, text="HARAM BLOCKER",
                 bg=P["surface"], fg=P["white"],
                 font=("Georgia", 13, "bold")).pack(side="left")
        tk.Label(left, text=f"  v{APP_VERSION}",
                 bg=P["surface"], fg=P["text3"],
                 font=("Courier", 9)).pack(side="left", pady=3)

        right = tk.Frame(bar, bg=P["surface"])
        right.pack(side="right", padx=16)

        tk.Button(right, text="GitHub",
                  bg=P["panel"], fg=P["text2"],
                  font=("Segoe UI", 9), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=P["hover"],
                  activeforeground=P["white"],
                  command=lambda: webbrowser.open(GITHUB_URL)
                  ).pack(side="right", padx=4)

        tk.Button(right, text="Change Password",
                  bg=P["panel"], fg=P["text2"],
                  font=("Segoe UI", 9), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=P["hover"],
                  activeforeground=P["white"],
                  command=self._change_password
                  ).pack(side="right", padx=4)

    def _sidebar(self, parent):
        sb = tk.Frame(parent, bg=P["surface"], width=168)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        tk.Frame(sb, bg=P["border2"], width=1).pack(side="right", fill="y")

        nav_items = [
            ("home",     "Dashboard"),
            ("cats",     "Categories"),
            ("custom",   "Custom Sites"),
            ("import",   "Import CSV"),
            ("log",      "History"),
            ("settings", "Settings"),
        ]
        self._nav_btns = {}
        tk.Frame(sb, bg=P["surface"], height=12).pack()
        for key, label in nav_items:
            btn = tk.Button(sb, text=label,
                            bg=P["surface"], fg=P["text2"],
                            font=("Segoe UI", 10), relief="flat", bd=0,
                            anchor="w", padx=20, pady=9, cursor="hand2",
                            activebackground=P["hover"],
                            activeforeground=P["white"],
                            command=lambda k=key: self._show(k))
            btn.pack(fill="x")
            self._nav_btns[key] = btn

    def _main_area(self, parent):
        self._frame = tk.Frame(parent, bg=P["bg"])
        self._frame.pack(side="left", fill="both", expand=True)
        self._pages = {
            "home":     self._pg_home(),
            "cats":     self._pg_cats(),
            "custom":   self._pg_custom(),
            "import":   self._pg_import(),
            "log":      self._pg_log(),
            "settings": self._pg_settings(),
        }
        for p in self._pages.values():
            p.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _statusbar(self):
        bar = tk.Frame(self, bg=P["surface"], height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=P["border2"], height=1).pack(fill="x", side="top")
        self._sb_text = tk.Label(bar, text="",
                                  bg=P["surface"], fg=P["text3"],
                                  font=("Courier", 8))
        self._sb_text.pack(side="left", padx=14)
        tk.Label(bar, text="/etc/hosts  |  system-wide",
                 bg=P["surface"], fg=P["text3"],
                 font=("Courier", 8)).pack(side="right", padx=14)

    def _show(self, key):
        self._pages[key].tkraise()
        for k, b in self._nav_btns.items():
            if k == key:
                b.config(bg=P["card"], fg=P["white"],
                         font=("Segoe UI", 10, "bold"))
            else:
                b.config(bg=P["surface"], fg=P["text2"],
                         font=("Segoe UI", 10))
        if key == "log":
            self._render_log()

    def _card(self, parent, **kw):
        f = tk.Frame(parent, bg=P["card"],
                     highlightbackground=P["border"],
                     highlightthickness=1, **kw)
        return f

    def _section_title(self, parent, text):
        tk.Label(parent, text=text,
                 bg=P["bg"], fg=P["white"],
                 font=("Georgia", 13, "bold")
                 ).pack(anchor="w", padx=24, pady=(20, 4))

    def _section_sub(self, parent, text):
        tk.Label(parent, text=text,
                 bg=P["bg"], fg=P["text2"],
                 font=("Segoe UI", 9), justify="left"
                 ).pack(anchor="w", padx=24, pady=(0, 12))

    def _pg_home(self):
        page = tk.Frame(self._frame, bg=P["bg"])

        hero = self._card(page, pady=30)
        hero.pack(fill="x", padx=24, pady=(22, 14))

        self._hero_title = tk.Label(hero, text="",
                                     bg=P["card"], font=("Georgia", 18, "bold"))
        self._hero_title.pack()

        self._hero_sub = tk.Label(hero, text="",
                                   bg=P["card"], fg=P["text2"],
                                   font=("Segoe UI", 10))
        self._hero_sub.pack(pady=(4, 0))

        tk.Frame(hero, bg=P["border2"], height=1
                 ).pack(fill="x", padx=36, pady=18)

        self._toggle_btn = tk.Button(hero, text="",
                                      font=("Segoe UI", 11, "bold"),
                                      relief="flat", bd=0,
                                      padx=40, pady=11, cursor="hand2",
                                      command=self._toggle)
        self._toggle_btn.pack()

        self._domain_lbl = tk.Label(hero, text="",
                                     bg=P["card"], fg=P["text3"],
                                     font=("Courier", 9))
        self._domain_lbl.pack(pady=(8, 0))

        stats = tk.Frame(page, bg=P["bg"])
        stats.pack(fill="x", padx=24, pady=(0, 14))
        for i, (cat, (label, color)) in enumerate(CATEGORIES.items()):
            cnt = len(self.base_domains.get(cat, []))
            c = self._card(stats, padx=12, pady=14)
            c.grid(row=0, column=i, sticky="nsew", padx=3)
            stats.columnconfigure(i, weight=1)
            tk.Label(c, text=str(cnt) + "+",
                     bg=P["card"], fg=color,
                     font=("Georgia", 16, "bold")).pack()
            tk.Label(c, text=label.split()[0],
                     bg=P["card"], fg=P["text3"],
                     font=("Segoe UI", 8)).pack()

        info = self._card(page, pady=14, padx=20)
        info.pack(fill="x", padx=24)
        for line in [
            "Redirects blocked domains to 0.0.0.0 via /etc/hosts",
            "Effective in all browsers — Chrome, Firefox, and others",
            "Password-protected — disabling requires your password",
            "Edit data/domains.csv to add or remove domains at any time",
        ]:
            tk.Label(info, text=line,
                     bg=P["card"], fg=P["text2"],
                     font=("Segoe UI", 9)).pack(anchor="w", pady=2)
        return page

    def _pg_cats(self):
        page = tk.Frame(self._frame, bg=P["bg"])
        self._section_title(page, "Categories")
        self._section_sub(page, "Enable or disable each category. Active changes apply immediately.")

        scroll = Scrollable(page, bg=P["bg"])
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        self._cat_vars = {}
        for cat, (label, color) in CATEGORIES.items():
            card = self._card(scroll.inner, pady=16, padx=20)
            card.pack(fill="x", pady=5)

            left = tk.Frame(card, bg=P["card"])
            left.pack(side="left", fill="x", expand=True)

            tk.Label(left, text=label,
                     bg=P["card"], fg=P["white"],
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")

            cnt = len(self.base_domains.get(cat, []))
            tk.Label(left,
                     text=f"{cnt} domains  •  www variants auto-added",
                     bg=P["card"], fg=P["text3"],
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))

            tk.Frame(left, bg=color, height=2, width=160
                     ).pack(anchor="w", pady=(7, 0))

            var = tk.BooleanVar(value=self.cfg["categories"].get(cat, True))
            self._cat_vars[cat] = var

            right = tk.Frame(card, bg=P["card"])
            right.pack(side="right", padx=6)

            state_lbl = tk.Label(right, text="",
                                  bg=P["card"], font=("Segoe UI", 8))
            state_lbl.pack(anchor="e", pady=(0, 3))

            def make_toggle(v=var, lbl=state_lbl):
                def _t():
                    lbl.config(
                        text="ON" if v.get() else "OFF",
                        fg=P["green"] if v.get() else P["text3"])
                    self._save_cats()
                return _t

            tk.Checkbutton(right, variable=var,
                           bg=P["card"], activebackground=P["card"],
                           selectcolor=P["green"],
                           fg=P["text2"], font=("Segoe UI", 9),
                           text="Enabled", cursor="hand2",
                           command=make_toggle()
                           ).pack(anchor="e")
            state_lbl.config(
                text="ON" if var.get() else "OFF",
                fg=P["green"] if var.get() else P["text3"])
        return page

    def _pg_custom(self):
        page = tk.Frame(self._frame, bg=P["bg"])
        self._section_title(page, "Custom Sites")
        self._section_sub(page, "Add any domain. Both domain.com and www.domain.com are blocked.")

        add_card = self._card(page, pady=14, padx=20)
        add_card.pack(fill="x", padx=24, pady=(0, 10))

        tk.Label(add_card, text="Domain",
                 bg=P["card"], fg=P["text3"],
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 4))

        row = tk.Frame(add_card, bg=P["card"])
        row.pack(fill="x")

        self._custom_entry = tk.Entry(row,
            bg=P["panel"], fg=P["text"],
            insertbackground=P["text"],
            font=("Courier", 11), relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=P["border"],
            highlightcolor=P["green"])
        self._custom_entry.pack(side="left", fill="x", expand=True,
                                 ipady=7, padx=(0, 10))
        self._custom_entry.bind("<Return>", lambda e: self._add_custom())

        tk.Button(row, text="Add",
                  bg=P["green"], fg=P["bg"],
                  font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                  padx=20, pady=7, cursor="hand2",
                  activebackground=P["green_d"],
                  activeforeground=P["bg"],
                  command=self._add_custom).pack(side="right")

        self._custom_list = Scrollable(page, bg=P["bg"])
        self._custom_list.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self._render_custom()
        return page

    def _pg_import(self):
        page = tk.Frame(self._frame, bg=P["bg"])
        self._section_title(page, "Import CSV")
        self._section_sub(page, "Import a domain list from a local file or a remote URL.")

        fmt = self._card(page, pady=12, padx=20)
        fmt.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(fmt, text="Required format",
                 bg=P["card"], fg=P["text3"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))
        for line in ["category,domain",
                     "adult,example.com",
                     "gambling,betsite.com",
                     "# comment lines are ignored"]:
            tk.Label(fmt, text=line,
                     bg=P["card"], fg=P["green"],
                     font=("Courier", 9)).pack(anchor="w")

        local_card = self._card(page, pady=14, padx=20)
        local_card.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(local_card, text="Local File",
                 bg=P["card"], fg=P["white"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        lr = tk.Frame(local_card, bg=P["card"])
        lr.pack(fill="x")
        self._local_lbl = tk.Label(lr, text="No file selected",
                                    bg=P["card"], fg=P["text3"],
                                    font=("Courier", 9))
        self._local_lbl.pack(side="left")
        tk.Button(lr, text="Browse",
                  bg=P["panel"], fg=P["text2"],
                  font=("Segoe UI", 9), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=P["hover"],
                  command=self._browse_csv).pack(side="right")
        tk.Button(lr, text="Import File",
                  bg=P["green"], fg=P["bg"],
                  font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=P["green_d"],
                  command=self._import_local).pack(side="right", padx=(0, 8))

        url_card = self._card(page, pady=14, padx=20)
        url_card.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(url_card, text="Remote URL",
                 bg=P["card"], fg=P["white"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        ur = tk.Frame(url_card, bg=P["card"])
        ur.pack(fill="x")
        self._url_entry = tk.Entry(ur,
            bg=P["panel"], fg=P["text"],
            insertbackground=P["text"],
            font=("Courier", 10), relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=P["border"],
            highlightcolor=P["green"])
        self._url_entry.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(ur, text="Fetch & Import",
                  bg=P["green"], fg=P["bg"],
                  font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2",
                  activebackground=P["green_d"],
                  command=self._import_url).pack(side="right", padx=(8, 0))

        self._import_msg = tk.Label(page, text="",
                                     bg=P["bg"], fg=P["text2"],
                                     font=("Segoe UI", 9))
        self._import_msg.pack(anchor="w", padx=24, pady=6)
        return page

    def _pg_log(self):
        page = tk.Frame(self._frame, bg=P["bg"])
        hdr = tk.Frame(page, bg=P["bg"])
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(hdr, text="History",
                 bg=P["bg"], fg=P["white"],
                 font=("Georgia", 13, "bold")).pack(side="left")
        tk.Button(hdr, text="Clear",
                  bg=P["panel"], fg=P["red"],
                  font=("Segoe UI", 9), relief="flat", bd=0,
                  padx=12, pady=5, cursor="hand2",
                  activebackground=P["hover"],
                  command=self._clear_log).pack(side="right")
        tk.Label(page, text="Protection enable/disable events.",
                 bg=P["bg"], fg=P["text2"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(0, 10))
        self._log_scroll = Scrollable(page, bg=P["bg"])
        self._log_scroll.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self._log_inner = self._log_scroll.inner
        return page

    def _pg_settings(self):
        page = tk.Frame(self._frame, bg=P["bg"])
        self._section_title(page, "Settings")

        as_card = self._card(page, pady=16, padx=20)
        as_card.pack(fill="x", padx=24, pady=(0, 10))
        ar = tk.Frame(as_card, bg=P["card"])
        ar.pack(fill="x")
        left = tk.Frame(ar, bg=P["card"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="Launch at Login",
                 bg=P["card"], fg=P["white"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(left,
                 text="Auto-start on login. Works on GNOME, KDE, XFCE and all XDG desktops.\n"
                      "Creates ~/.config/autostart/haram_blocker.desktop",
                 bg=P["card"], fg=P["text3"],
                 font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(3, 0))
        self._autostart_var = tk.BooleanVar(value=is_autostart())
        tk.Checkbutton(ar, variable=self._autostart_var,
                       text="Enabled",
                       bg=P["card"], activebackground=P["card"],
                       selectcolor=P["green"], fg=P["text2"],
                       font=("Segoe UI", 9), cursor="hand2",
                       command=self._toggle_autostart
                       ).pack(side="right")

        dom_card = self._card(page, pady=16, padx=20)
        dom_card.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(dom_card, text="Domains File",
                 bg=P["card"], fg=P["white"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(dom_card, text=str(DOMAINS_CSV),
                 bg=P["card"], fg=P["text3"],
                 font=("Courier", 9)).pack(anchor="w", pady=(4, 8))
        br = tk.Frame(dom_card, bg=P["card"])
        br.pack(anchor="w")
        tk.Button(br, text="Open in Editor",
                  bg=P["green"], fg=P["bg"],
                  font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2",
                  activebackground=P["green_d"],
                  command=self._open_csv).pack(side="left")
        tk.Button(br, text="Reload",
                  bg=P["panel"], fg=P["text2"],
                  font=("Segoe UI", 9), relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2",
                  activebackground=P["hover"],
                  command=self._reload_domains).pack(side="left", padx=(8, 0))

        about = self._card(page, pady=16, padx=20)
        about.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(about, text="About",
                 bg=P["card"], fg=P["white"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(about,
                 text=f"Haram Blocker v{APP_VERSION}\n"
                      "Open-source Linux content filter\n"
                      "Configuration: ~/.config/haram_blocker/",
                 bg=P["card"], fg=P["text3"],
                 font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(4, 8))
        tk.Button(about, text="View on GitHub",
                  bg=P["panel"], fg=P["text2"],
                  font=("Segoe UI", 9), relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2",
                  activebackground=P["hover"],
                  command=lambda: webbrowser.open(GITHUB_URL)
                  ).pack(anchor="w")
        return page

    def _refresh_status(self):
        enabled = self.cfg.get("enabled", False)
        count   = len(all_domains(self.cfg, self.base_domains))
        if enabled:
            self._hero_title.config(text="Protection Active", fg=P["green"])
            self._hero_sub.config(
                text=f"Blocking {count} domains across all browsers")
            self._toggle_btn.config(
                text="Disable Protection",
                bg=P["red"], fg=P["white"],
                activebackground=P["red_d"],
                activeforeground=P["white"])
        else:
            self._hero_title.config(text="Protection Inactive", fg=P["red"])
            self._hero_sub.config(text="Your device is not protected right now")
            self._toggle_btn.config(
                text="Enable Protection",
                bg=P["green"], fg=P["bg"],
                activebackground=P["green_d"],
                activeforeground=P["bg"])
        self._domain_lbl.config(text=f"{count} domains in blocklist")
        self._sb_text.config(
            text=f"{'ACTIVE' if enabled else 'INACTIVE'}  |  {count} domains  |  "
                 f"config: {CONFIG_DIR}")

    def _toggle(self):
        if self.cfg["enabled"]:
            pw = simpledialog.askstring(
                "Password Required",
                "Enter your password to disable protection:",
                show="*", parent=self)
            if pw is None:
                return
            if hash_pw(pw) != self.cfg["password_hash"]:
                messagebox.showerror("Wrong Password",
                    "Incorrect password. Protection remains active.")
                return
            self.cfg["enabled"] = False
        else:
            self.cfg["enabled"] = True
        save_config(self.cfg)
        self._apply()

    def _apply(self):
        self._toggle_btn.config(state="disabled", text="Applying...")
        self.update()
        ok, err = apply_hosts(self.cfg, self.base_domains)
        self._toggle_btn.config(state="normal")
        if ok:
            self._refresh_status()
            state = "enabled" if self.cfg["enabled"] else "disabled"
            messagebox.showinfo("Done", f"Protection has been {state}.")
        else:
            self.cfg["enabled"] = not self.cfg["enabled"]
            save_config(self.cfg)
            self._refresh_status()
            messagebox.showerror("Error",
                f"Could not modify /etc/hosts.\n\n"
                f"Run with: sudo python3 haram_blocker.py\n\nDetail: {err}")

    def _save_cats(self):
        for cat, var in self._cat_vars.items():
            self.cfg["categories"][cat] = var.get()
        save_config(self.cfg)
        self._refresh_status()
        if self.cfg["enabled"]:
            self._apply()

    def _render_custom(self):
        for w in self._custom_list.inner.winfo_children():
            w.destroy()
        sites = [s for s in self.cfg.get("custom_sites", [])
                 if not s.startswith("www.")]
        if not sites:
            tk.Label(self._custom_list.inner,
                     text="No custom sites added yet.",
                     bg=P["bg"], fg=P["text3"],
                     font=("Segoe UI", 10)).pack(pady=24)
            return
        for site in sites:
            row = self._card(self._custom_list.inner, pady=9, padx=16)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=site,
                     bg=P["card"], fg=P["text"],
                     font=("Courier", 10)).pack(side="left")
            tk.Label(row, text="(+ www)",
                     bg=P["card"], fg=P["text3"],
                     font=("Segoe UI", 8)).pack(side="left", padx=6)
            tk.Button(row, text="Remove",
                      bg=P["panel"], fg=P["red"],
                      font=("Segoe UI", 9), relief="flat", bd=0,
                      padx=8, pady=3, cursor="hand2",
                      activebackground=P["hover"],
                      command=lambda s=site: self._remove_custom(s)
                      ).pack(side="right")

    def _add_custom(self):
        raw = self._custom_entry.get().strip()
        if not raw:
            return
        site = raw.lower().replace("https://","").replace("http://","").strip("/")
        if not site:
            return
        sites = self.cfg.setdefault("custom_sites", [])
        added = False
        for v in [site, "www." + site]:
            if v not in sites:
                sites.append(v)
                added = True
        if added:
            save_config(self.cfg)
            self._custom_entry.delete(0, "end")
            self._render_custom()
            self._refresh_status()
            if self.cfg["enabled"]:
                self._apply()

    def _remove_custom(self, site):
        self.cfg["custom_sites"] = [
            s for s in self.cfg.get("custom_sites", [])
            if s != site and s != "www." + site
        ]
        save_config(self.cfg)
        self._render_custom()
        self._refresh_status()
        if self.cfg["enabled"]:
            self._apply()

    def _change_password(self):
        old = simpledialog.askstring("Current Password",
            "Current password:", show="*", parent=self)
        if old is None:
            return
        if hash_pw(old) != self.cfg["password_hash"]:
            messagebox.showerror("Wrong Password", "Incorrect password.")
            return
        new1 = simpledialog.askstring("New Password",
            "New password (min 6 characters):", show="*", parent=self)
        if not new1 or len(new1) < 6:
            messagebox.showwarning("Too Short", "Minimum 6 characters required.")
            return
        new2 = simpledialog.askstring("Confirm Password",
            "Confirm new password:", show="*", parent=self)
        if new1 != new2:
            messagebox.showerror("Mismatch", "Passwords do not match.")
            return
        self.cfg["password_hash"] = hash_pw(new1)
        save_config(self.cfg)
        messagebox.showinfo("Success", "Password changed.")

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self._pending_import = Path(path)
            self._local_lbl.config(text=Path(path).name, fg=P["green"])

    def _import_local(self):
        if not self._pending_import:
            messagebox.showwarning("No File", "Select a CSV file first.")
            return
        self._do_import(self._pending_import)

    def _import_url(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Enter a URL.")
            return
        self._import_msg.config(text="Fetching...", fg=P["text2"])
        self.update()
        tmp = Path("/tmp/_hb_import.csv")
        try:
            with urlopen(url, timeout=12) as r:
                tmp.write_bytes(r.read())
            self._do_import(tmp)
        except URLError as e:
            self._import_msg.config(text=f"Network error: {e}", fg=P["red"])
        except Exception as e:
            self._import_msg.config(text=f"Error: {e}", fg=P["red"])

    def _do_import(self, path):
        try:
            imported = load_domains_csv(path)
            total = sum(len(v) for v in imported.values())
            if total == 0:
                self._import_msg.config(text="No valid domains found.", fg=P["red"])
                return
            for cat, doms in imported.items():
                existing = set(self.base_domains.get(cat, []))
                self.base_domains[cat] = list(existing | set(doms))
            save_domains_csv(self.base_domains, DOMAINS_CSV)
            self._import_msg.config(
                text=f"Imported {total} domains. Saved to domains.csv.",
                fg=P["green"])
            self._refresh_status()
            if self.cfg["enabled"]:
                self._apply()
        except Exception as e:
            self._import_msg.config(text=f"Parse error: {e}", fg=P["red"])

    def _render_log(self):
        for w in self._log_inner.winfo_children():
            w.destroy()
        log = load_log()
        if not log:
            tk.Label(self._log_inner, text="No events logged.",
                     bg=P["bg"], fg=P["text3"],
                     font=("Segoe UI", 10)).pack(pady=24)
            return
        for entry in reversed(log[-100:]):
            row = tk.Frame(self._log_inner, bg=P["card"],
                           highlightbackground=P["border2"],
                           highlightthickness=1)
            row.pack(fill="x", pady=2)
            color = P["green"] if entry["action"] == "enabled" else P["red"]
            tk.Label(row, text=entry["action"].upper(),
                     bg=P["card"], fg=color, width=9,
                     font=("Segoe UI", 9, "bold")).pack(side="left", padx=14, pady=8)
            tk.Frame(row, bg=P["border2"], width=1).pack(side="left", fill="y")
            tk.Label(row, text=f"{entry['domains']} domains",
                     bg=P["card"], fg=P["text2"],
                     font=("Courier", 9)).pack(side="left", padx=14)
            tk.Label(row, text=entry["time"],
                     bg=P["card"], fg=P["text3"],
                     font=("Courier", 9)).pack(side="right", padx=14)

    def _clear_log(self):
        if messagebox.askyesno("Clear History", "Delete all history entries?"):
            LOG_FILE.write_text("[]")
            self._render_log()

    def _open_csv(self):
        for ed in ["gedit", "kate", "mousepad", "xed", "pluma", "nano"]:
            try:
                subprocess.Popen([ed, str(DOMAINS_CSV)])
                return
            except FileNotFoundError:
                continue
        subprocess.Popen(["xdg-open", str(DOMAINS_CSV)])

    def _reload_domains(self):
        self.base_domains = load_domains_csv(DOMAINS_CSV)
        self._refresh_status()
        total = sum(len(v) for v in self.base_domains.values())
        messagebox.showinfo("Reloaded", f"Domains reloaded.\nTotal: {total}")

    def _toggle_autostart(self):
        if self._autostart_var.get():
            path = setup_autostart()
            messagebox.showinfo("Autostart Enabled",
                f"Will launch at login.\n\nFile: {path}")
        else:
            remove_autostart()
            messagebox.showinfo("Autostart Disabled",
                "Will no longer launch at login.")


if __name__ == "__main__":
    app = App()
    app._show("home")
    app.mainloop()
