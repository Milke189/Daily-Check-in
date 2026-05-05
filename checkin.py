"""
每日签到计数器 - Daily Check-in Counter
支持多项目签到：每个项目独立追踪签到记录
"""

import json
import os
import tkinter as tk
from tkinter import messagebox, simpledialog
from datetime import datetime, timedelta

# 数据文件路径
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkin_data.json")

# 主题色
C = {
    "bg":       "#1a1a2e",
    "surface":  "#16213e",
    "bar":      "#0f0f23",
    "accent":   "#e94560",
    "green":    "#2ecc71",
    "text":     "#eaeaea",
    "dim":      "#8892b0",
    "muted":    "#4a5568",
    "white":    "#ffffff",
    "dark_red": "#c73e54",
}

EMPTY_PROJECT = {
    "total": 0,
    "streak": 0,
    "max_streak": 0,
    "last_checkin": None,
    "history": [],
}


def load_data():
    """加载数据，兼容旧版格式"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "total" in data and "projects" not in data:
                old = {k: data.get(k, v) for k, v in EMPTY_PROJECT.items()}
                data = {"projects": {"默认": old}, "current": "默认"}
            if "projects" not in data:
                data["projects"] = {"默认": dict(EMPTY_PROJECT)}
            if "current" not in data or data["current"] not in data["projects"]:
                data["current"] = list(data["projects"].keys())[0]
            for proj in data["projects"].values():
                for key in EMPTY_PROJECT:
                    if key not in proj:
                        proj[key] = EMPTY_PROJECT[key]
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"projects": {"默认": dict(EMPTY_PROJECT)}, "current": "默认"}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════
#  主应用
# ══════════════════════════════════════════════════════════════

class CheckinApp:
    def __init__(self, root):
        self.root = root
        self.root.title("每日签到器")
        self.root.geometry("420x620")
        self.root.resizable(False, False)
        self.root.configure(bg=C["bg"])

        self.data = load_data()
        self.today = datetime.now().strftime("%Y-%m-%d")
        self._cal_win = None   # 日历窗口单例
        self._cal_draw = None  # 日历重绘函数

        self.build_ui()
        self.render_tabs()
        self.refresh_display()

        self.root.bind("<Control-r>", lambda e: self.reset_data())

    # ── 数据快捷访问 ──

    def proj(self):
        return self.data["projects"][self.data["current"]]

    def checked_today(self):
        return self.proj()["last_checkin"] == self.today

    # ──────────────────────────────────────────────────────────
    #  UI 构建
    # ──────────────────────────────────────────────────────────

    def build_ui(self):
        bg, surface, bar = C["bg"], C["surface"], C["bar"]

        # ─ 可滚动主区域 ─
        outer = tk.Frame(self.root, bg=bg)
        outer.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(outer, bg=bg, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.main = tk.Frame(self.canvas, bg=bg)
        self._win_id = self.canvas.create_window((0, 0), window=self.main, anchor="nw")

        self.main.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self._win_id, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        F = self.main  # 所有子组件挂在此 Frame 上

        # ─ 顶部栏 ─
        top = tk.Frame(F, bg=bg)
        top.pack(fill="x", padx=20, pady=(16, 0))

        tk.Label(top, text=datetime.now().strftime("%Y.%m.%d"),
                 font=("Consolas", 11), bg=bg, fg=C["muted"]).pack(side="left")

        tk.Button(top, text="\U0001f4c5", font=("Segoe UI Emoji", 13),
                  bg=bar, fg=C["dim"], relief="flat", bd=0, cursor="hand2",
                  activebackground=bar, activeforeground=C["text"],
                  command=self.show_calendar).pack(side="right", padx=(4, 0))

        tk.Button(top, text="⚙", font=("Segoe UI Symbol", 13),
                  bg=bar, fg=C["dim"], relief="flat", bd=0, cursor="hand2",
                  activebackground=bar, activeforeground=C["text"],
                  command=self.open_settings).pack(side="right")

        # ─ 项目标签栏 ─
        self.tab_frame = tk.Frame(F, bg=bg)
        self.tab_frame.pack(fill="x", padx=20, pady=(12, 0))

        self.tab_bar = tk.Frame(self.tab_frame, bg=bg)
        self.tab_bar.pack(fill="x")

        # ─ 项目名 ─
        self.project_label = tk.Label(F, text="", font=("Microsoft YaHei UI", 22, "bold"),
                                      bg=bg, fg=C["text"])
        self.project_label.pack(pady=(16, 0))

        # ─ 大数字 ─
        self.total_label = tk.Label(F, text="0",
                                    font=("Microsoft YaHei UI", 72, "bold"),
                                    bg=bg, fg=C["accent"])
        self.total_label.pack(pady=(12, 0))

        tk.Label(F, text="累计签到天数", font=("Microsoft YaHei UI", 11),
                 bg=bg, fg=C["dim"]).pack()

        # ─ 签到按钮 ─
        self.btn = tk.Button(F, text="签 到 +1",
                             font=("Microsoft YaHei UI", 16, "bold"),
                             bg=C["accent"], fg=C["white"],
                             activebackground=C["dark_red"], activeforeground=C["white"],
                             relief="flat", cursor="hand2", bd=0, padx=50, pady=10,
                             command=self.checkin)
        self.btn.pack(pady=18)

        # ─ 信息卡片 ─
        cards = tk.Frame(F, bg=bg)
        cards.pack(padx=24, fill="x")

        self.streak_card = self._card(cards, "当前连续", "0 天")
        self.streak_card.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.max_card = self._card(cards, "最长连续", "0 天")
        self.max_card.pack(side="right", expand=True, fill="x", padx=(6, 0))

        # ─ 状态 ─
        self.status_label = tk.Label(F, text="", font=("Microsoft YaHei UI", 10),
                                     bg=bg, fg=C["green"])
        self.status_label.pack(pady=(10, 0))


    def _card(self, parent, title, value):
        f = tk.Frame(parent, bg=C["surface"], padx=16, pady=10)
        tk.Label(f, text=title, font=("Microsoft YaHei UI", 9),
                 bg=C["surface"], fg=C["dim"]).pack()
        vl = tk.Label(f, text=value, font=("Microsoft YaHei UI", 20, "bold"),
                      bg=C["surface"], fg=C["text"])
        vl.pack()
        f._val = vl
        return f

    # ──────────────────────────────────────────────────────────
    #  标签栏
    # ──────────────────────────────────────────────────────────

    def render_tabs(self):
        for w in self.tab_bar.winfo_children():
            w.destroy()

        active = self.data["current"]
        for name in self.data["projects"]:
            is_on = (name == active)
            lbl = tk.Label(self.tab_bar, text=f" {name} ",
                           font=("Microsoft YaHei UI", 9, "bold" if is_on else "normal"),
                           bg=C["accent"] if is_on else C["surface"],
                           fg=C["white"] if is_on else C["dim"],
                           padx=10, pady=4, cursor="hand2")
            lbl.pack(side="left", padx=(0, 4))
            lbl.bind("<Button-1>", lambda e, n=name: self.switch_project(n))
            lbl.bind("<Button-3>", lambda e, n=name: self._tab_menu(e, n))

        add = tk.Label(self.tab_bar, text=" + ",
                       font=("Microsoft YaHei UI", 12, "bold"),
                       bg=C["surface"], fg=C["green"], padx=8, pady=2, cursor="hand2")
        add.pack(side="left", padx=(4, 0))
        add.bind("<Button-1>", lambda e: self.add_project())

    def _tab_menu(self, event, name):
        m = tk.Menu(self.root, tearoff=0,
                    bg=C["surface"], fg=C["text"],
                    activebackground=C["accent"], activeforeground=C["white"],
                    font=("Microsoft YaHei UI", 9))
        m.add_command(label="重命名", command=lambda: self.rename_project(name))
        m.add_command(label="删除", command=lambda: self.delete_project(name))
        m.tk_popup(event.x_root, event.y_root)

    def switch_project(self, name):
        if name == self.data["current"]:
            return
        self.data["current"] = name
        save_data(self.data)
        self.render_tabs()
        self.refresh_display()
        self._refresh_calendar()

    def add_project(self):
        name = simpledialog.askstring("新建项目", "请输入项目名称：",
                                      parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.data["projects"]:
            messagebox.showwarning("提示", f'项目 "{name}" 已存在！')
            return
        self.data["projects"][name] = dict(EMPTY_PROJECT)
        self.data["current"] = name
        save_data(self.data)
        self.render_tabs()
        self.refresh_display()

    def rename_project(self, old):
        new = simpledialog.askstring("重命名", "新名称：",
                                     initialvalue=old, parent=self.root)
        if not new or not new.strip() or new.strip() == old:
            return
        new = new.strip()
        if new in self.data["projects"]:
            messagebox.showwarning("提示", f'"{new}" 已存在！')
            return
        self.data["projects"][new] = self.data["projects"].pop(old)
        if self.data["current"] == old:
            self.data["current"] = new
        save_data(self.data)
        self.render_tabs()
        self.refresh_display()

    def delete_project(self, name):
        if len(self.data["projects"]) <= 1:
            messagebox.showinfo("提示", "至少保留一个项目。")
            return
        if not messagebox.askyesno("确认删除",
                                   f'确定要删除 "{name}" 及其所有签到数据吗？'):
            return
        del self.data["projects"][name]
        if self.data["current"] == name:
            self.data["current"] = list(self.data["projects"].keys())[0]
        save_data(self.data)
        self.render_tabs()
        self.refresh_display()

    # ──────────────────────────────────────────────────────────
    #  设置面板
    # ──────────────────────────────────────────────────────────

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("300x200")
        win.configure(bg=C["bg"])
        win.resizable(False, False)

        tk.Label(win, text="设置", font=("Microsoft YaHei UI", 14, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(pady=(20, 15))

        tk.Button(win, text="重置当前项目数据",
                  font=("Microsoft YaHei UI", 11), bg=C["accent"], fg=C["white"],
                  relief="flat", cursor="hand2", bd=0, padx=20, pady=8,
                  activebackground=C["dark_red"], activeforeground=C["white"],
                  command=lambda: [win.destroy(), self.reset_data()]).pack(pady=6)

        tk.Button(win, text="新建项目",
                  font=("Microsoft YaHei UI", 11), bg=C["surface"], fg=C["text"],
                  relief="flat", cursor="hand2", bd=0, padx=20, pady=8,
                  command=lambda: [win.destroy(), self.add_project()]).pack(pady=6)

    # ──────────────────────────────────────────────────────────
    #  显示刷新
    # ──────────────────────────────────────────────────────────

    def refresh_display(self):
        p = self.proj()
        self.project_label.config(text=self.data["current"])
        self.total_label.config(text=str(p["total"]))
        self.streak_card._val.config(text=f'{p["streak"]} 天')
        self.max_card._val.config(text=f'{p["max_streak"]} 天')

        if self.checked_today():
            self.btn.config(state="disabled", bg="#555", text="今日已签到 ✓")
            t = p["history"][-1].split(" ")[1] if p["history"] else ""
            self.status_label.config(text=f"签到时间: {t}", fg=C["green"])
        else:
            self.btn.config(state="normal", bg=C["accent"], text="签 到 +1")
            self.status_label.config(text="今天还没有签到哦", fg=C["accent"])

    # ──────────────────────────────────────────────────────────
    #  签到逻辑
    # ──────────────────────────────────────────────────────────

    def checkin(self):
        if self.checked_today():
            messagebox.showinfo("提示", "今天已经签到过了！明天再来吧~")
            return

        p = self.proj()
        now = datetime.now()
        d = now.strftime("%Y-%m-%d")
        t = now.strftime("%H:%M:%S")

        if p["last_checkin"]:
            last = datetime.strptime(p["last_checkin"], "%Y-%m-%d")
            p["streak"] = p["streak"] + 1 if (now - last).days == 1 else 1
        else:
            p["streak"] = 1

        p["total"] += 1
        p["last_checkin"] = d
        p["history"].append(f"{d} {t}")
        if len(p["history"]) > 50:
            p["history"] = p["history"][-50:]
        if p["streak"] > p["max_streak"]:
            p["max_streak"] = p["streak"]

        save_data(self.data)
        self.refresh_display()
        self._refresh_calendar()
        self._pulse()

    def reset_data(self):
        name = self.data["current"]
        if not messagebox.askyesno("确认重置",
                                   f'确定要重置 "{name}" 的所有数据吗？\n此操作不可撤销！'):
            return
        self.data["projects"][name] = dict(EMPTY_PROJECT)
        save_data(self.data)
        self.refresh_display()
        self._refresh_calendar()
        self.status_label.config(text="数据已重置", fg=C["accent"])

    def _pulse(self):
        o = self.total_label.cget("fg")
        for i, c in enumerate([C["green"], o, C["green"], o]):
            self.root.after(i * 180, lambda c=c: self.total_label.config(fg=c))

    # ──────────────────────────────────────────────────────────
    #  日历视图（单例窗口，跟随当前项目实时刷新）
    # ──────────────────────────────────────────────────────────

    def _refresh_calendar(self):
        """若日历窗口已打开，则用当前项目数据重绘"""
        if self._cal_win and self._cal_win.winfo_exists():
            if self._cal_draw:
                self._cal_draw()
        else:
            self._cal_win = None
            self._cal_draw = None

    def show_calendar(self):
        # 若已打开则前置并刷新
        if self._cal_win and self._cal_win.winfo_exists():
            self._cal_win.lift()
            self._refresh_calendar()
            return

        now = datetime.now()
        st = {"y": now.year, "m": now.month}

        win = tk.Toplevel(self.root)
        win.title("签到日历")
        win.geometry("400x440")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        self._cal_win = win

        # ─ 头部 ─
        hdr = tk.Frame(win, bg=C["bg"])
        hdr.pack(fill="x", padx=16, pady=(14, 4))
        tl = tk.Label(hdr, text="", font=("Microsoft YaHei UI", 14, "bold"),
                      bg=C["bg"], fg=C["text"])
        tl.pack(side="left")
        stat = tk.Label(hdr, text="", font=("Microsoft YaHei UI", 10),
                        bg=C["bg"], fg=C["dim"])
        stat.pack(side="right")

        # ─ 导航 ─
        nav = tk.Frame(win, bg=C["bg"])
        nav.pack(fill="x", padx=16, pady=(0, 8))
        ml = tk.Label(nav, text="", font=("Microsoft YaHei UI", 13, "bold"),
                      bg=C["bg"], fg=C["text"])
        ml.pack()

        btn_frame = tk.Frame(nav, bg=C["bg"])
        btn_frame.place(relx=0.0, rely=0.5, anchor="w")
        pb = tk.Button(btn_frame, text="◀", font=("Microsoft YaHei UI", 11),
                       bg=C["surface"], fg=C["text"], relief="flat", bd=0,
                       padx=10, cursor="hand2")
        pb.pack(side="left")

        btn_frame2 = tk.Frame(nav, bg=C["bg"])
        btn_frame2.place(relx=1.0, rely=0.5, anchor="e")
        nb = tk.Button(btn_frame2, text="▶", font=("Microsoft YaHei UI", 11),
                       bg=C["surface"], fg=C["text"], relief="flat", bd=0,
                       padx=10, cursor="hand2")
        nb.pack(side="right")

        # ─ 星期头 ─
        wk = tk.Frame(win, bg=C["bg"])
        wk.pack(fill="x", padx=16)
        for d in ["一", "二", "三", "四", "五", "六", "日"]:
            tk.Label(wk, text=d, font=("Microsoft YaHei UI", 10, "bold"),
                     bg=C["bg"], fg=C["dim"], width=5).pack(side="left", expand=True)

        # ─ 网格 ─
        grid = tk.Frame(win, bg=C["bg"])
        grid.pack(fill="both", expand=True, padx=16, pady=(4, 14))

        def draw():
            # 每次重绘都从当前项目读取最新数据
            p = self.proj()
            name = self.data["current"]
            checked = set(r.split(" ")[0] for r in p["history"])

            win.title(f"签到日历 — {name}")
            for w in grid.winfo_children():
                w.destroy()

            y, m = st["y"], st["m"]
            tl.config(text=f"{name}  {y}年{m}月")
            stat.config(text=f"共 {p['total']} 天")
            ml.config(text=f"{y}年{m}月")
            pb.config(command=lambda: nav_m(-1))
            nb.config(command=lambda: nav_m(1))

            first = datetime(y, m, 1)
            last = (datetime(y + 1, 1, 1) - timedelta(days=1) if m == 12
                    else datetime(y, m + 1, 1) - timedelta(days=1))
            days = last.day
            sc = first.weekday()

            for d in range(1, days + 1):
                r, c = (sc + d - 1) // 7, (sc + d - 1) % 7
                ds = f"{y}-{m:02d}-{d:02d}"
                hit = ds in checked
                today = (y == now.year and m == now.month and d == now.day)

                bg = C["green"] if hit else C["surface"]
                fg = C["white"] if hit else (C["text"] if not today else C["accent"])
                ft = ("Microsoft YaHei UI", 11, "bold") if (hit or today) else ("Microsoft YaHei UI", 10)

                cell = tk.Label(grid, text=str(d), font=ft, bg=bg, fg=fg,
                                width=5, height=2, relief="flat", anchor="center")
                cell.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")

                if today and not hit:
                    cell.config(highlightbackground=C["accent"], highlightthickness=1)

            for c in range(7):
                grid.columnconfigure(c, weight=1)

        def nav_m(delta):
            st["m"] += delta
            if st["m"] > 12:
                st["m"], st["y"] = 1, st["y"] + 1
            elif st["m"] < 1:
                st["m"], st["y"] = 12, st["y"] - 1
            draw()

        self._cal_draw = draw
        draw()


# ══════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    root.update_idletasks()
    w, h = 420, 620
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")
    CheckinApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
