import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
import os
import datetime
import concurrent.futures
import psutil
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  QUEUES & PROOF DATA
# ─────────────────────────────────────────────────────────────────────────────
monitor_queue = queue.Queue()
process_queue = queue.Queue()
cleaner_queue = queue.Queue()

proof_lock = threading.Lock()
proof_data = {
    "monitor_last_wake": "–", "monitor_interval": "–",
    "monitor_raw_cpu": [], "monitor_raw_ram_used": 0,
    "monitor_raw_ram_total": 0,
    "process_last_wake": "–", "process_interval": "–",
    "process_enum_threads": 4, "process_pids_scanned": 0,
    "process_scan_ms": 0, "process_in_list": 0,
    "cleaner_last_wake": "–", "cleaner_threads": 7,
    "cleaner_scan_time": 0.0, "cleaner_files_found": 0,
    "cleaner_status": "IDLE",
}

# ─────────────────────────────────────────────────────────────────────────────
#  CYBERPUNK COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────────────
BG       = "#050a0e"
BG2      = "#080f14"
PANEL_BG = "#060c10"
CYAN     = "#00f5ff"
PINK     = "#ff2d78"
GREEN_N  = "#00ff9d"
YELLOW_N = "#ffe600"
RED_N    = "#ff2d2d"
TXT      = "#c8e6f0"
TXT_DIM  = "#3a6070"
GRID_C   = "#0a2030"

FONT_TITLE = ("Courier New", 13, "bold")
FONT_HEAD  = ("Courier New", 9,  "bold")
FONT_MONO  = ("Courier New", 8)
FONT_BIG   = ("Courier New", 22, "bold")
FONT_MED   = ("Courier New", 14, "bold")
FONT_SM    = ("Courier New", 7)

HISTORY_LEN = 60


def pct_color(pct):
    if pct < 60:  return GREEN_N
    if pct < 85:  return YELLOW_N
    return RED_N


# ─────────────────────────────────────────────────────────────────────────────
#  NEON PANEL  — canvas with notched corner border
# ─────────────────────────────────────────────────────────────────────────────
class NeonPanel(tk.Canvas):
    def __init__(self, parent, color=CYAN, label="", **kwargs):
        kwargs.setdefault("bg", BG2)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)
        self._color = color
        self._label = label
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e=None):
        self.delete("border")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4: return
        c, nc = self._color, 8
        pts = [nc,0, w-nc,0, w,nc, w,h-nc, w-nc,h, nc,h, 0,h-nc, 0,nc]
        self.create_polygon(pts, outline=c, fill=BG2, width=1, tags="border")
        self.create_polygon(pts, outline=c, fill="", width=3,
                            stipple="gray25", tags="border")
        if self._label:
            self.create_text(12, 0, text=f" {self._label} ",
                             anchor="nw", font=FONT_MONO,
                             fill=c, tags="border")


