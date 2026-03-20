#!/usr/bin/env python3
"""Haram Blocker v2.0"""

from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog, ttk
import subprocess, hashlib, json, os, re, csv, webbrowser, datetime, threading, random
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from collections import defaultdict

#Paths 
SCRIPT_DIR   = Path(__file__).parent.resolve()
CONFIG_DIR   = Path.home() / ".config" / "haram_blocker"
CONFIG_FILE  = CONFIG_DIR  / "config.json"
LOG_FILE     = CONFIG_DIR  / "history.json"
TRAFFIC_FILE = CONFIG_DIR  / "traffic.json"
STATS_FILE   = CONFIG_DIR  / "stats.json"
DOMAINS_CSV  = SCRIPT_DIR  / "data" / "domains.csv"
QUOTES_FILE  = SCRIPT_DIR  / "data" / "quotes.json"
ICON_FILE    = SCRIPT_DIR  / "assets" / "icon.png"
HOSTS_FILE   = "/etc/hosts"
MARKER_START = "# === HARAM BLOCKER START ==="
MARKER_END   = "# === HARAM BLOCKER END ==="
GITHUB_URL   = "https://github.com/adnanisagoodboy/haram-blocker"
VERSION      = "2.0"

CATEGORIES = {
    "adult":         ("Adult & 18+ Sites",    "#e05c6e"),
    "gambling":      ("Betting & Gambling",    "#d4a843"),
    "dating":        ("Dating & Hookup",       "#d47843"),
    "alcohol_drugs": ("Alcohol & Drugs",       "#9b7fe8"),
    "ads":           ("Ad Networks",           "#4a9eff"),
    "social_media":  ("Social Media",          "#f06292"),
}

# Palette
BG      = "#07090f"
SURFACE = "#0b0f1c"
PANEL   = "#0f1525"
CARD    = "#141e35"
CARD2   = "#18243e"
HOVER   = "#1d2a48"
BORDER  = "#1f3052"
BORDER2 = "#111928"
GREEN   = "#00e09e"
GREEND  = "#00b87e"
GREENB  = "#021a12"
RED     = "#f0506a"
REDD    = "#c0405a"
REDB    = "#1a020a"
GOLD    = "#f0b030"
BLUE    = "#4090ff"
PINK    = "#f060a0"
PURPLE  = "#9870f8"
ORANGE  = "#f08030"
TEXT    = "#b8cce8"
TEXT2   = "#607090"
TEXT3   = "#2e4060"
WHITE   = "#e0eeff"

CAT_COLORS = {cat: color for cat, (_, color) in CATEGORIES.items()}

#Data

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def jload(path, default):
    if Path(path).exists():
        try:
            with open(path) as f: return json.load(f)
        except: pass
    return default

def jsave(path, data, limit=0):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if limit and isinstance(data, list): data = data[-limit:]
    with open(path, "w") as f: json.dump(data, f, indent=2)

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f: return json.load(f)
        except: pass
    return {
        "password_hash": hash_pw("admin"),
        "enabled":       False,
        "categories":    {k: True for k in CATEGORIES},
        "custom_sites":  [],
        "wildcards":     [],
        "whitelist":     [],
    }

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)

def load_domains_csv(path):
    result = {k: [] for k in CATEGORIES}
    if not Path(path).exists(): return result
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith("#"): continue
            if len(row) < 2: continue
            cat = row[0].strip().lower()
            dom = row[1].strip().lower().replace("https://","").replace("http://","").strip("/")
            if cat in result and dom: result[cat].append(dom)
    return result