# ─────────────────────────────────────────────────────────────────────────────
#  WAVEFORM CANVAS
# ─────────────────────────────────────────────────────────────────────────────
class WaveformCanvas(tk.Canvas):
    def __init__(self, parent, color=CYAN, maxval=100, **kw):
        kw.setdefault("bg", PANEL_BG)
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._color = color
        self._maxval = maxval
        self._data = [0.0] * HISTORY_LEN
        self.bind("<Configure>", lambda e: self._draw())

    def push(self, val):
        self._data.append(float(val))
        if len(self._data) > HISTORY_LEN:
            self._data.pop(0)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2: return
        for i in range(0, h, max(1, h // 4)):
            self.create_line(0, i, w, i, fill=GRID_C, width=1)
        n  = len(self._data)
        xs = [int(w * i / (n - 1)) for i in range(n)]
        ys = [int(h - (v / self._maxval) * (h - 2)) for v in self._data]
        pts = []
        for x, y in zip(xs, ys):
            pts += [x, y]
        if len(pts) >= 4:
            self.create_line(*pts, fill=self._color, width=2, smooth=True)
        poly_pts = [xs[0], h] + pts + [xs[-1], h]
        self.create_polygon(poly_pts, fill=self._color,
                            stipple="gray12", outline="")
        cur = self._data[-1]
        self.create_text(w - 4, 4, text=f"{cur:.0f}%",
                         anchor="ne", font=FONT_SM, fill=self._color)


# ─────────────────────────────────────────────────────────────────────────────
#  NEON BAR
# ─────────────────────────────────────────────────────────────────────────────
class NeonBar(tk.Canvas):
    def __init__(self, parent, color=CYAN, height=10, **kw):
        kw.setdefault("bg", PANEL_BG)
        kw.setdefault("highlightthickness", 0)
        kw["height"] = height
        super().__init__(parent, **kw)
        self._color = color
        self._pct   = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct):
        self._pct = max(0.0, min(100.0, float(pct)))
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2: return
        self.create_rectangle(0, 0, w, h, fill="#0a1a22", outline="")
        fw = int(w * self._pct / 100)
        col = pct_color(self._pct)
        if fw > 0:
            self.create_rectangle(0, 0, fw, h, fill=col, outline="")
            self.create_rectangle(0, 0, fw, h//2,
                                  fill="white", stipple="gray12", outline="")
        for i in range(10, 100, 10):
            tx = int(w * i / 100)
            self.create_line(tx, 0, tx, 3, fill=GRID_C)


# ═════════════════════════════════════════════════════════════════════════════
#  TAB 1  —  LIVE HARDWARE MONITOR
# ═════════════════════════════════════════════════════════════════════════════
class MonitorTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._core_count = psutil.cpu_count(logical=True)
        self._total_ram  = psutil.virtual_memory().total / (1024**2)
        self._stress_on  = False
        self._build_ui()
        self._start_thread()
        self._poll_gui()

    def _build_ui(self):
        # ── TOP STATUS BAR ──
        top = tk.Frame(self, bg=BG, height=30)
        top.pack(fill=tk.X, padx=6, pady=(4, 0))
        top.pack_propagate(False)

        self._stress_btn = tk.Button(
            top, text="⚡ Stress Test (10 s)",
            font=FONT_HEAD, bg=PINK, fg=BG,
            activebackground="#ff6ba0", relief=tk.FLAT,
            cursor="hand2", bd=0, padx=8,
            command=self._do_stress)
        self._stress_btn.pack(side=tk.LEFT, padx=4)

        self._stress_lbl = tk.Label(top, text="● ACTIVE",
                                     font=FONT_HEAD, fg=GREEN_N, bg=BG)

        self._ts_lbl = tk.Label(top, text="Last update: –",
                                 font=FONT_MONO, fg=TXT_DIM, bg=BG)
        self._ts_lbl.pack(side=tk.RIGHT, padx=8)

        # ── MAIN GRID ──
        main = tk.Frame(self, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=4)
        main.rowconfigure(0, weight=1)

        # ══ LEFT ══
        left = tk.Frame(main, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # Stat cards
        cards = tk.Frame(left, bg=BG)
        cards.pack(fill=tk.X, pady=(0, 4))
        for i in range(3): cards.columnconfigure(i, weight=1)

        mem_p = NeonPanel(cards, color=PINK, label="MEMORY", height=58)
        mem_p.grid(row=0, column=0, padx=3, sticky="nsew")
        self._mem_val = tk.Label(mem_p, text="– MB",
                                  font=FONT_MED, fg=PINK, bg=BG2)
        self._mem_val.place(relx=0.5, rely=0.55, anchor="center")

        cpu_p = NeonPanel(cards, color=CYAN, label="CPU", height=58)
        cpu_p.grid(row=0, column=1, padx=3, sticky="nsew")
        self._cpu_card = tk.Label(cpu_p, text="0%",
                                   font=FONT_MED, fg=CYAN, bg=BG2)
        self._cpu_card.place(relx=0.5, rely=0.55, anchor="center")

        sys_p = NeonPanel(cards, color=CYAN, label="SYSTEM", height=58)
        sys_p.grid(row=0, column=2, padx=3, sticky="nsew")
        self._procs_lbl = tk.Label(sys_p, text="– procs",
                                    font=FONT_MED, fg=CYAN, bg=BG2)
        self._procs_lbl.place(relx=0.5, rely=0.55, anchor="center")

        # CPU Cores panel
        cores_p = NeonPanel(left, color=CYAN, label="CPU CORES")
        cores_p.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        inner = tk.Frame(cores_p, bg=BG2)
        inner.place(relx=0, rely=0, relwidth=1, relheight=1,
                    x=4, y=16, width=-8, height=-20)

        self._c_bars = []
        self._c_lbls = []
        for i in range(self._core_count):
            rf = tk.Frame(inner, bg=BG2)
            rf.pack(fill=tk.X, pady=1, padx=4)
            tk.Label(rf, text=f"Core {i}",
                     font=FONT_MONO, fg=TXT_DIM, bg=BG2,
                     width=6, anchor="w").pack(side=tk.LEFT)
            bar = NeonBar(rf, color=CYAN, height=9)
            bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            lbl = tk.Label(rf, text="   0%",
                            font=FONT_MONO, fg=CYAN, bg=BG2, width=6)
            lbl.pack(side=tk.RIGHT)
            self._c_bars.append(bar)
            self._c_lbls.append(lbl)

        # ══ RIGHT ══
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=2)
        right.rowconfigure(1, weight=2)
        right.rowconfigure(2, weight=1)

        # CPU History
        cpu_hist = NeonPanel(right, color=CYAN, label="CPU HISTORY")
        cpu_hist.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        self._cpu_big = tk.Label(cpu_hist, text="0%",
                                  font=FONT_BIG, fg=CYAN, bg=BG2)
        self._cpu_big.place(relx=0.04, rely=0.10)
        tk.Label(cpu_hist, text="Overall",
                 font=FONT_SM, fg=TXT_DIM, bg=BG2).place(relx=0.04, rely=0.62)
        self._cpu_wave = WaveformCanvas(cpu_hist, color=CYAN,
                                         bg=BG2, highlightthickness=0)
        self._cpu_wave.place(relx=0.26, rely=0.06,
                              relwidth=0.72, relheight=0.90)

        # Memory
        mem_panel = NeonPanel(right, color=PINK, label="MEMORY")
        mem_panel.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        self._mem_big = tk.Label(mem_panel, text="0%",
                                  font=FONT_BIG, fg=PINK, bg=BG2)
        self._mem_big.place(relx=0.04, rely=0.08)
        self._mem_detail = tk.Label(mem_panel, text="",
                                     font=FONT_MONO, fg=TXT_DIM, bg=BG2)
        self._mem_detail.place(relx=0.48, rely=0.20)
        self._mem_bar = NeonBar(mem_panel, color=PINK, height=18)
        self._mem_bar.place(relx=0.04, rely=0.62, relwidth=0.92, height=18)

        # GPU
        gpu_panel = NeonPanel(right, color=PINK, label="GPU")
        gpu_panel.grid(row=2, column=0, sticky="nsew")
        self._gpu_big = tk.Label(gpu_panel, text="0%",
                                  font=FONT_MED, fg=PINK, bg=BG2)
        self._gpu_big.place(relx=0.04, rely=0.12)
        self._gpu_name = tk.Label(gpu_panel,
                                   text=self._detect_gpu(),
                                   font=FONT_MONO, fg=TXT_DIM, bg=BG2)
        self._gpu_name.place(relx=0.28, rely=0.18)
        self._gpu_bar = NeonBar(gpu_panel, color=PINK, height=10)
        self._gpu_bar.place(relx=0.04, rely=0.68, relwidth=0.92, height=10)

    def _detect_gpu(self):
        try:
            import subprocess
            r = subprocess.run(
                ["wmic","path","win32_VideoController","get","name"],
                capture_output=True, text=True, timeout=3)
            lines = [l.strip() for l in r.stdout.splitlines()
                     if l.strip() and l.strip().lower() != "name"]
            return lines[0][:40] if lines else "GPU not detected"
        except:
            return "GPU not detected"

    def _start_thread(self):
        psutil.cpu_percent(interval=None, percpu=True)
        threading.Thread(target=self._poll_hw, daemon=True).start()

    def _poll_hw(self):
        prev = time.monotonic()
        while True:
            t0  = time.monotonic()
            per = psutil.cpu_percent(interval=0.4, percpu=True)
            avg = sum(per) / len(per)
            vm  = psutil.virtual_memory()
            used_mb = vm.used / (1024**2)
            pct_ram = vm.percent
            pids    = len(psutil.pids())
            now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            iv  = (time.monotonic() - prev) * 1000
            prev = time.monotonic()
            with proof_lock:
                proof_data.update({
                    "monitor_last_wake":     now,
                    "monitor_interval":      f"{iv:.0f}ms",
                    "monitor_raw_cpu":       per,
                    "monitor_raw_ram_used":  used_mb,
                    "monitor_raw_ram_total": self._total_ram,
                })
            monitor_queue.put({"per": per, "avg": avg, "used_mb": used_mb,
                                "pct_ram": pct_ram, "pids": pids, "ts": now})
            time.sleep(max(0, 0.5 - (time.monotonic() - t0)))

    def _poll_gui(self):
        try:
            while True:
                d = monitor_queue.get_nowait()
                self._apply(d)
        except queue.Empty:
            pass
        self.after(100, self._poll_gui)

    def _apply(self, d):
        per, avg = d["per"], d["avg"]
        self._cpu_big.config(text=f"{avg:.0f}%", fg=pct_color(avg))
        self._cpu_card.config(text=f"{avg:.0f}%", fg=pct_color(avg))
        self._cpu_wave.push(avg)
        for i, pct in enumerate(per[:len(self._c_bars)]):
            self._c_bars[i].set(pct)
            self._c_bars[i]._color = pct_color(pct)
            self._c_lbls[i].config(text=f"{pct:5.1f}%", fg=pct_color(pct))
        used_mb, pct_ram = d["used_mb"], d["pct_ram"]
        self._mem_big.config(text=f"{pct_ram:.0f}%")
        self._mem_bar.set(pct_ram)
        self._mem_val.config(text=f"{used_mb:.0f} MB")
        self._mem_detail.config(
            text=f"{used_mb:.0f} MB used\nTotal: {self._total_ram:.0f} MB")
        self._procs_lbl.config(text=f"{d['pids']} procs")
        self._ts_lbl.config(text=f"Last update: {d['ts']}")

    def _do_stress(self):
        if self._stress_on: return
        self._stress_on = True
        self._stress_btn.config(state=tk.DISABLED)
        self._stress_lbl.pack(side=tk.LEFT, padx=6)
        n = self._core_count

        def worker():
            end = time.monotonic() + 10
            x   = 1.0
            while time.monotonic() < end:
                x = x * 1.0000001 + 0.0000001

        def run():
            ts = [threading.Thread(target=worker, daemon=True)
                  for _ in range(n)]
            for t in ts: t.start()
            for t in ts: t.join()
            self.after(0, self._stress_end)

        threading.Thread(target=run, daemon=True).start()

    def _stress_end(self):
        self._stress_on = False
        self._stress_btn.config(state=tk.NORMAL)
        self._stress_lbl.pack_forget()


# ═════════════════════════════════════════════════════════════════════════════
#  TAB 2  —  PROCESS CONTROLLER
# ═════════════════════════════════════════════════════════════════════════════
class ProcessTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._all      = []
        self._shown    = []
        self._sort_col = "cpu"
        self._sort_rev = True
        self._filter   = ""
        self._build_ui()
        self._start_thread()
        self._poll_gui()

    def _build_ui(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=8, pady=6)

        tk.Label(top, text="FILTER:", font=FONT_HEAD,
                 fg=TXT_DIM, bg=BG).pack(side=tk.LEFT)
        self._fvar = tk.StringVar()
        self._fvar.trace_add("write", lambda *_: self._refilter())
        tk.Entry(top, textvariable=self._fvar, font=FONT_MONO,
                 bg="#0a1a22", fg=CYAN,
                 insertbackground=CYAN, relief=tk.FLAT,
                 highlightthickness=1, highlightbackground=CYAN,
                 width=22).pack(side=tk.LEFT, padx=6)

        tk.Label(top, text="PATH:", font=FONT_HEAD,
                 fg=TXT_DIM, bg=BG).pack(side=tk.LEFT, padx=(12,0))
        self._pvar = tk.StringVar()
        tk.Entry(top, textvariable=self._pvar, font=FONT_MONO,
                 bg="#0a1a22", fg=PINK, insertbackground=PINK,
                 relief=tk.FLAT, highlightthickness=1,
                 highlightbackground=PINK, width=36
                 ).pack(side=tk.LEFT, padx=4)

        for lbl, cmd, col in [("Browse", self._browse, TXT_DIM),
                                ("Launch ▶", self._launch, GREEN_N)]:
            tk.Button(top, text=lbl, font=FONT_HEAD,
                      bg="#0a1a22", fg=col, relief=tk.FLAT,
                      cursor="hand2", highlightthickness=1,
                      highlightbackground=col,
                      command=cmd, padx=6).pack(side=tk.LEFT, padx=3)

        self._cnt_lbl = tk.Label(top, text="", font=FONT_MONO,
                                  fg=TXT_DIM, bg=BG)
        self._cnt_lbl.pack(side=tk.RIGHT, padx=8)

        style = ttk.Style()
        style.configure("P.Treeview",
                         background=PANEL_BG, foreground=TXT,
                         fieldbackground=PANEL_BG, rowheight=20,
                         font=FONT_MONO, borderwidth=0)
        style.configure("P.Treeview.Heading",
                         background="#0a1a22", foreground=CYAN,
                         font=FONT_HEAD)
        style.map("P.Treeview",
                  background=[("selected","#0a1a22")],
                  foreground=[("selected",CYAN)])

        tf = tk.Frame(self, bg=BG,
                      highlightbackground=CYAN, highlightthickness=1)
        tf.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,4))

        cols = ("name","pid","cpu","ram","status")
        self._tree = ttk.Treeview(tf, columns=cols,
                                   show="headings", style="P.Treeview")
        for c, h, w in [("name","Process Name",210),("pid","PID",70),
                          ("cpu","CPU %",80),("ram","RAM MB",90),
                          ("status","Status",100)]:
            self._tree.heading(c, text=h,
                               command=lambda _c=c: self._sort_by(_c))
            self._tree.column(c, width=w, anchor=tk.W)
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL,
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        btn_f = tk.Frame(self, bg=BG)
        btn_f.pack(fill=tk.X, padx=8, pady=4)
        for lbl, cmd, col in [("⏸ SUSPEND", self._suspend, YELLOW_N),
                                ("▶ RESUME",  self._resume,  GREEN_N),
                                ("✕ KILL",    self._kill,    RED_N)]:
            tk.Button(btn_f, text=lbl, font=FONT_HEAD,
                      bg="#0a1a22", fg=col, relief=tk.FLAT,
                      cursor="hand2", highlightthickness=1,
                      highlightbackground=col,
                      command=cmd, padx=12, pady=4
                      ).pack(side=tk.LEFT, padx=6)

        self._status_lbl = tk.Label(self, text="",
                                     font=FONT_MONO, fg=TXT_DIM, bg=BG)
        self._status_lbl.pack(anchor="w", padx=10)

    def _start_thread(self):
        for p in psutil.process_iter():
            try: p.cpu_percent(interval=None)
            except: pass
        time.sleep(0.5)
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        while True:
            t0   = time.monotonic()
            data = self._enumerate()
            ms   = (time.monotonic() - t0) * 1000
            now  = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            with proof_lock:
                proof_data.update({
                    "process_last_wake":    now,
                    "process_interval":     "2000ms",
                    "process_pids_scanned": len(data),
                    "process_scan_ms":      ms,
                    "process_in_list":      len(data),
                })
            process_queue.put(data)
            time.sleep(2)

    def _enumerate(self):
        pids = [p.pid for p in psutil.process_iter()]
        out  = []
        lk   = threading.Lock()

        def chunk(sub):
            local = []
            for pid in sub:
                try:
                    p = psutil.Process(pid)
                    i = p.as_dict(["pid","name","cpu_percent",
                                   "memory_info","status"])
                    ram = i["memory_info"].rss/(1024**2) if i["memory_info"] else 0
                    local.append({"pid": i["pid"], "name": i["name"] or "–",
                                  "cpu": i["cpu_percent"] or 0.0,
                                  "ram": round(ram, 1),
                                  "status": i["status"] or "?"})
                except: pass
            with lk: out.extend(local)

        sz = max(1, len(pids)//4)
        chunks = [pids[i:i+sz] for i in range(0, len(pids), sz)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            concurrent.futures.wait([ex.submit(chunk, c) for c in chunks])
        return out

    def _poll_gui(self):
        try:
            while True:
                data = process_queue.get_nowait()
                self._all = data
                self._refilter()
        except queue.Empty: pass
        self.after(500, self._poll_gui)

    def _refilter(self):
        f = self._fvar.get().lower()
        self._shown = ([p for p in self._all if f in p["name"].lower()]
                       if f else list(self._all))
        self._sort_by(self._sort_col, toggle=False)
        self._redraw()

    def _sort_by(self, col, toggle=True):
        if toggle:
            if self._sort_col == col: self._sort_rev = not self._sort_rev
            else: self._sort_col = col; self._sort_rev = col in ("cpu","ram")
        self._shown.sort(key=lambda x: x[self._sort_col],
                         reverse=self._sort_rev)
        self._redraw()

    def _redraw(self):
        sel = self._tree.selection()
        sel_pid = None
        if sel:
            try: sel_pid = int(self._tree.item(sel[0])["values"][1])
            except: pass
        self._tree.delete(*self._tree.get_children())
        restore = None
        for p in self._shown:
            iid = self._tree.insert("", tk.END,
                values=(p["name"],p["pid"],f"{p['cpu']:.1f}",
                        f"{p['ram']:.1f}",p["status"]),
                tags=(p["status"],))
            if p["pid"] == sel_pid: restore = iid
        self._tree.tag_configure("running",  foreground=TXT)
        self._tree.tag_configure("sleeping", foreground=TXT_DIM)
        self._tree.tag_configure("stopped",  foreground=YELLOW_N)
        self._tree.tag_configure("zombie",   foreground=RED_N)
        if restore: self._tree.selection_set(restore)
        self._cnt_lbl.config(
            text=f"{len(self._shown)} shown / {len(self._all)} total")

    def _sel_pid(self):
        s = self._tree.selection()
        if not s:
            messagebox.showwarning("SysForge","Select a process first.")
            return None
        return int(self._tree.item(s[0])["values"][1])

    _PROTECTED = {"system","smss.exe","csrss.exe","wininit.exe","lsass.exe"}

    def _browse(self):
        p = filedialog.askopenfilename(
            filetypes=[("Executables","*.exe"),("All","*.*")])
        if p: self._pvar.set(p)

    def _launch(self):
        path = self._pvar.get().strip()
        if not path:
            messagebox.showwarning("SysForge","Enter a path."); return
        try:
            import subprocess; subprocess.Popen([path])
            self._status_lbl.config(
                text=f"Launched: {os.path.basename(path)}", fg=GREEN_N)
        except Exception as e:
            messagebox.showerror("SysForge", str(e))

    def _suspend(self):
        pid = self._sel_pid()
        if pid is None: return
        try:
            p = psutil.Process(pid)
            if p.name().lower() in self._PROTECTED or pid < 10:
                messagebox.showerror("SysForge","Protected process."); return
            p.suspend()
            self._status_lbl.config(text=f"Suspended PID {pid}", fg=YELLOW_N)
        except psutil.AccessDenied:
            messagebox.showerror("SysForge","Access denied — run as Admin.")
        except Exception as e:
            messagebox.showerror("SysForge",str(e))

    def _resume(self):
        pid = self._sel_pid()
        if pid is None: return
        try:
            psutil.Process(pid).resume()
            self._status_lbl.config(text=f"Resumed PID {pid}", fg=GREEN_N)
        except Exception as e:
            messagebox.showerror("SysForge",str(e))

    def _kill(self):
        pid = self._sel_pid()
        if pid is None: return
        try:
            p = psutil.Process(pid)
            if p.name().lower() in self._PROTECTED or pid < 10:
                messagebox.showerror("SysForge","Protected process."); return
            if not messagebox.askyesno("SysForge",
                    f"Kill {p.name()} (PID {pid})?"): return
            p.kill()
            self._status_lbl.config(text=f"Killed PID {pid}", fg=RED_N)
        except psutil.NoSuchProcess:
            self._status_lbl.config(text="Process already gone.", fg=TXT_DIM)
        except Exception as e:
            messagebox.showerror("SysForge",str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  TAB 3  —  PARALLEL SYSTEM CLEANER
# ═════════════════════════════════════════════════════════════════════════════
TARGETS = [
    ("Temp",         r"C:\Windows\Temp"),
    ("Temp",         os.path.expandvars(r"%TEMP%")),
    ("Prefetch",     r"C:\Windows\Prefetch"),
    ("Update Cache", r"C:\Windows\SoftwareDistribution\Download"),
    ("Browser",      os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache")),
    ("Browser",      os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache")),
    ("Recycle Bin",  r"C:\$Recycle.Bin"),
]

class CleanerTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._files    = []
        self._scanning = False
        self._checked  = set()
        self._build_ui()
        self._poll_gui()

    def _build_ui(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=8, pady=6)

        self._scan_btn = tk.Button(
            top, text="🔍 SCAN", font=FONT_HEAD,
            bg="#0a1a22", fg=CYAN, relief=tk.FLAT,
            cursor="hand2", highlightthickness=1,
            highlightbackground=CYAN, padx=10,
            command=self._start_scan)
        self._scan_btn.pack(side=tk.LEFT, padx=4)

        self._prog_lbl = tk.Label(top, text="Idle — click Scan to begin",
                                   font=FONT_MONO, fg=TXT_DIM, bg=BG)
        self._prog_lbl.pack(side=tk.LEFT, padx=8)

        self._time_lbl = tk.Label(top, text="", font=FONT_MONO,
                                   fg=GREEN_N, bg=BG)
        self._time_lbl.pack(side=tk.RIGHT, padx=8)

        self._pbar = ttk.Progressbar(top, mode="indeterminate", length=160)
        self._pbar.pack(side=tk.RIGHT, padx=4)

        self._summ = tk.Label(self, text="", font=FONT_MONO,
                               fg=TXT, bg=BG, justify=tk.LEFT)
        self._summ.pack(anchor="w", padx=10, pady=2)

        style = ttk.Style()
        style.configure("C.Treeview",
                         background=PANEL_BG, foreground=TXT,
                         fieldbackground=PANEL_BG, rowheight=19,
                         font=FONT_MONO, borderwidth=0)
        style.configure("C.Treeview.Heading",
                         background="#0a1a22", foreground=PINK,
                         font=FONT_HEAD)
        style.map("C.Treeview",
                  background=[("selected","#0a1a22")],
                  foreground=[("selected",PINK)])

        tf = tk.Frame(self, bg=BG,
                      highlightbackground=PINK, highlightthickness=1)
        tf.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,4))

        cols = ("sel","path","size","mtime","cat")
        self._tree = ttk.Treeview(tf, columns=cols,
                                   show="headings", style="C.Treeview")
        for c, h, w in [("sel","✓",28),("path","Full Path",380),
                          ("size","Size",80),("mtime","Modified",100),
                          ("cat","Category",110)]:
            self._tree.heading(c, text=h)
            self._tree.column(c, width=w)
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL,
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<Button-1>", self._toggle)

        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=8, pady=4)
        for lbl, cmd, col in [("☑ All", self._sel_all, TXT_DIM),
                                ("☐ None", self._desel_all, TXT_DIM)]:
            tk.Button(bot, text=lbl, font=FONT_MONO,
                      bg="#0a1a22", fg=col, relief=tk.FLAT,
                      cursor="hand2", command=cmd, padx=6
                      ).pack(side=tk.LEFT, padx=4)
        self._del_btn = tk.Button(
            bot, text="🗑 DELETE SELECTED", font=FONT_HEAD,
            bg="#0a1a22", fg=RED_N, relief=tk.FLAT,
            cursor="hand2", highlightthickness=1,
            highlightbackground=RED_N,
            command=self._delete, padx=10)
        self._del_btn.pack(side=tk.RIGHT, padx=4)
        self._dpbar = ttk.Progressbar(bot, mode="determinate", length=180)
        self._dpbar.pack(side=tk.RIGHT, padx=6)

    def _start_scan(self):
        if self._scanning: return
        self._scanning = True
        self._scan_btn.config(state=tk.DISABLED)
        self._files = []
        self._tree.delete(*self._tree.get_children())
        self._checked.clear()
        self._summ.config(text="")
        self._pbar.start(12)
        self._prog_lbl.config(text="Scanning…  0 files", fg=YELLOW_N)
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        t0  = time.monotonic()
        out = []
        lk  = threading.Lock()
        cnt = [0]

        def scan(cat, d):
            p = Path(d)
            if not p.exists(): return
            try: entries = list(p.rglob("*"))
            except: return
            local = []
            for e in entries:
                try:
                    if e.is_file():
                        st = e.stat()
                        kb = st.st_size / 1024
                        mt = datetime.datetime.fromtimestamp(
                            st.st_mtime).strftime("%d/%m/%Y")
                        sz = f"{kb:.1f}KB" if kb < 1024 else f"{kb/1024:.2f}MB"
                        local.append({"path": str(e), "size_kb": kb,
                                      "size_disp": sz, "mtime": mt, "cat": cat})
                except: pass
            with lk:
                out.extend(local)
                cnt[0] += len(local)
                cleaner_queue.put(("prog",
                    f"Scanning {p.name}…  {cnt[0]} files found"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
            concurrent.futures.wait(
                [ex.submit(scan, c, d) for c, d in TARGETS])

        el = time.monotonic() - t0
        with proof_lock:
            proof_data.update({
                "cleaner_last_wake":   datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "cleaner_scan_time":   round(el, 2),
                "cleaner_files_found": len(out),
                "cleaner_status":      "IDLE",
            })
        cleaner_queue.put(("done", out, el))

    def _poll_gui(self):
        try:
            while True:
                m = cleaner_queue.get_nowait()
                if m[0] == "prog":
                    self._prog_lbl.config(text=m[1])
                elif m[0] == "done":
                    self._scan_done(m[1], m[2])
                elif m[0] == "dp":
                    self._dpbar["value"] = m[1]
                    if m[2]:
                        try: self._tree.delete(m[2]); self._checked.discard(m[2])
                        except: pass
                elif m[0] == "dfin":
                    self._del_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("SysForge",
                        f"Deleted {m[1]} files. Freed {m[2]/1024:.2f} MB." +
                        (f"\nFailed: {len(m[3])}." if m[3] else ""))
        except queue.Empty: pass
        self.after(250, self._poll_gui)

    def _scan_done(self, files, el):
        self._files = files
        self._pbar.stop()
        self._scan_btn.config(state=tk.NORMAL)
        self._scanning = False
        self._time_lbl.config(text=f"Scan: {el:.2f}s")
        self._prog_lbl.config(
            text=f"Complete — {len(files)} files found", fg=GREEN_N)
        self._populate(files)
        self._update_summary()

    def _populate(self, files):
        self._tree.delete(*self._tree.get_children())
        self._checked.clear()
        for f in files:
            iid = self._tree.insert("", tk.END,
                values=("✓",f["path"],f["size_disp"],f["mtime"],f["cat"]),
                tags=("on",))
            self._checked.add(iid)
        self._tree.tag_configure("on",  foreground=TXT)
        self._tree.tag_configure("off", foreground=TXT_DIM)

    def _toggle(self, e):
        iid = self._tree.identify_row(e.y)
        if not iid: return
        vals = list(self._tree.item(iid)["values"])
        if iid in self._checked:
            self._checked.discard(iid); vals[0] = "☐"
            self._tree.item(iid, tags=("off",), values=vals)
        else:
            self._checked.add(iid); vals[0] = "✓"
            self._tree.item(iid, tags=("on",), values=vals)
        self._update_summary()

    def _sel_all(self):
        for iid in self._tree.get_children():
            self._checked.add(iid)
            v = list(self._tree.item(iid)["values"]); v[0] = "✓"
            self._tree.item(iid, tags=("on",), values=v)
        self._update_summary()

    def _desel_all(self):
        for iid in self._tree.get_children():
            self._checked.discard(iid)
            v = list(self._tree.item(iid)["values"]); v[0] = "☐"
            self._tree.item(iid, tags=("off",), values=v)
        self._update_summary()

    def _update_summary(self):
        if not self._files: return
        cats = {}
        tot  = 0
        for f in self._files:
            c = f["cat"]
            cats.setdefault(c, {"n":0,"kb":0})
            cats[c]["n"] += 1; cats[c]["kb"] += f["size_kb"]; tot += f["size_kb"]
        parts = " | ".join(
            f"{c}: {v['n']} ({v['kb']/1024:.1f}MB)" for c,v in cats.items())
        self._summ.config(
            text=f"Total: {len(self._files)} files ({tot/1024:.1f} MB)   {parts}")

    def _delete(self):
        iids = [(iid, self._tree.item(iid)["values"][1])
                for iid in self._checked]
        if not iids:
            messagebox.showinfo("SysForge","Nothing selected."); return
        kb = sum(f["size_kb"] for f in self._files
                 if any(f["path"] == p for _,p in iids))
        if not messagebox.askyesno("SysForge — Confirm",
                f"Delete {len(iids)} files ({kb/1024:.1f} MB)?\nCannot be undone."):
            return
        self._del_btn.config(state=tk.DISABLED)
        self._dpbar["maximum"] = len(iids)
        self._dpbar["value"]   = 0

        safe = [d for _,d in TARGETS]
        def is_safe(path):
            for r in safe:
                try:
                    if Path(path).is_relative_to(Path(r)): return True
                except: pass
            return False

        def worker():
            done=0; freed=0; failed=[]
            lk2=threading.Lock()
            def rm(item):
                nonlocal done, freed
                iid, path = item
                if not is_safe(path): return
                try:
                    sz = Path(path).stat().st_size/1024
                    os.remove(path)
                    with lk2: done+=1; freed+=sz
                    cleaner_queue.put(("dp", done, iid))
                except:
                    with lk2: failed.append(path)
                    cleaner_queue.put(("dp", done, None))
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
                concurrent.futures.wait([ex.submit(rm,i) for i in iids])
            cleaner_queue.put(("dfin", done, freed, failed))

        threading.Thread(target=worker, daemon=True).start()


# ═════════════════════════════════════════════════════════════════════════════
#  PROOF PANEL  (F2)
# ═════════════════════════════════════════════════════════════════════════════
class ProofPanel(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("SysForge — Live Proof Panel")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.geometry("540x320+20+20")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        hdr = tk.Frame(self, bg=BG,
                        highlightbackground=CYAN, highlightthickness=1)
        hdr.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(hdr, text="[ SYSFORGE LIVE PROOF PANEL ]  F2 to hide",
                 font=FONT_HEAD, fg=CYAN, bg=BG).pack(pady=4)

        self._txt = tk.Text(self, font=("Courier New", 8),
                             bg=BG, fg=GREEN_N, relief=tk.FLAT,
                             width=68, height=15,
                             state=tk.DISABLED,
                             highlightbackground=CYAN,
                             highlightthickness=1)
        self._txt.pack(padx=6, pady=4)
        self._tick()

    def _tick(self):
        with proof_lock:
            d = dict(proof_data)
        cpu_s = ", ".join(f"{v:.1f}" for v in d["monitor_raw_cpu"][:6])
        if len(d["monitor_raw_cpu"]) > 6: cpu_s += "…"
        lines = [
            "BACKGROUND THREADS",
            f"  Monitor  ACTIVE  last:{d['monitor_last_wake']}  iv:{d['monitor_interval']}",
            f"  Process  ACTIVE  last:{d['process_last_wake']}  iv:{d['process_interval']}",
            f"  Cleaner  {d['cleaner_status']:<5}  last:{d['cleaner_last_wake']}",
            "",
            "MONITOR",
            f"  API: psutil (cpu_percent + virtual_memory)",
            f"  raw CPU: [{cpu_s}]",
            f"  raw RAM: {d['monitor_raw_ram_used']:.0f}MB / {d['monitor_raw_ram_total']:.0f}MB",
            "",
            "PROCESS THREAD",
            f"  threads:{d['process_enum_threads']}  PIDs:{d['process_pids_scanned']}"
            f"  dur:{d['process_scan_ms']:.0f}ms  list:{d['process_in_list']}",
            "",
            "CLEANER (last scan)",
            f"  threads:{d['cleaner_threads']}  time:{d['cleaner_scan_time']:.2f}s"
            f"  files:{d['cleaner_files_found']}",
        ]
        self._txt.config(state=tk.NORMAL)
        self._txt.delete("1.0", tk.END)
        self._txt.insert("1.0", "\n".join(lines))
        self._txt.config(state=tk.DISABLED)
        self.after(1000, self._tick)


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════════════
class SysForge(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SYS:FORGE CORE")
        self.configure(bg=BG)
        self.geometry("1180x740")
        self.minsize(900, 600)
        self._proof = None
        self._build()
        self.bind_all("<F2>", self._toggle_proof)

    def _build(self):
        # Title bar
        tb = tk.Frame(self, bg=BG, height=36)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)

        tk.Label(tb, text="◈ SYS",
                 font=("Courier New",15,"bold"),
                 fg=CYAN, bg=BG).pack(side=tk.LEFT, padx=(10,0))
        tk.Label(tb, text=":FORGE CORE",
                 font=("Courier New",15,"bold"),
                 fg=PINK, bg=BG).pack(side=tk.LEFT)
        tk.Label(tb, text="  //  PARALLEL WINDOWS SYSTEM UTILITY",
                 font=FONT_MONO, fg=TXT_DIM, bg=BG).pack(side=tk.LEFT, pady=4)

        self._clock = tk.Label(tb, text="",
                                font=FONT_HEAD, fg=TXT_DIM, bg=BG)
        self._clock.pack(side=tk.RIGHT, padx=14)
        tk.Label(tb, text="F2 ▸ PROOF PANEL",
                 font=FONT_MONO, fg=TXT_DIM, bg=BG).pack(side=tk.RIGHT)
        self._tick_clock()

        # Neon divider (2px — cyan + pink lines)
        div = tk.Canvas(self, height=2, bg=BG, highlightthickness=0)
        div.pack(fill=tk.X)
        div.bind("<Configure>", lambda e: (
            div.delete("all"),
            div.create_line(0,0,e.width,0, fill=CYAN, width=1),
            div.create_line(0,1,e.width,1, fill=PINK, width=1)))

        # Notebook
        style = ttk.Style()
        style.configure("SF.TNotebook",
                         background=BG, borderwidth=0,
                         tabmargins=[0,0,0,0])
        style.configure("SF.TNotebook.Tab",
                         background="#0a1a22", foreground=TXT_DIM,
                         font=FONT_HEAD, padding=[16,6], borderwidth=0)
        style.map("SF.TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", CYAN)],
                  focuscolor=[("selected", BG)])

        nb = ttk.Notebook(self, style="SF.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True)

        self._t1 = MonitorTab(nb)
        self._t2 = ProcessTab(nb)
        self._t3 = CleanerTab(nb)

        nb.add(self._t1, text="  ◈ Monitor  ")
        nb.add(self._t2, text="  ◈ Processes  ")
        nb.add(self._t3, text="  ◈ Cleaner  ")

    def _tick_clock(self):
        self._clock.config(
            text=datetime.datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _toggle_proof(self, _=None):
        if self._proof is None:
            self._proof = ProofPanel(self)
        elif self._proof.winfo_viewable():
            self._proof.withdraw()
        else:
            self._proof.deiconify()


if __name__ == "__main__":
    app = SysForge()
    app.mainloop()