def save_domains_csv(domains, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category","domain"])
        w.writerow(["# categories: adult|gambling|dating|alcohol_drugs|ads|social_media",""])
        for cat, doms in domains.items():
            w.writerow([f"# {cat}",""])
            for d in sorted(set(doms)): w.writerow([cat, d])

def all_domains(cfg, base):
    wl = set(cfg.get("whitelist", []))
    d, cmap = [], {}
    for cat, sites in base.items():
        if cfg["categories"].get(cat, True):
            for s in sites:
                if s not in wl: d.append(s); cmap[s] = cat
    for s in cfg.get("custom_sites", []):
        if s not in wl: d.append(s); cmap[s] = "custom"
    extra = []
    for x in d:
        if not x.startswith("www.") and "/" not in x and "." in x:
            w = "www."+x
            if w not in d: extra.append(w); cmap[w] = cmap.get(x,"custom")
    return list(set(d+extra)), cmap

def is_blocked(domain, cfg, base):
    domain = domain.lower().strip()
    bl, _ = all_domains(cfg, base)
    bs = set(bl)
    if domain in bs or "www."+domain in bs: return True
    for wc in cfg.get("wildcards",[]):
        pat = wc.replace(".",r"\.").replace("*",".*")
        if re.fullmatch(pat, domain): return True
    return False

def load_stats():
    return jload(STATS_FILE, {"total_blocked":0,"sessions":0,"first_run":None,"by_category":{}})

def bump_stats(count, by_cat):
    s = load_stats()
    if not s.get("first_run"): s["first_run"] = datetime.date.today().isoformat()
    s["total_blocked"] = s.get("total_blocked",0) + count
    s["sessions"]      = s.get("sessions",0) + 1
    bc = s.setdefault("by_category",{})
    for cat, n in by_cat.items(): bc[cat] = bc.get(cat,0) + n
    jsave(STATS_FILE, s)

def append_event(action, count):
    log = jload(LOG_FILE, [])
    log.append({"time": now_str(), "action": action, "domains": count})
    jsave(LOG_FILE, log, 500)

def append_traffic(domain, category):
    t = jload(TRAFFIC_FILE, [])
    t.append({"time": now_str(), "domain": domain, "category": category})
    jsave(TRAFFIC_FILE, t, 3000)

def now_str(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_quotes():
    return jload(QUOTES_FILE, [])

#  DNS traffic monitor 

def detect_dns_method():
    """Detect which DNS logging method is available."""
    try:
        r = subprocess.run(["systemctl","is-active","systemd-resolved"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "active":
            return "resolved"
    except FileNotFoundError: pass
    try:
        r = subprocess.run(["systemctl","is-active","dnsmasq"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "active":
            return "dnsmasq"
    except FileNotFoundError: pass
    return None

def get_dns_log_lines(method, since_cursor=None):
    """
    Pull recent DNS query lines.
    Returns (lines:list[str], new_cursor:str|None)
    """
    lines = []
    cursor = since_cursor
    if method == "resolved":
        cmd = ["journalctl", "-u", "systemd-resolved", "--no-pager",
               "-n", "200", "--output=short-iso"]
        if since_cursor:
            cmd += ["--after-cursor", since_cursor]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            raw = r.stdout.strip().splitlines()
            # Also get new cursor
            cr = subprocess.run(
                ["journalctl", "-u", "systemd-resolved",
                 "--no-pager", "-n", "1", "--show-cursor", "--output=short-iso"],
                capture_output=True, text=True)
            for line in cr.stdout.splitlines():
                if line.startswith("-- cursor:"):
                    cursor = line.split(":", 1)[1].strip()
            lines = raw
        except Exception: pass

    elif method == "dnsmasq":
        cmd = ["journalctl", "-u", "dnsmasq", "--no-pager", "-n", "200"]
        if since_cursor:
            cmd += ["--after-cursor", since_cursor]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            lines = r.stdout.strip().splitlines()
            cr = subprocess.run(
                ["journalctl", "-u", "dnsmasq", "--no-pager",
                 "-n", "1", "--show-cursor"],
                capture_output=True, text=True)
            for line in cr.stdout.splitlines():
                if line.startswith("-- cursor:"):
                    cursor = line.split(":",1)[1].strip()
        except Exception: pass

    return lines, cursor

def parse_dns_queries(lines, method):
    """Extract queried domain names from log lines."""
    queries = []
    for line in lines:
        domain = None
        if method == "resolved":
            # systemd-resolved logs: "... Using DNS server ... for ..."
            # or "... LLMNR query ..."
            m = re.search(r"IN (\S+)\.", line)
            if not m:
                m = re.search(r"Resolving (\S+?) via", line)
            if not m:
                m = re.search(r"query\[A\]\s+(\S+?)\s+from", line)
            if m:
                domain = m.group(1).rstrip(".").lower()
        elif method == "dnsmasq":
            m = re.search(r"query\[[A-Z]+\]\s+(\S+?)\s+from", line)
            if m: domain = m.group(1).rstrip(".").lower()
        if domain and "." in domain and len(domain) > 3:
            queries.append(domain)
    return queries

#System 

def run_root(cmd):
    for pre in [["pkexec"],["sudo","-n"],["sudo"]]:
        try:
            r = subprocess.run(pre+cmd, capture_output=True, text=True)
            if r.returncode == 0: return True, ""
        except FileNotFoundError: continue
    return False, "Could not gain root access."

def apply_hosts(cfg, base):
    try: content = Path(HOSTS_FILE).read_text()
    except PermissionError: return False, "Permission denied reading /etc/hosts"
    pat = re.compile(rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n?", re.DOTALL)
    content = pat.sub("", content)
    domains, cmap = all_domains(cfg, base)
    if cfg["enabled"]:
        by_cat = defaultdict(int)
        for d in domains: by_cat[cmap.get(d,"custom")] += 1
        lines = [MARKER_START, f"# Haram Blocker v{VERSION} — {len(domains)} domains"]
        for d in sorted(domains): lines.append(f"0.0.0.0 {d}")
        lines.append(MARKER_END)
        content = content.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n"
        bump_stats(len(domains), dict(by_cat))
    tmp = Path("/tmp/_hb_hosts")
    tmp.write_text(content)
    ok, err = run_root(["cp", str(tmp), HOSTS_FILE])
    try: tmp.unlink()
    except: pass
    if ok:
        for cmd in [["systemctl","restart","systemd-resolved"],["service","nscd","restart"]]:
            subprocess.run(["pkexec"]+cmd, capture_output=True)
        append_event("enabled" if cfg["enabled"] else "disabled", len(domains))
    return ok, err

def setup_autostart():
    d = Path.home()/".config"/"autostart"
    d.mkdir(parents=True, exist_ok=True)
    f = d/"haram_blocker.desktop"
    f.write_text(
        f"[Desktop Entry]\nType=Application\nName=Haram Blocker\n"
        f"Exec=python3 {SCRIPT_DIR/'haram_blocker.py'}\nIcon={ICON_FILE}\n"
        f"Hidden=false\nNoDisplay=false\nX-GNOME-Autostart-enabled=true\n"
        f"X-KDE-autostart-after=panel\nStartupNotify=false\n")
    return str(f)

def remove_autostart():
    f = Path.home()/".config"/"autostart"/"haram_blocker.desktop"
    if f.exists(): f.unlink()

def is_autostart():
    return (Path.home()/".config"/"autostart"/"haram_blocker.desktop").exists()

#  UI primitives 

def B(parent, text, bg, fg, cmd, font=("Segoe UI",9), px=16, py=8, abg=None):
    return tk.Button(parent, text=text, bg=bg, fg=fg, font=font,
                     relief="flat", bd=0, padx=px, pady=py,
                     cursor="hand2", activebackground=abg or bg,
                     activeforeground=fg, command=cmd)

def E(parent, font=("Courier",11), w=None):
    kw = dict(bg=PANEL, fg=TEXT, insertbackground=TEXT, font=font,
              relief="flat", bd=0, highlightthickness=1,
              highlightbackground=BORDER, highlightcolor=GREEN)
    if w: kw["width"] = w
    return tk.Entry(parent, **kw)

def Sep(parent, color=BORDER2):
    return tk.Frame(parent, bg=color, height=1)

def Card(parent, **kw):
    return tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, **kw)

#  Shield 

class Shield(tk.Canvas):
    W, H = 130, 148
    def __init__(self, parent, active, **kw):
        super().__init__(parent, width=self.W, height=self.H,
                         bg=CARD, highlightthickness=0, bd=0, **kw)
        self._active=active; self._anim=None; self._step=0
        self.draw(active)

    def draw(self, active):
        self._active=active; self.delete("all")
        cx,cy = self.W//2, self.H//2-2
        color = GREEN if active else RED
        dark  = GREEND if active else REDD
        glow  = GREENB if active else REDB
        for i in range(4,0,-1):
            r=52+i*4; self.create_oval(cx-r,cy-r,cx+r,cy+r,fill=glow,outline="")
        sw,sh=78,92; sx,sy=cx-sw//2,cy-sh//2
        pts=[sx,sy+14,cx,sy,sx+sw,sy+14,sx+sw,sy+sh*0.58,cx,sy+sh,sx,sy+sh*0.58]
        sdw=[(p+3 if i%2 else p+2) for i,p in enumerate(pts)]
        self.create_polygon(sdw,fill=dark,outline="",smooth=True)
        self.create_polygon(pts,fill=color,outline="",smooth=True)
        self.create_polygon([sx+10,sy+14,cx-4,sy+1,cx+10,sy+1,sx+24,sy+14],
                            fill=dark,outline="",smooth=False)
        lx,ly=cx,cy+6
        self.create_arc(lx-11,ly-22,lx+11,ly-2,start=0,extent=180,style="arc",outline=CARD,width=5)
        self.create_rectangle(lx-13,ly-8,lx+13,ly+16,fill=CARD,outline="")
        self.create_rectangle(lx-11,ly-6,lx+11,ly+14,fill=CARD,outline="")
        self.create_oval(lx-4,ly-1,lx+4,ly+7,fill=color,outline="")
        self.create_rectangle(lx-3,ly+5,lx+3,ly+12,fill=color,outline="")

    def set_active(self, active):
        if self._anim: self.after_cancel(self._anim)
        self._step=0; self.draw(active); self._pulse()

    def _pulse(self):
        if self._step>=8: return
        self._step+=1; self.draw(self._active)
        cx,cy=self.W//2,self.H//2-2
        d=self._step*3
        self.create_oval(cx-56-d,cy-56-d,cx+56+d,cy+56+d,
                         fill=GREENB if self._active else REDB,outline="",tags="glow")
        self.tag_lower("glow")
        self._anim=self.after(50,self._pulse)

#  Bar chart

class BarChart(tk.Canvas):
    COLS=[GREEN,GOLD,ORANGE,PURPLE,BLUE,PINK]
    def __init__(self,parent,data,h=160,**kw):
        super().__init__(parent,height=h,bg=CARD,highlightthickness=0,**kw)
        self._data=data; self._h=h
        self.bind("<Configure>", lambda e: self._draw(e.width))
        self.after(80, lambda: self._draw(self.winfo_width()))

    def update(self, data):
        self._data=data; self._draw(self.winfo_width())

    def _draw(self,w):
        self.delete("all")
        if w<10: return
        if not self._data or not any(self._data.values()):
            self.create_text(w//2,self._h//2,text="No data yet",fill=TEXT3,font=("Segoe UI",10))
            return
        labels=list(self._data.keys()); values=list(self._data.values())
        mx=max(values) or 1
        pl,pr,pt,pb=16,16,22,38; n=len(labels)
        slot=(w-pl-pr)/n; bw=max(16,slot*0.58)
        for i,(lab,val) in enumerate(zip(labels,values)):
            x0=pl+i*slot+(slot-bw)/2; x1=x0+bw
            bh=(val/mx)*(self._h-pt-pb)
            y0=self._h-pb-bh; y1=self._h-pb
            col=self.COLS[i%len(self.COLS)]
            self.create_rectangle(x0,y0+4,x1,y1,fill=col,outline="",width=0)
            self.create_rectangle(x0,y0,x1,y0+6,fill=col,outline="",width=0)
            if val: self.create_text((x0+x1)/2,y0-5,text=str(val),fill=TEXT2,font=("Courier",8),anchor="s")
            self.create_line(x0,pt,x0,self._h-pb,fill=BORDER2,width=1,dash=(2,4))
            self.create_text((x0+x1)/2,self._h-pb+8,text=lab[:8],fill=TEXT3,font=("Courier",8),anchor="n")
        self.create_line(pl,self._h-pb,w-pr,self._h-pb,fill=BORDER,width=1)

#  Scrollable 

class Scroll(tk.Frame):
    def __init__(self, parent, bg=BG, **kw):
        super().__init__(parent, bg=bg, **kw)
        self._cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self._cv.yview)
        self.inner = tk.Frame(self._cv, bg=bg)
        self._win  = self._cv.create_window((0,0), window=self.inner, anchor="nw")
        self._cv.configure(yscrollcommand=sb.set)
        self._cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>",
            lambda _: self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>",
            lambda e: self._cv.itemconfig(self._win, width=e.width))
        self._cv.bind_all("<Button-4>",   lambda e: self._cv.yview_scroll(-1,"units"))
        self._cv.bind_all("<Button-5>",   lambda e: self._cv.yview_scroll(1,"units"))
        self._cv.bind_all("<MouseWheel>",
            lambda e: self._cv.yview_scroll(int(-e.delta/60),"units"))

#  App


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg         = load_config()
        self.base        = load_domains_csv(DOMAINS_CSV)
        self._pcsv       = None
        self._dns_method = None
        self._dns_cursor = None
        self._dns_thread = None
        self._dns_running= False
        self._traf_buf   = []   # buffer for thread->UI
        self._traf_lock  = threading.Lock()
        self._traf_len   = 0
        self._quotes     = load_quotes()
        self._cur_quote  = 0
        self._chart_ref  = None  # reference to stats bar chart

        self.title("Haram Blocker")
        self.geometry("1020x760")
        self.minsize(820,600)
        self.configure(bg=BG)

        if ICON_FILE.exists():
            try: self.iconphoto(True, tk.PhotoImage(file=str(ICON_FILE)))
            except: pass

        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TScrollbar", background=CARD, troughcolor=SURFACE,
                    borderwidth=0, arrowcolor=TEXT3, relief="flat")
        s.map("TScrollbar", background=[("active",HOVER),("!active",CARD)])

        self._build()
        self._go("dashboard")
        self._detect_dns()
        self._tick()

    #  Build

    def _build(self):
        self._topbar()
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True)
        self._sidebar(mid)
        Sep(mid, BORDER2).pack(side="left", fill="y")
        self._area = tk.Frame(mid, bg=BG)
        self._area.pack(side="left", fill="both", expand=True)
        self._statusbar()
        self._make_pages()

    def _topbar(self):
        bar = tk.Frame(self, bg=SURFACE, height=58)
        bar.pack(fill="x"); bar.pack_propagate(False)
        Sep(bar, BORDER2).pack(fill="x", side="bottom")
        L = tk.Frame(bar, bg=SURFACE)
        L.pack(side="left", padx=24, pady=10)
        tk.Label(L, text="HARAM BLOCKER", bg=SURFACE, fg=WHITE,
                 font=("Georgia",14,"bold")).pack(side="left")
        tk.Label(L, text=f"  v{VERSION}", bg=SURFACE, fg=TEXT3,
                 font=("Courier",9)).pack(side="left", pady=4)
        R = tk.Frame(bar, bg=SURFACE)
        R.pack(side="right", padx=18)
        B(R, "GitHub",          PANEL, TEXT2, lambda: webbrowser.open(GITHUB_URL),
          abg=HOVER).pack(side="right", padx=4)
        B(R, "Change Password", PANEL, TEXT2, self._change_pw,
          abg=HOVER).pack(side="right", padx=4)

    def _sidebar(self, parent):
        sb = tk.Frame(parent, bg=SURFACE, width=196)
        sb.pack(side="left", fill="y"); sb.pack_propagate(False)
        self._nav = {}
        tk.Frame(sb, bg=SURFACE, height=12).pack()
        NAV = [
            (None,       "PROTECTION"),
            ("dashboard","  Dashboard"),
            ("quotes",   "  Daily Motivation"),
            (None,       "BLOCKING"),
            ("cats",     "  Categories"),
            ("custom",   "  Custom Sites"),
            ("wildcards","  Wildcards"),
            ("whitelist","  Whitelist"),
            (None,       "TOOLS"),
            ("tester",   "  Site Tester"),
            ("monitor",  "  Traffic Monitor"),
            ("stats",    "  Statistics"),
            (None,       "DATA"),
            ("import",   "  Import CSV"),
            ("history",  "  History"),
            ("settings", "  Settings"),
        ]
        for key, label in NAV:
            if key is None:
                tk.Frame(sb, bg=SURFACE, height=4).pack()
                tk.Label(sb, text=label, bg=SURFACE, fg=TEXT3,
                         font=("Courier",7,"bold"), anchor="w"
                         ).pack(fill="x", padx=22, pady=(4,2))
                continue
            b = tk.Button(sb, text=label, bg=SURFACE, fg=TEXT2,
                          font=("Segoe UI",9), relief="flat", bd=0,
                          anchor="w", padx=14, pady=9, cursor="hand2",
                          activebackground=HOVER, activeforeground=WHITE,
                          command=lambda k=key: self._go(k))
            b.pack(fill="x")
            self._nav[key] = b

    def _statusbar(self):
        bar = tk.Frame(self, bg=SURFACE, height=30)
        bar.pack(fill="x", side="bottom"); bar.pack_propagate(False)
        Sep(bar, BORDER2).pack(fill="x", side="top")
        self._sb = tk.Label(bar, text="", bg=SURFACE, fg=TEXT3, font=("Courier",8))
        self._sb.pack(side="left", padx=18)
        self._dns_lbl = tk.Label(bar, text="DNS: detecting...", bg=SURFACE,
                                  fg=TEXT3, font=("Courier",8))
        self._dns_lbl.pack(side="right", padx=18)

    #  Pages 

    def _make_pages(self):
        self._pg = {}
        fns = {
            "dashboard": self._pg_dashboard,
            "quotes":    self._pg_quotes,
            "cats":      self._pg_cats,
            "custom":    self._pg_custom,
            "wildcards": self._pg_wildcards,
            "whitelist": self._pg_whitelist,
            "tester":    self._pg_tester,
            "monitor":   self._pg_monitor,
            "stats":     self._pg_stats,
            "import":    self._pg_import,
            "history":   self._pg_history,
            "settings":  self._pg_settings,
        }
        for key, fn in fns.items():
            p = tk.Frame(self._area, bg=BG)
            p.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._pg[key] = p
            fn(p)

    def _go(self, key):
        self._pg[key].tkraise()
        for k,b in self._nav.items():
            b.config(bg=CARD2 if k==key else SURFACE,
                     fg=WHITE if k==key else TEXT2,
                     font=("Segoe UI",9,"bold") if k==key else ("Segoe UI",9))
        if key == "history": self._render_history()
        if key == "stats":   self._render_stats()
        if key == "monitor": self._render_monitor()

    def _ph(self, page, title, sub=""):
        tk.Label(page, text=title, bg=BG, fg=WHITE,
                 font=("Georgia",14,"bold")).pack(anchor="w", padx=24, pady=(22,3))
        if sub:
            tk.Label(page, text=sub, bg=BG, fg=TEXT2,
                     font=("Segoe UI",9)).pack(anchor="w", padx=24, pady=(0,12))

    # ── Dashboard 

    def _pg_dashboard(self, page):
        sc = Scroll(page); sc.pack(fill="both", expand=True)
        inn = sc.inner

        hero = Card(inn); hero.pack(fill="x", padx=24, pady=(22,14))
        top  = tk.Frame(hero, bg=CARD); top.pack(fill="x", padx=30, pady=28)

        scol = tk.Frame(top, bg=CARD); scol.pack(side="left", padx=(0,28))
        self._shield = Shield(scol, self.cfg.get("enabled",False))
        self._shield.pack()

        icol = tk.Frame(top, bg=CARD); icol.pack(side="left", fill="both", expand=True)
        tk.Label(icol, text="PROTECTION STATUS", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w")
        self._st_title = tk.Label(icol, text="", bg=CARD, font=("Georgia",26,"bold"))
        self._st_title.pack(anchor="w", pady=(6,2))
        self._st_sub   = tk.Label(icol, text="", bg=CARD, fg=TEXT2, font=("Segoe UI",10))
        self._st_sub.pack(anchor="w")
        Sep(icol, BORDER2).pack(fill="x", pady=16)
        self._tog = tk.Button(icol, text="", font=("Segoe UI",11,"bold"),
                               relief="flat", bd=0, padx=36, pady=12,
                               cursor="hand2", command=self._toggle)
        self._tog.pack(anchor="w")
        self._dom_lbl = tk.Label(icol, text="", bg=CARD, fg=TEXT3, font=("Courier",9))
        self._dom_lbl.pack(anchor="w", pady=(10,0))

        Sep(hero, BORDER2).pack(fill="x", padx=30)
        cats = tk.Frame(hero, bg=CARD); cats.pack(fill="x", padx=30, pady=18)
        self._clbls = {}
        for i,(cat,(_,color)) in enumerate(CATEGORIES.items()):
            col = tk.Frame(cats, bg=CARD)
            col.grid(row=0, column=i, sticky="nsew", padx=8)
            cats.columnconfigure(i, weight=1)
            cnt = len(self.base.get(cat,[]))
            nl = tk.Label(col, text=str(cnt), bg=CARD, fg=color,
                          font=("Georgia",17,"bold"))
            nl.pack(anchor="w")
            tk.Label(col, text=cat.replace("_"," ").split()[0],
                     bg=CARD, fg=TEXT3, font=("Segoe UI",7)).pack(anchor="w")
            tk.Frame(col, bg=color, height=2).pack(fill="x", pady=(4,0))
            self._clbls[cat] = nl

        # Counter card
        ctr = Card(inn, pady=18, padx=28); ctr.pack(fill="x", padx=24, pady=(0,14))
        ct = tk.Frame(ctr, bg=CARD); ct.pack(fill="x")
        tk.Label(ct, text="TOTAL DOMAINS BLOCKED SINCE INSTALL",
                 bg=CARD, fg=TEXT3, font=("Courier",8,"bold")).pack(side="left")
        self._tot_lbl = tk.Label(ct, text="0", bg=CARD, fg=GREEN,
                                  font=("Georgia",28,"bold"))
        self._tot_lbl.pack(side="right")
        cb = tk.Frame(ctr, bg=CARD); cb.pack(fill="x", pady=(8,0))
        self._sess_lbl  = tk.Label(cb, text="", bg=CARD, fg=TEXT2, font=("Segoe UI",9))
        self._sess_lbl.pack(side="left")
        self._since_lbl = tk.Label(cb, text="", bg=CARD, fg=TEXT3, font=("Segoe UI",9))
        self._since_lbl.pack(side="right")

        # Quote preview
        qc = Card(inn, pady=18, padx=28); qc.pack(fill="x", padx=24, pady=(0,24))
        tk.Label(qc, text="DAILY MOTIVATION", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,10))
        self._dash_q_text = tk.Label(qc, text="", bg=CARD, fg=TEXT,
                                      font=("Georgia",11,"italic"),
                                      wraplength=600, justify="left")
        self._dash_q_text.pack(anchor="w")
        self._dash_q_auth = tk.Label(qc, text="", bg=CARD, fg=TEXT2,
                                      font=("Segoe UI",9))
        self._dash_q_auth.pack(anchor="w", pady=(6,0))
        B(qc, "Next Quote", PANEL, TEXT2, self._next_dash_quote,
          abg=HOVER).pack(anchor="w", pady=(12,0))

        self._refresh()
        self._show_dash_quote()

    # ── Motivation / Quotes 

    def _pg_quotes(self, page):
        self._ph(page, "Daily Motivation",
                 "Quotes on discipline, strength, faith and overcoming addiction.")

        # Filter bar
        fb = Card(page, pady=12, padx=24); fb.pack(fill="x", padx=24, pady=(0,12))
        tk.Label(fb, text="FILTER", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(side="left", padx=(0,12))
        self._q_filter = tk.StringVar(value="all")
        filters = [("All","all"),("Faith","faith"),("Discipline","discipline"),
                   ("Strength","strength"),("Purity","purity"),("Stoicism","stoicism")]
        for label, val in filters:
            tk.Radiobutton(fb, text=label, variable=self._q_filter, value=val,
                           bg=CARD, fg=TEXT2, selectcolor=CARD,
                           activebackground=CARD, activeforeground=GREEN,
                           font=("Segoe UI",9), cursor="hand2",
                           command=self._render_quotes).pack(side="left", padx=6)

        self._q_scroll = Scroll(page); self._q_scroll.pack(fill="both", expand=True,
                                                             padx=24, pady=(0,16))
        self._render_quotes()

    def _render_quotes(self):
        for w in self._q_scroll.inner.winfo_children(): w.destroy()
        filt = self._q_filter.get()
        quotes = self._quotes
        if filt != "all":
            quotes = [q for q in quotes if q.get("category","") == filt]
        if not quotes:
            tk.Label(self._q_scroll.inner, text="No quotes in this category.",
                     bg=BG, fg=TEXT3, font=("Segoe UI",10)).pack(pady=28)
            return
        for q in quotes:
            c = Card(self._q_scroll.inner, pady=18, padx=24)
            c.pack(fill="x", pady=5)
            cat   = q.get("category","")
            color = {"faith":GOLD,"discipline":GREEN,"strength":BLUE,
                     "purity":PINK,"stoicism":PURPLE,"courage":ORANGE,
                     "resilience":RED,"motivation":GREEN}.get(cat, TEXT2)
            tk.Frame(c, bg=color, height=3).pack(fill="x", anchor="w",
                                                   pady=(0,12), padx=0)
            tk.Label(c, text=f'"{q["quote"]}"', bg=CARD, fg=WHITE,
                     font=("Georgia",11,"italic"),
                     wraplength=680, justify="left").pack(anchor="w")
            tk.Label(c, text=f"— {q['author']}", bg=CARD, fg=TEXT2,
                     font=("Segoe UI",9)).pack(anchor="w", pady=(8,0))
            tk.Label(c, text=cat.upper(), bg=CARD, fg=color,
                     font=("Courier",7,"bold")).pack(anchor="e")

    def _show_dash_quote(self):
        if not self._quotes: return
        q = random.choice(self._quotes)
        self._dash_q_text.config(text=f'"{q["quote"]}"')
        self._dash_q_auth.config(text=f'— {q["author"]}')

    def _next_dash_quote(self):
        self._show_dash_quote()

    # ── Categories

    def _pg_cats(self, page):
        self._ph(page, "Categories", "Toggle each category. Changes apply immediately.")
        sc = Scroll(page); sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._cvars = {}
        for cat, (label, color) in CATEGORIES.items():
            c = Card(sc.inner, pady=18, padx=24); c.pack(fill="x", pady=5)
            L = tk.Frame(c, bg=CARD); L.pack(side="left", fill="x", expand=True)
            tk.Label(L, text=label, bg=CARD, fg=WHITE,
                     font=("Segoe UI",12,"bold")).pack(anchor="w")
            cnt = len(self.base.get(cat,[]))
            tk.Label(L, text=f"{cnt} domains  •  www variants added automatically",
                     bg=CARD, fg=TEXT3, font=("Segoe UI",8)).pack(anchor="w", pady=(3,0))
            tk.Frame(L, bg=color, height=3, width=200).pack(anchor="w", pady=(8,0))
            R = tk.Frame(c, bg=CARD); R.pack(side="right", padx=8)
            var = tk.BooleanVar(value=self.cfg["categories"].get(cat,True))
            self._cvars[cat] = var
            ind = tk.Label(R, text="ON" if var.get() else "OFF",
                           bg=CARD, fg=GREEN if var.get() else TEXT3,
                           font=("Courier",9,"bold"))
            ind.pack(anchor="e", pady=(0,5))
            def _cb(v=var, l=ind):
                l.config(text="ON" if v.get() else "OFF",
                         fg=GREEN if v.get() else TEXT3)
                self._save_cats()
            tk.Checkbutton(R, variable=var, text="Enabled",
                           bg=CARD, activebackground=CARD, selectcolor=GREEN,
                           fg=TEXT2, font=("Segoe UI",9), cursor="hand2",
                           command=_cb).pack(anchor="e")

    # ── Custom sites

    def _pg_custom(self, page):
        self._ph(page, "Custom Sites", "Add any domain. www variant blocked automatically.")
        a = Card(page, pady=16, padx=24); a.pack(fill="x", padx=24, pady=(0,12))
        tk.Label(a, text="DOMAIN", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,6))
        row = tk.Frame(a, bg=CARD); row.pack(fill="x")
        self._ce = E(row); self._ce.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,12))
        self._ce.bind("<Return>", lambda _: self._add_custom())
        B(row, "Add", GREEN, BG, self._add_custom,
          font=("Segoe UI",10,"bold"), px=24, py=8, abg=GREEND).pack(side="right")
        self._cs_sc = Scroll(page); self._cs_sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._render_custom()

    # ── Wildcards 

    def _pg_wildcards(self, page):
        self._ph(page, "Wildcard Rules", "Block domain families.  Example: *.casino.com")
        ex = Card(page, pady=12, padx=24); ex.pack(fill="x", padx=24, pady=(0,10))
        tk.Label(ex, text="EXAMPLES", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,6))
        for e in ["*.ads.com      blocks all subdomains of ads.com",
                  "tracking.*     blocks domains starting with tracking",
                  "*.doubleclick.*  blocks all doubleclick variants"]:
            tk.Label(ex, text=e, bg=CARD, fg=GREEN, font=("Courier",9)).pack(anchor="w")
        a = Card(page, pady=16, padx=24); a.pack(fill="x", padx=24, pady=(0,12))
        tk.Label(a, text="PATTERN", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,6))
        row = tk.Frame(a, bg=CARD); row.pack(fill="x")
        self._wce = E(row); self._wce.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,12))
        self._wce.bind("<Return>", lambda _: self._add_wc())
        B(row, "Add", GREEN, BG, self._add_wc,
          font=("Segoe UI",10,"bold"), px=24, py=8, abg=GREEND).pack(side="right")
        self._wc_sc = Scroll(page); self._wc_sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._render_wc()

    # ── Whitelist 

    def _pg_whitelist(self, page):
        self._ph(page, "Whitelist", "Sites listed here are never blocked.")
        a = Card(page, pady=16, padx=24); a.pack(fill="x", padx=24, pady=(0,12))
        tk.Label(a, text="DOMAIN TO ALLOW", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,6))
        row = tk.Frame(a, bg=CARD); row.pack(fill="x")
        self._wle = E(row); self._wle.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,12))
        self._wle.bind("<Return>", lambda _: self._add_wl())
        B(row, "Allow", GOLD, BG, self._add_wl,
          font=("Segoe UI",10,"bold"), px=24, py=8, abg=GOLD).pack(side="right")
        self._wl_sc = Scroll(page); self._wl_sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._render_wl()

    # ── Site tester─

    def _pg_tester(self, page):
        self._ph(page, "Site Tester", "Check if a domain is in your blocklist.")
        a = Card(page, pady=18, padx=24); a.pack(fill="x", padx=24, pady=(0,14))
        tk.Label(a, text="DOMAIN", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,6))
        row = tk.Frame(a, bg=CARD); row.pack(fill="x")
        self._te = E(row); self._te.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,12))
        self._te.bind("<Return>", lambda _: self._run_test())
        B(row, "Check", GREEN, BG, self._run_test,
          font=("Segoe UI",10,"bold"), px=24, py=8, abg=GREEND).pack(side="right")
        self._tc = Card(page, pady=22, padx=24); self._tc.pack(fill="x", padx=24)
        tk.Label(self._tc, text="Enter a domain above and press Check.",
                 bg=CARD, fg=TEXT3, font=("Segoe UI",10)).pack(anchor="w")

    # ── Traffic Monitor 

    def _pg_monitor(self, page):
        hdr = tk.Frame(page, bg=BG); hdr.pack(fill="x", padx=24, pady=(22,4))
        tk.Label(hdr, text="Traffic Monitor", bg=BG, fg=WHITE,
                 font=("Georgia",14,"bold")).pack(side="left")
        self._mon_status = tk.Label(hdr, text="", bg=BG, fg=TEXT3,
                                     font=("Courier",8,"bold"))
        self._mon_status.pack(side="left", padx=10, pady=5)
        B(hdr, "Clear", PANEL, RED, self._clear_traffic, abg=HOVER).pack(side="right")

        info = Card(page, pady=14, padx=24); info.pack(fill="x", padx=24, pady=(0,12))
        self._mon_info = tk.Label(info, text="Detecting DNS method...",
                                   bg=CARD, fg=TEXT2, font=("Segoe UI",9),
                                   wraplength=700, justify="left")
        self._mon_info.pack(anchor="w")

        # Summary row
        sr = tk.Frame(page, bg=BG); sr.pack(fill="x", padx=24, pady=(0,10))
        for i,(label,attr,color) in enumerate([
            ("Queries Seen",  "_mon_total", TEXT2),
            ("Blocked",       "_mon_blocked", RED),
            ("Allowed",       "_mon_allowed", GREEN),
            ("Unique Domains","_mon_unique",  BLUE),
        ]):
            c = Card(sr, pady=12, padx=16)
            c.grid(row=0, column=i, sticky="nsew", padx=4)
            sr.columnconfigure(i, weight=1)
            lv = tk.Label(c, text="0", bg=CARD, fg=color, font=("Georgia",18,"bold"))
            lv.pack()
            tk.Label(c, text=label, bg=CARD, fg=TEXT3, font=("Segoe UI",8)).pack()
            setattr(self, attr, lv)

        # Live feed
        tk.Label(page, text="LIVE DNS QUERIES", bg=BG, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", padx=24, pady=(4,4))
        self._mon_sc = Scroll(page)
        self._mon_sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._mon_inner = self._mon_sc.inner
        self._render_monitor()

    # ── Statistics

    def _pg_stats(self, page):
        hdr = tk.Frame(page, bg=BG); hdr.pack(fill="x", padx=24, pady=(22,4))
        tk.Label(hdr, text="Statistics", bg=BG, fg=WHITE,
                 font=("Georgia",14,"bold")).pack(side="left")
        B(hdr, "Refresh", PANEL, TEXT2, self._render_stats, abg=HOVER).pack(side="right")
        self._st_sc = Scroll(page)
        self._st_sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._st_inner = self._st_sc.inner

    # ── Import 

    def _pg_import(self, page):
        self._ph(page, "Import CSV", "Merge domains from a local file or remote URL.")
        sc = Scroll(page); sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        inn = sc.inner

        fmt = Card(inn, pady=14, padx=24); fmt.pack(fill="x", pady=(0,12))
        tk.Label(fmt, text="REQUIRED FORMAT", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,8))
        for line in ["category,domain",
                     "adult,example-adult.com",
                     "ads,tracker.example.net",
                     "# lines starting with # are ignored"]:
            tk.Label(fmt, text=line, bg=CARD, fg=GREEN,
                     font=("Courier",9)).pack(anchor="w", pady=1)

        lc = Card(inn, pady=18, padx=24); lc.pack(fill="x", pady=(0,12))
        tk.Label(lc, text="LOCAL FILE", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,10))
        lr = tk.Frame(lc, bg=CARD); lr.pack(fill="x")
        self._loc_lbl = tk.Label(lr, text="No file selected", bg=CARD, fg=TEXT3,
                                  font=("Courier",9))
        self._loc_lbl.pack(side="left")
        B(lr, "Import", GREEN, BG, self._import_local,
          font=("Segoe UI",9,"bold"), px=14, py=6, abg=GREEND
          ).pack(side="right", padx=(8,0))
        B(lr, "Browse", PANEL, TEXT2, self._browse_csv,
          px=14, py=6, abg=HOVER).pack(side="right")

        uc = Card(inn, pady=18, padx=24); uc.pack(fill="x", pady=(0,12))
        tk.Label(uc, text="REMOTE URL", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,10))
        ur = tk.Frame(uc, bg=CARD); ur.pack(fill="x")
        self._url_e = E(ur, font=("Courier",10))
        self._url_e.pack(side="left", fill="x", expand=True, ipady=6)
        B(ur, "Fetch & Import", GREEN, BG, self._import_url,
          font=("Segoe UI",9,"bold"), px=14, py=6, abg=GREEND
          ).pack(side="right", padx=(10,0))

        self._imp_msg = tk.Label(inn, text="", bg=BG, fg=TEXT2, font=("Segoe UI",9))
        self._imp_msg.pack(anchor="w", pady=8)

    # ── History 

    def _pg_history(self, page):
        hdr = tk.Frame(page, bg=BG); hdr.pack(fill="x", padx=24, pady=(22,4))
        tk.Label(hdr, text="History", bg=BG, fg=WHITE,
                 font=("Georgia",14,"bold")).pack(side="left")
        B(hdr, "Clear", PANEL, RED, self._clear_history, abg=HOVER).pack(side="right")
        tk.Label(page, text="Protection enable and disable events.",
                 bg=BG, fg=TEXT2, font=("Segoe UI",9)).pack(anchor="w", padx=24, pady=(0,10))
        self._hist_sc = Scroll(page)
        self._hist_sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._hist_inner = self._hist_sc.inner

    # ── Settings 

    def _pg_settings(self, page):
        self._ph(page, "Settings", "")
        sc = Scroll(page); sc.pack(fill="both", expand=True, padx=24, pady=(0,16))
        inn = sc.inner

        # Autostart
        ac = Card(inn, pady=20, padx=24); ac.pack(fill="x", pady=(0,12))
        row = tk.Frame(ac, bg=CARD); row.pack(fill="x")
        L = tk.Frame(row, bg=CARD); L.pack(side="left", fill="x", expand=True)
        tk.Label(L, text="Launch at Login", bg=CARD, fg=WHITE,
                 font=("Segoe UI",12,"bold")).pack(anchor="w")
        tk.Label(L,
                 text="Auto-start via XDG autostart entry.\n"
                      "Compatible with GNOME, KDE, XFCE, MATE, Cinnamon, and LXQt.\n"
                      "File: ~/.config/autostart/haram_blocker.desktop",
                 bg=CARD, fg=TEXT3, font=("Segoe UI",9), justify="left"
                 ).pack(anchor="w", pady=(4,0))
        self._as_var = tk.BooleanVar(value=is_autostart())
        tk.Checkbutton(row, variable=self._as_var, text="Enabled",
                       bg=CARD, activebackground=CARD, selectcolor=GREEN,
                       fg=TEXT2, font=("Segoe UI",9), cursor="hand2",
                       command=self._toggle_autostart).pack(side="right")

        # Domains file
        dc = Card(inn, pady=20, padx=24); dc.pack(fill="x", pady=(0,12))
        tk.Label(dc, text="Domains File", bg=CARD, fg=WHITE,
                 font=("Segoe UI",12,"bold")).pack(anchor="w")
        tk.Label(dc, text=str(DOMAINS_CSV), bg=CARD, fg=TEXT3,
                 font=("Courier",9)).pack(anchor="w", pady=(4,12))
        br = tk.Frame(dc, bg=CARD); br.pack(anchor="w")
        B(br, "Open in Editor", GREEN, BG, self._open_csv,
          font=("Segoe UI",9,"bold"), px=14, py=7, abg=GREEND).pack(side="left")
        B(br, "Reload Domains", PANEL, TEXT2, self._reload_domains,
          px=14, py=7, abg=HOVER).pack(side="left", padx=10)

        # Export
        ec = Card(inn, pady=20, padx=24); ec.pack(fill="x", pady=(0,12))
        tk.Label(ec, text="Export Blocklist", bg=CARD, fg=WHITE,
                 font=("Segoe UI",12,"bold")).pack(anchor="w")
        tk.Label(ec,
                 text="Export all active domains including custom sites and www variants.",
                 bg=CARD, fg=TEXT3, font=("Segoe UI",9)).pack(anchor="w", pady=(4,12))
        self._exp_lbl = tk.Label(ec, text="", bg=CARD, fg=GREEN, font=("Segoe UI",9))
        self._exp_lbl.pack(anchor="w", pady=(0,8))
        B(ec, "Export as CSV", PANEL, TEXT2, self._export_csv,
          px=14, py=7, abg=HOVER).pack(anchor="w")

        # About
        ab = Card(inn, pady=20, padx=24); ab.pack(fill="x", pady=(0,12))
        tk.Label(ab, text="About", bg=CARD, fg=WHITE,
                 font=("Segoe UI",12,"bold")).pack(anchor="w")
        tk.Label(ab,
                 text=f"Haram Blocker v{VERSION}\n"
                      "Open-source Linux content filter\n"
                      "Config: ~/.config/haram_blocker/\n"
                      "Default password: admin",
                 bg=CARD, fg=TEXT3, font=("Segoe UI",9), justify="left"
                 ).pack(anchor="w", pady=(4,12))
        B(ab, "View on GitHub", PANEL, TEXT2,
          lambda: webbrowser.open(GITHUB_URL),
          px=14, py=7, abg=HOVER).pack(anchor="w")

    # ── Refresh status 

    def _refresh(self):
        enabled = self.cfg.get("enabled", False)
        domains, _ = all_domains(self.cfg, self.base)
        count = len(domains)

        self._shield.set_active(enabled)

        if enabled:
            self._st_title.config(text="Active",   fg=GREEN)
            self._st_sub.config(text=f"Blocking {count} domains across all browsers")
            self._tog.config(text="Disable Protection",
                bg=RED, fg=WHITE, activebackground=REDD, activeforeground=WHITE)
        else:
            self._st_title.config(text="Inactive", fg=RED)
            self._st_sub.config(text="Your device is not protected right now")
            self._tog.config(text="Enable Protection",
                bg=GREEN, fg=BG, activebackground=GREEND, activeforeground=BG)

        self._dom_lbl.config(text=f"{count} domains in blocklist")
        self._sb.config(
            text=f"{'ACTIVE' if enabled else 'INACTIVE'}  |  {count} domains  |  {CONFIG_DIR}")

        for cat, nl in self._clbls.items():
            nl.config(text=str(len(self.base.get(cat,[]))))

        s = load_stats()
        self._tot_lbl.config(text=f"{s.get('total_blocked',0):,}")
        n = s.get("sessions",0)
        self._sess_lbl.config(text=f"{n} session{'s' if n!=1 else ''}")
        since = s.get("first_run")
        self._since_lbl.config(text=f"since {since}" if since else "")

    # ── Toggle ────

    def _toggle(self):
        if self.cfg["enabled"]:
            pw = simpledialog.askstring("Password Required",
                "Enter your password to disable protection:", show="*", parent=self)
            if pw is None: return
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
        self._tog.config(state="disabled", text="Applying...")
        self.update()
        ok, err = apply_hosts(self.cfg, self.base)
        self._tog.config(state="normal")
        if ok:
            self._refresh()
            messagebox.showinfo("Done",
                f"Protection has been {'enabled' if self.cfg['enabled'] else 'disabled'}.")
        else:
            self.cfg["enabled"] = not self.cfg["enabled"]
            save_config(self.cfg)
            self._refresh()
            messagebox.showerror("Error",
                f"Could not modify /etc/hosts.\n\nTry: sudo python3 haram_blocker.py\n\n{err}")

    def _save_cats(self):
        for cat, var in self._cvars.items():
            self.cfg["categories"][cat] = var.get()
        save_config(self.cfg)
        self._refresh()
        if self.cfg["enabled"]: self._apply()

    # ── Custom ────

    def _render_custom(self):
        for w in self._cs_sc.inner.winfo_children(): w.destroy()
        sites = [s for s in self.cfg.get("custom_sites",[]) if not s.startswith("www.")]
        if not sites:
            tk.Label(self._cs_sc.inner, text="No custom sites added yet.",
                     bg=BG, fg=TEXT3, font=("Segoe UI",10)).pack(pady=28)
            return
        for site in sites:
            r = Card(self._cs_sc.inner, pady=10, padx=18); r.pack(fill="x", pady=3)
            tk.Label(r, text=site, bg=CARD, fg=TEXT, font=("Courier",10)).pack(side="left")
            tk.Label(r, text="  + www", bg=CARD, fg=TEXT3,
                     font=("Segoe UI",8)).pack(side="left")
            B(r, "Remove", PANEL, RED, lambda s=site: self._rm_custom(s),
              px=10, py=4, abg=HOVER).pack(side="right")

    def _add_custom(self):
        raw  = self._ce.get().strip()
        site = raw.lower().replace("https://","").replace("http://","").strip("/")
        if not site: return
        sites = self.cfg.setdefault("custom_sites",[])
        added = False
        for v in [site, "www."+site]:
            if v not in sites: sites.append(v); added = True
        if added:
            save_config(self.cfg); self._ce.delete(0,"end")
            self._render_custom(); self._refresh()
            if self.cfg["enabled"]: self._apply()

    def _rm_custom(self, site):
        self.cfg["custom_sites"] = [
            s for s in self.cfg.get("custom_sites",[])
            if s != site and s != "www."+site]
        save_config(self.cfg); self._render_custom(); self._refresh()
        if self.cfg["enabled"]: self._apply()

    # ── Wildcards ─

    def _render_wc(self):
        for w in self._wc_sc.inner.winfo_children(): w.destroy()
        wcs = self.cfg.get("wildcards",[])
        if not wcs:
            tk.Label(self._wc_sc.inner, text="No wildcard rules added yet.",
                     bg=BG, fg=TEXT3, font=("Segoe UI",10)).pack(pady=28)
            return
        for wc in wcs:
            r = Card(self._wc_sc.inner, pady=10, padx=18); r.pack(fill="x", pady=3)
            tk.Label(r, text=wc, bg=CARD, fg=GOLD, font=("Courier",10)).pack(side="left")
            B(r, "Remove", PANEL, RED, lambda w=wc: self._rm_wc(w),
              px=10, py=4, abg=HOVER).pack(side="right")

    def _add_wc(self):
        raw = self._wce.get().strip()
        if not raw: return
        wcs = self.cfg.setdefault("wildcards",[])
        if raw not in wcs:
            wcs.append(raw); save_config(self.cfg)
            self._wce.delete(0,"end"); self._render_wc()

    def _rm_wc(self, wc):
        self.cfg["wildcards"] = [w for w in self.cfg.get("wildcards",[]) if w != wc]
        save_config(self.cfg); self._render_wc()

    # ── Whitelist ─

    def _render_wl(self):
        for w in self._wl_sc.inner.winfo_children(): w.destroy()
        wl = self.cfg.get("whitelist",[])
        if not wl:
            tk.Label(self._wl_sc.inner, text="No sites whitelisted.",
                     bg=BG, fg=TEXT3, font=("Segoe UI",10)).pack(pady=28)
            return
        for site in wl:
            r = Card(self._wl_sc.inner, pady=10, padx=18); r.pack(fill="x", pady=3)
            tk.Label(r, text=site, bg=CARD, fg=GOLD, font=("Courier",10)).pack(side="left")
            B(r, "Remove", PANEL, RED, lambda s=site: self._rm_wl(s),
              px=10, py=4, abg=HOVER).pack(side="right")

    def _add_wl(self):
        raw  = self._wle.get().strip()
        site = raw.lower().replace("https://","").replace("http://","").strip("/")
        if not site: return
        wl = self.cfg.setdefault("whitelist",[])
        if site not in wl:
            wl.append(site); save_config(self.cfg)
            self._wle.delete(0,"end"); self._render_wl()
            self._refresh()
            if self.cfg["enabled"]: self._apply()

    def _rm_wl(self, site):
        self.cfg["whitelist"] = [s for s in self.cfg.get("whitelist",[]) if s != site]
        save_config(self.cfg); self._render_wl(); self._refresh()
        if self.cfg["enabled"]: self._apply()

    # ── Site tester──

    def _run_test(self):
        raw    = self._te.get().strip()
        domain = raw.lower().replace("https://","").replace("http://","").strip("/")
        if not domain: return
        blocked = is_blocked(domain, self.cfg, self.base)
        for w in self._tc.winfo_children(): w.destroy()
        tk.Label(self._tc, text=domain, bg=CARD, fg=TEXT2,
                 font=("Courier",13)).pack(anchor="w")
        if blocked:
            self._tc.config(highlightbackground=GREEN, highlightthickness=2)
            tk.Label(self._tc, text="BLOCKED", bg=CARD, fg=GREEN,
                     font=("Georgia",22,"bold")).pack(anchor="w", pady=(8,2))
            tk.Label(self._tc, text="This domain is in your blocklist.",
                     bg=CARD, fg=TEXT2, font=("Segoe UI",10)).pack(anchor="w")
        else:
            self._tc.config(highlightbackground=RED, highlightthickness=2)
            tk.Label(self._tc, text="NOT BLOCKED", bg=CARD, fg=RED,
                     font=("Georgia",22,"bold")).pack(anchor="w", pady=(8,2))
            detail = ("Protection is inactive." if not self.cfg["enabled"]
                      else "Not in blocklist. Add it via Custom Sites or Wildcards.")
            tk.Label(self._tc, text=detail, bg=CARD, fg=TEXT2,
                     font=("Segoe UI",10)).pack(anchor="w")

    # ── Traffic Monitor ─────

    def _detect_dns(self):
        def _do():
            method = detect_dns_method()
            self._dns_method = method
            self.after(0, lambda: self._update_dns_ui(method))
        threading.Thread(target=_do, daemon=True).start()

    def _update_dns_ui(self, method):
        if method == "resolved":
            msg = "systemd-resolved detected. DNS queries will appear here in real time."
            self._dns_lbl.config(text="DNS: systemd-resolved", fg=GREEN)
        elif method == "dnsmasq":
            msg = "dnsmasq detected. DNS queries will appear here in real time."
            self._dns_lbl.config(text="DNS: dnsmasq", fg=GREEN)
        else:
            msg = ("No supported DNS logger detected.\n\n"
                   "To enable traffic monitoring, enable DNS logging:\n\n"
                   "  systemd-resolved:  sudo systemctl enable --now systemd-resolved\n"
                   "  dnsmasq:           sudo pacman -S dnsmasq && sudo systemctl enable --now dnsmasq\n\n"
                   "Once enabled, restart Haram Blocker.")
            self._dns_lbl.config(text="DNS: not detected", fg=RED)
        if hasattr(self, "_mon_info"):
            self._mon_info.config(text=msg)
        if hasattr(self, "_mon_status"):
            self._mon_status.config(
                text="MONITORING" if method else "INACTIVE",
                fg=GREEN if method else RED)
        if method:
            self._start_dns_thread()

    def _start_dns_thread(self):
        if self._dns_running: return
        self._dns_running = True
        def _worker():
            while self._dns_running:
                try:
                    lines, cursor = get_dns_log_lines(self._dns_method, self._dns_cursor)
                    if cursor: self._dns_cursor = cursor
                    if lines:
                        queries = parse_dns_queries(lines, self._dns_method)
                        if queries:
                            domains, cmap = all_domains(self.cfg, self.base)
                            bs = set(domains)
                            new_entries = []
                            for q in queries:
                                blocked = q in bs or "www."+q in bs
                                cat = cmap.get(q, cmap.get("www."+q, "unknown"))
                                new_entries.append({
                                    "time":    now_str(),
                                    "domain":  q,
                                    "blocked": blocked,
                                    "category": cat if blocked else "—",
                                })
                                if blocked:
                                    append_traffic(q, cat)
                            with self._traf_lock:
                                self._traf_buf.extend(new_entries)
                except Exception:
                    pass
                threading.Event().wait(2.0)
        threading.Thread(target=_worker, daemon=True).start()

    def _render_monitor(self):
        if not hasattr(self, "_mon_inner"): return
        for w in self._mon_inner.winfo_children(): w.destroy()

        traffic = jload(TRAFFIC_FILE, [])

        # Update summary counters from buffer
        with self._traf_lock:
            buf = list(self._traf_buf)

        total   = len(buf)
        blocked = sum(1 for e in buf if e.get("blocked"))
        allowed = total - blocked
        unique  = len(set(e["domain"] for e in buf))

        if hasattr(self, "_mon_total"):
            self._mon_total.config(text=str(total))
            self._mon_blocked.config(text=str(blocked))
            self._mon_allowed.config(text=str(allowed))
            self._mon_unique.config(text=str(unique))

        if not buf:
            tk.Label(self._mon_inner,
                     text="No DNS queries captured yet.\nBrowse the web with protection enabled.",
                     bg=BG, fg=TEXT3, font=("Segoe UI",10)).pack(pady=28)
            return

        # Show most recent entries
        for entry in reversed(buf[-300:]):
            r = tk.Frame(self._mon_inner, bg=CARD,
                         highlightbackground=BORDER2, highlightthickness=1)
            r.pack(fill="x", pady=2)
            is_b  = entry.get("blocked", False)
            color = RED if is_b else GREEN
            cat   = entry.get("category","—")
            tk.Frame(r, bg=color, width=4).pack(side="left", fill="y")
            tk.Label(r, text="BLOCK" if is_b else "ALLOW", bg=CARD, fg=color,
                     font=("Courier",8,"bold"), width=6).pack(side="left", padx=10, pady=9)
            tk.Frame(r, bg=BORDER2, width=1).pack(side="left", fill="y")
            tk.Label(r, text=entry.get("domain",""), bg=CARD, fg=TEXT,
                     font=("Courier",9)).pack(side="left", padx=12)
            if is_b:
                cat_color = CAT_COLORS.get(cat, TEXT2)
                tk.Label(r, text=cat, bg=CARD, fg=cat_color,
                         font=("Courier",8)).pack(side="left", padx=4)
            tk.Label(r, text=entry.get("time",""), bg=CARD, fg=TEXT3,
                     font=("Courier",8)).pack(side="right", padx=12)

    def _clear_traffic(self):
        if messagebox.askyesno("Clear", "Clear traffic monitor and stored logs?"):
            jsave(TRAFFIC_FILE, [])
            with self._traf_lock: self._traf_buf.clear()
            self._render_monitor()

    # ── Statistics 

    def _render_stats(self):
        if not hasattr(self, "_st_inner"): return
        for w in self._st_inner.winfo_children(): w.destroy()
        s  = load_stats()
        bc = s.get("by_category",{})

        # Overview
        ov = Card(self._st_inner, pady=20, padx=24); ov.pack(fill="x", pady=(0,12))
        tk.Label(ov, text="OVERVIEW", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,12))
        for label, val in [
            ("Total domains blocked",  f"{s.get('total_blocked',0):,}"),
            ("Protection sessions",    str(s.get("sessions",0))),
            ("First run",              s.get("first_run","—")),
            ("DNS method",             self._dns_method or "not detected"),
        ]:
            r = tk.Frame(ov, bg=CARD); r.pack(fill="x", pady=5)
            tk.Label(r, text=label, bg=CARD, fg=TEXT2, font=("Segoe UI",10)).pack(side="left")
            tk.Label(r, text=val,   bg=CARD, fg=GREEN,
                     font=("Courier",11,"bold")).pack(side="right")

        # Bar chart
        ch = Card(self._st_inner, pady=20, padx=24); ch.pack(fill="x", pady=(0,12))
        tk.Label(ch, text="BLOCKS BY CATEGORY", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,12))
        chart_data = {k.replace("_"," "): bc.get(k,0) for k in CATEGORIES}
        self._chart_ref = BarChart(ch, chart_data, h=190)
        self._chart_ref.pack(fill="x", pady=(0,6))

        # Per-category bars
        pc = Card(self._st_inner, pady=20, padx=24); pc.pack(fill="x", pady=(0,12))
        tk.Label(pc, text="PER CATEGORY", bg=CARD, fg=TEXT3,
                 font=("Courier",8,"bold")).pack(anchor="w", pady=(0,12))
        total = s.get("total_blocked",1) or 1
        for cat,(label,color) in CATEGORIES.items():
            cnt = bc.get(cat,0)
            r   = tk.Frame(pc, bg=CARD); r.pack(fill="x", pady=4)
            tk.Label(r, text=label, bg=CARD, fg=TEXT2, font=("Segoe UI",10)).pack(side="left")
            tk.Label(r, text=str(cnt), bg=CARD, fg=color,
                     font=("Courier",10,"bold")).pack(side="right")
            bf = tk.Frame(pc, bg=BORDER2, height=6); bf.pack(fill="x", pady=(0,6))
            bf.update_idletasks()
            bw = max(bf.winfo_width(), 500)
            tk.Frame(bf, bg=color, height=6,
                     width=int(bw*cnt/total)).place(x=0,y=0)

        # Top blocked domains from traffic log
        traffic = jload(TRAFFIC_FILE, [])
        if traffic:
            tc = Card(self._st_inner, pady=20, padx=24); tc.pack(fill="x", pady=(0,12))
            tk.Label(tc, text="TOP BLOCKED DOMAINS", bg=CARD, fg=TEXT3,
                     font=("Courier",8,"bold")).pack(anchor="w", pady=(0,12))
            counts: dict = defaultdict(int)
            for e in traffic: counts[e.get("domain","")] += 1
            for domain, cnt in sorted(counts.items(), key=lambda x: -x[1])[:20]:
                r = tk.Frame(tc, bg=CARD); r.pack(fill="x", pady=4)
                tk.Label(r, text=domain, bg=CARD, fg=TEXT2,
                         font=("Courier",9)).pack(side="left")
                tk.Label(r, text=str(cnt), bg=CARD, fg=GOLD,
                         font=("Courier",10,"bold")).pack(side="right")

    # ── Import/Export

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if path:
            self._pcsv = Path(path)
            self._loc_lbl.config(text=Path(path).name, fg=GREEN)

    def _import_local(self):
        if not self._pcsv:
            messagebox.showwarning("No File","Browse and select a CSV file first.")
            return
        self._do_import(self._pcsv)

    def _import_url(self):
        url = self._url_e.get().strip()
        if not url: return
        self._imp_msg.config(text="Fetching...", fg=TEXT2); self.update()
        tmp = Path("/tmp/_hb_import.csv")
        try:
            with urlopen(url, timeout=14) as r: tmp.write_bytes(r.read())
            self._do_import(tmp)
        except URLError as e: self._imp_msg.config(text=f"Network error: {e}", fg=RED)
        except Exception as e: self._imp_msg.config(text=f"Error: {e}", fg=RED)

    def _do_import(self, path):
        try:
            imported = load_domains_csv(path)
            total    = sum(len(v) for v in imported.values())
            if total == 0:
                self._imp_msg.config(text="No valid domains found.", fg=RED); return
            for cat, doms in imported.items():
                self.base[cat] = list(set(self.base.get(cat,[])) | set(doms))
            save_domains_csv(self.base, DOMAINS_CSV)
            self._imp_msg.config(
                text=f"Imported {total} domains and saved to domains.csv.", fg=GREEN)
            self._refresh()
            if self.cfg["enabled"]: self._apply()
        except Exception as e:
            self._imp_msg.config(text=f"Parse error: {e}", fg=RED)

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Save blocklist",
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv"),("All files","*.*")],
            initialfile=f"haram_blocker_export_{datetime.date.today()}.csv")
        if not path: return
        domains, cmap = all_domains(self.cfg, self.base)
        try:
            with open(path,"w",newline="",encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["domain","category"])
                for d in sorted(domains): w.writerow([d, cmap.get(d,"custom")])
            self._exp_lbl.config(
                text=f"Exported {len(domains)} domains to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    # ── History ───

    def _render_history(self):
        for w in self._hist_inner.winfo_children(): w.destroy()
        log = jload(LOG_FILE, [])
        if not log:
            tk.Label(self._hist_inner, text="No events logged yet.",
                     bg=BG, fg=TEXT3, font=("Segoe UI",10)).pack(pady=28)
            return
        for e in reversed(log[-150:]):
            r = tk.Frame(self._hist_inner, bg=CARD,
                         highlightbackground=BORDER2, highlightthickness=1)
            r.pack(fill="x", pady=2)
            color = GREEN if e["action"]=="enabled" else RED
            tk.Frame(r, bg=color, width=4).pack(side="left", fill="y")
            tk.Label(r, text=e["action"].upper(), bg=CARD, fg=color,
                     width=10, font=("Courier",9,"bold")).pack(side="left", padx=16, pady=12)
            tk.Frame(r, bg=BORDER2, width=1).pack(side="left", fill="y")
            tk.Label(r, text=f"{e['domains']} domains", bg=CARD, fg=TEXT2,
                     font=("Courier",9)).pack(side="left", padx=16)
            tk.Label(r, text=e["time"], bg=CARD, fg=TEXT3,
                     font=("Courier",9)).pack(side="right", padx=16)

    def _clear_history(self):
        if messagebox.askyesno("Clear History","Delete all history entries?"):
            jsave(LOG_FILE, []); self._render_history()

    # ── Settings actions ────

    def _change_pw(self):
        old = simpledialog.askstring("Current Password","Current password:",
                                      show="*", parent=self)
        if old is None: return
        if hash_pw(old) != self.cfg["password_hash"]:
            messagebox.showerror("Wrong Password","Incorrect password."); return
        new1 = simpledialog.askstring("New Password",
            "New password (min 6 characters):", show="*", parent=self)
        if not new1 or len(new1) < 6:
            messagebox.showwarning("Too Short","Minimum 6 characters required."); return
        new2 = simpledialog.askstring("Confirm Password","Confirm new password:",
                                       show="*", parent=self)
        if new1 != new2:
            messagebox.showerror("Mismatch","Passwords do not match."); return
        self.cfg["password_hash"] = hash_pw(new1)
        save_config(self.cfg)
        messagebox.showinfo("Success","Password updated.")

    def _toggle_autostart(self):
        if self._as_var.get():
            p = setup_autostart()
            messagebox.showinfo("Autostart Enabled",f"Will launch at login.\n\n{p}")
        else:
            remove_autostart()
            messagebox.showinfo("Autostart Disabled","Will no longer launch at login.")

    def _open_csv(self):
        for ed in ["kate","gedit","mousepad","xed","pluma","nano"]:
            try: subprocess.Popen([ed, str(DOMAINS_CSV)]); return
            except FileNotFoundError: continue
        subprocess.Popen(["xdg-open", str(DOMAINS_CSV)])

    def _reload_domains(self):
        self.base = load_domains_csv(DOMAINS_CSV)
        self._refresh()
        total = sum(len(v) for v in self.base.values())
        messagebox.showinfo("Reloaded",f"Reloaded {total} domains from domains.csv.")

    # ── Tick 

    def _tick(self):
        # Flush DNS buffer to monitor if on that page
        with self._traf_lock:
            has_new = len(self._traf_buf) != self._traf_len
        if has_new:
            self._traf_len = len(self._traf_buf)
            self._render_monitor()
        self.after(2000, self._tick)


if __name__ == "__main__":
    App().mainloop()