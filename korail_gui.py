# -*- coding: utf-8 -*-
"""korail2 를 쓰는 데스크톱 GUI (Tkinter).

    $ python korail_gui.py

추가 설치가 필요 없다. 비밀번호는 화면에서 가려지고, 파일이나 로그에
기록하지 않는다. 로그인 성공 후에는 입력칸에서도 지운다.
"""
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from korail2 import (AdultPassenger, ChildPassenger, Korail, KorailError,
                     NeedToLoginError, NoResultsError, ReserveOption,
                     SeniorPassenger, SoldOutError, ToddlerPassenger,
                     TrainType)
from korail2.korail2 import KST

APP_TITLE = "korail2 승차권 조회·예약"

# 코레일이 같은 코드로 묶는 종별은 라벨도 합쳐서 보여준다.
TRAIN_TYPES = [
    ("전체", TrainType.ALL),
    ("KTX / KTX-산천", TrainType.KTX),
    ("새마을 / ITX-새마을", TrainType.SAEMAEUL),
    ("무궁화 / 누리로", TrainType.MUGUNGHWA),
    ("통근열차", TrainType.TONGGEUN),
    ("ITX-청춘", TrainType.ITX_CHEONGCHUN),
    ("공항직통", TrainType.AIRPORT),
]

RESERVE_OPTIONS = [
    ("일반실 우선", ReserveOption.GENERAL_FIRST),
    ("일반실만", ReserveOption.GENERAL_ONLY),
    ("특실 우선", ReserveOption.SPECIAL_FIRST),
    ("특실만", ReserveOption.SPECIAL_ONLY),
]

MIN_POLL_INTERVAL = 10  # 초. 코레일이 자동화를 차단하므로 더 짧게 두지 않는다.


def kst_now():
    """코레일 API 는 한국시간 기준이다."""
    return datetime.now(KST)


def fmt_time(hhmmss):
    return "%s:%s" % (hhmmss[:2], hhmmss[2:4])


class KorailApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x660")
        self.minsize(880, 600)

        self.korail = None
        self._api_lock = threading.Lock()   # Korail 세션을 한 번에 하나씩만 쓴다
        self._ui_queue = queue.Queue()      # 워커 -> Tk 메인 스레드
        self._stop_polling = threading.Event()
        self._poll_thread = None
        self._drain_job = None
        self._trains = {}                   # treeview iid -> Train
        self._reservations = {}             # treeview iid -> Reservation

        self._build_account_bar()
        self._build_body()
        self._build_statusbar()
        self._set_logged_in(False)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._drain_job = self.after(100, self._drain_ui_queue)

    # ------------------------------------------------------------------
    # 스레드 처리: 네트워크는 워커에서, 위젯 갱신은 메인 스레드에서만.
    # ------------------------------------------------------------------
    def _drain_ui_queue(self):
        try:
            while True:
                self._ui_queue.get_nowait()()
        except queue.Empty:
            pass
        self._drain_job = self.after(100, self._drain_ui_queue)

    def post(self, fn):
        self._ui_queue.put(fn)

    def run_async(self, work, on_success, on_error=None):
        def worker():
            try:
                with self._api_lock:
                    result = work()
            except Exception as exc:
                self.post(lambda e=exc: (on_error or self._show_error)(e))
            else:
                self.post(lambda r=result: on_success(r))
        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, exc):
        self.set_status(str(exc))
        messagebox.showerror("오류", str(exc), parent=self)

    # ------------------------------------------------------------------
    # 화면 구성
    # ------------------------------------------------------------------
    def _build_account_bar(self):
        bar = ttk.LabelFrame(self, text="계정")
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="아이디").grid(row=0, column=0, padx=(8, 4), pady=8)
        self.var_id = tk.StringVar(value=os.environ.get("KORAIL_ID", ""))
        ttk.Entry(bar, textvariable=self.var_id, width=22).grid(row=0, column=1)

        ttk.Label(bar, text="비밀번호").grid(row=0, column=2, padx=(12, 4))
        self.var_pw = tk.StringVar()
        pw = ttk.Entry(bar, textvariable=self.var_pw, width=22, show="•")
        pw.grid(row=0, column=3)
        pw.bind("<Return>", lambda _e: self.on_login())

        self.btn_login = ttk.Button(bar, text="로그인", command=self.on_login)
        self.btn_login.grid(row=0, column=4, padx=8)
        self.btn_logout = ttk.Button(bar, text="로그아웃", command=self.on_logout)
        self.btn_logout.grid(row=0, column=5)

        self.lbl_account = ttk.Label(bar, text="로그아웃 상태", foreground="#a00")
        self.lbl_account.grid(row=0, column=6, padx=12)

        ttk.Label(bar, foreground="#666",
                  text="회원번호 / 이메일 / 010-0000-0000 형식 모두 사용할 수 있습니다."
                  ).grid(row=1, column=0, columnspan=7, sticky="w", padx=8, pady=(0, 6))

    def _build_body(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_criteria(body)

        self.nb = ttk.Notebook(body)
        self.nb.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._build_results_tab()
        self._build_auto_tab()
        self._build_reservations_tab()

    def _build_criteria(self, parent):
        box = ttk.LabelFrame(parent, text="검색 조건")
        box.pack(side="left", fill="y")

        now = kst_now()
        rows = [
            ("출발역", "var_dep", tk.StringVar(value="서울")),
            ("도착역", "var_arr", tk.StringVar(value="부산")),
            ("날짜 (yyyyMMdd)", "var_date", tk.StringVar(value=now.strftime("%Y%m%d"))),
            ("시각 (hhmmss)", "var_time", tk.StringVar(value=now.strftime("%H%M%S"))),
        ]
        for i, (label, attr, var) in enumerate(rows):
            ttk.Label(box, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            setattr(self, attr, var)
            ttk.Entry(box, textvariable=var, width=18).grid(row=i, column=1, padx=(0, 8))

        row = len(rows)
        ttk.Label(box, text="열차 종별").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.cbo_type = ttk.Combobox(box, width=16, state="readonly",
                                     values=[t[0] for t in TRAIN_TYPES])
        self.cbo_type.current(0)
        self.cbo_type.grid(row=row, column=1, padx=(0, 8))

        row += 1
        ttk.Separator(box, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8)

        row += 1
        ttk.Label(box, text="승객", font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8)

        self.psgr_vars = {}
        for label, key, default in [("어른", "adult", 1), ("어린이", "child", 0),
                                    ("유아", "toddler", 0), ("경로", "senior", 0)]:
            row += 1
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", padx=(20, 8), pady=2)
            var = tk.IntVar(value=default)
            self.psgr_vars[key] = var
            ttk.Spinbox(box, from_=0, to=9, width=5, textvariable=var).grid(
                row=row, column=1, sticky="w")

        row += 1
        ttk.Separator(box, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8)

        row += 1
        ttk.Label(box, text="좌석 등급").grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.cbo_option = ttk.Combobox(box, width=16, state="readonly",
                                       values=[o[0] for o in RESERVE_OPTIONS])
        self.cbo_option.current(0)
        self.cbo_option.grid(row=row, column=1, padx=(0, 8))

        row += 1
        self.var_no_seats = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="매진 열차도 표시", variable=self.var_no_seats).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8)

        row += 1
        self.var_waiting = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="예약 대기 가능 열차 포함",
                        variable=self.var_waiting).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8)

        row += 1
        self.var_allday = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="하루 전체 조회 (느림)", variable=self.var_allday).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8)

        row += 1
        self.btn_search = ttk.Button(box, text="열차 조회", command=self.on_search)
        self.btn_search.grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=12)

    def _build_results_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="조회 결과")

        holder = ttk.Frame(tab)
        holder.pack(side="top", fill="both", expand=True, padx=4, pady=4)

        cols = ("type", "dep", "arr", "seat")
        self.tree = ttk.Treeview(holder, columns=cols, show="headings",
                                 selectmode="browse")
        for col, text, width in [("type", "열차", 130), ("dep", "출발", 150),
                                 ("arr", "도착", 150), ("seat", "좌석", 240)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")

        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.on_reserve())

        actions = ttk.Frame(tab)
        actions.pack(fill="x", padx=4, pady=(0, 6))
        self.btn_reserve = ttk.Button(actions, text="선택한 열차 예약",
                                      command=self.on_reserve)
        self.btn_reserve.pack(side="left")
        ttk.Label(actions, foreground="#666",
                  text="  예약은 결제 기한이 있는 실제 예약입니다.").pack(side="left")

    def _build_auto_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="자동 좌석 대기")

        warn = ttk.LabelFrame(tab, text="주의")
        warn.pack(fill="x", padx=6, pady=6)
        ttk.Label(warn, justify="left", foreground="#a00", text=(
            "코레일은 자동화 접근을 탐지해 차단합니다 (MACRO ERROR).\n"
            "짧은 간격으로 반복 조회하면 계정 제재나 약관 위반이 될 수 있습니다.\n"
            "간격은 %d초 미만으로 설정할 수 없습니다. 본인 책임 하에 사용하세요."
            % MIN_POLL_INTERVAL)).pack(anchor="w", padx=8, pady=6)

        opts = ttk.Frame(tab)
        opts.pack(fill="x", padx=6, pady=4)

        ttk.Label(opts, text="조회 간격(초)").grid(row=0, column=0, sticky="w", padx=(4, 6))
        self.var_interval = tk.IntVar(value=30)
        ttk.Spinbox(opts, from_=MIN_POLL_INTERVAL, to=600, width=6,
                    textvariable=self.var_interval).grid(row=0, column=1)

        ttk.Label(opts, text="최대 시도 횟수").grid(row=0, column=2, sticky="w", padx=(16, 6))
        self.var_attempts = tk.IntVar(value=120)
        ttk.Spinbox(opts, from_=1, to=9999, width=7,
                    textvariable=self.var_attempts).grid(row=0, column=3)

        self.var_auto_reserve = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="좌석을 찾으면 자동으로 예약",
                        variable=self.var_auto_reserve).grid(
            row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(8, 0))

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", padx=6, pady=6)
        self.btn_poll_start = ttk.Button(buttons, text="대기 시작", command=self.on_poll_start)
        self.btn_poll_start.pack(side="left")
        self.btn_poll_stop = ttk.Button(buttons, text="중지", command=self.on_poll_stop,
                                        state="disabled")
        self.btn_poll_stop.pack(side="left", padx=6)

        log_holder = ttk.Frame(tab)
        log_holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.txt_log = tk.Text(log_holder, height=14, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_holder, orient="vertical",
                                   command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

    def _build_reservations_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="내 예약")

        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ("train", "route", "price", "limit")
        self.tree_rsv = ttk.Treeview(holder, columns=cols, show="headings",
                                     selectmode="browse")
        for col, text, width in [("train", "열차", 150), ("route", "구간", 240),
                                 ("price", "금액", 120), ("limit", "결제 기한", 160)]:
            self.tree_rsv.heading(col, text=text)
            self.tree_rsv.column(col, width=width, anchor="w")

        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree_rsv.yview)
        self.tree_rsv.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree_rsv.pack(side="left", fill="both", expand=True)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", padx=4, pady=(0, 6))
        self.btn_rsv_refresh = ttk.Button(actions, text="새로고침",
                                          command=self.on_load_reservations)
        self.btn_rsv_refresh.pack(side="left")
        self.btn_rsv_cancel = ttk.Button(actions, text="선택한 예약 취소",
                                         command=self.on_cancel_reservation)
        self.btn_rsv_cancel.pack(side="left", padx=6)

    def _build_statusbar(self):
        self.var_status = tk.StringVar(value="로그인이 필요합니다.")
        ttk.Label(self, textvariable=self.var_status, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # 상태
    # ------------------------------------------------------------------
    def set_status(self, text):
        self.var_status.set(text)

    def log(self, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "[%s] %s\n" % (stamp, text))
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _set_logged_in(self, logged_in):
        state = "normal" if logged_in else "disabled"
        for widget in (self.btn_search, self.btn_reserve, self.btn_poll_start,
                       self.btn_rsv_refresh, self.btn_rsv_cancel, self.btn_logout):
            widget.configure(state=state)
        self.btn_login.configure(state="disabled" if logged_in else "normal")

    # ------------------------------------------------------------------
    # 입력값 읽기
    # ------------------------------------------------------------------
    def _passengers(self):
        counts = {k: v.get() for k, v in self.psgr_vars.items()}
        classes = {"adult": AdultPassenger, "child": ChildPassenger,
                   "toddler": ToddlerPassenger, "senior": SeniorPassenger}
        passengers = [classes[k](n) for k, n in counts.items() if n > 0]
        if not passengers:
            raise ValueError("승객을 한 명 이상 지정해주세요.")
        return passengers

    def _criteria(self):
        dep = self.var_dep.get().strip()
        arr = self.var_arr.get().strip()
        if not dep or not arr:
            raise ValueError("출발역과 도착역을 입력해주세요.")
        date = self.var_date.get().strip()
        time_ = self.var_time.get().strip()
        for value, name, length in ((date, "날짜", 8), (time_, "시각", 6)):
            if not (value.isdigit() and len(value) == length):
                raise ValueError("%s 형식이 올바르지 않습니다: %s" % (name, value))
        return {
            "dep": dep, "arr": arr, "date": date, "time": time_,
            "train_type": TRAIN_TYPES[self.cbo_type.current()][1],
            "passengers": self._passengers(),
        }

    def _reserve_option(self):
        return RESERVE_OPTIONS[self.cbo_option.current()][1]

    # ------------------------------------------------------------------
    # 로그인
    # ------------------------------------------------------------------
    def on_login(self):
        korail_id, korail_pw = self.var_id.get().strip(), self.var_pw.get()
        if not korail_id or not korail_pw:
            messagebox.showwarning("로그인", "아이디와 비밀번호를 입력해주세요.", parent=self)
            return

        self.btn_login.configure(state="disabled")
        self.set_status("로그인 중...")
        korail = Korail(korail_id, korail_pw, auto_login=False)

        def done(ok):
            # 성공 여부와 무관하게 화면에서 비밀번호를 지운다.
            self.var_pw.set("")
            if ok:
                self.korail = korail
                self.lbl_account.configure(
                    text="%s (%s)" % (korail.name, korail.membership_number),
                    foreground="#060")
                self._set_logged_in(True)
                self.set_status("로그인되었습니다.")
                self.on_load_reservations()
            else:
                self.btn_login.configure(state="normal")
                self.set_status("로그인 실패")
                messagebox.showerror("로그인", "아이디 또는 비밀번호를 확인해주세요.",
                                     parent=self)

        def failed(exc):
            self.var_pw.set("")
            self.btn_login.configure(state="normal")
            self._show_error(exc)

        self.run_async(korail.login, done, failed)

    def on_logout(self):
        self.on_poll_stop()
        if self.korail:
            try:
                self.korail.logout()
            except KorailError:
                pass
        self.korail = None
        self._trains.clear()
        self._reservations.clear()
        self.tree.delete(*self.tree.get_children())
        self.tree_rsv.delete(*self.tree_rsv.get_children())
        self.lbl_account.configure(text="로그아웃 상태", foreground="#a00")
        self._set_logged_in(False)
        self.set_status("로그아웃되었습니다.")

    # ------------------------------------------------------------------
    # 조회 / 예약
    # ------------------------------------------------------------------
    def _search(self, criteria):
        kwargs = dict(criteria)
        kwargs["include_no_seats"] = self.var_no_seats.get()
        kwargs["include_waiting_list"] = self.var_waiting.get()
        if self.var_allday.get():
            return self.korail.search_train_allday(**kwargs)
        return self.korail.search_train(**kwargs)

    def on_search(self):
        try:
            criteria = self._criteria()
        except ValueError as exc:
            messagebox.showwarning("입력 확인", str(exc), parent=self)
            return

        self.btn_search.configure(state="disabled")
        self.set_status("조회 중...")

        def done(trains):
            self.btn_search.configure(state="normal")
            self._fill_trains(trains)
            self.set_status("%d개 열차를 찾았습니다." % len(trains))
            self.nb.select(0)

        def failed(exc):
            self.btn_search.configure(state="normal")
            self._fill_trains([])
            if isinstance(exc, NoResultsError):
                self.set_status("조건에 맞는 열차가 없습니다.")
            else:
                self._show_error(exc)

        self.run_async(lambda: self._search(criteria), done, failed)

    def _fill_trains(self, trains):
        self.tree.delete(*self.tree.get_children())
        self._trains.clear()
        for train in trains:
            seats = []
            if train.has_special_seat():
                seats.append("특실")
            if train.has_general_seat():
                seats.append("일반실")
            if train.has_general_waiting_list():
                seats.append("예약대기(일반)")
            iid = self.tree.insert("", "end", values=(
                "%s %s" % (train.train_type_name, train.train_no),
                "%s %s" % (train.dep_name, fmt_time(train.dep_time)),
                "%s %s" % (train.arr_name, fmt_time(train.arr_time)),
                ", ".join(seats) or "좌석 없음",
            ))
            self._trains[iid] = train

    def on_reserve(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("예약", "예약할 열차를 선택해주세요.", parent=self)
            return
        train = self._trains[selection[0]]
        try:
            passengers = self._passengers()
        except ValueError as exc:
            messagebox.showwarning("입력 확인", str(exc), parent=self)
            return

        if not messagebox.askyesno(
                "예약 확인",
                "아래 열차를 실제로 예약합니다.\n\n%s\n\n계속할까요?" % repr(train),
                parent=self):
            return

        option = self._reserve_option()
        self.btn_reserve.configure(state="disabled")
        self.set_status("예약 중...")

        def done(rsv):
            self.btn_reserve.configure(state="normal")
            self.set_status("예약되었습니다.")
            messagebox.showinfo("예약 완료", repr(rsv), parent=self)
            self.on_load_reservations()

        def failed(exc):
            self.btn_reserve.configure(state="normal")
            if isinstance(exc, SoldOutError):
                self.set_status("좌석이 매진되었습니다.")
                messagebox.showwarning("예약", "좌석이 매진되었습니다.", parent=self)
            else:
                self._show_error(exc)

        self.run_async(
            lambda: self.korail.reserve(train, passengers=passengers, option=option),
            done, failed)

    # ------------------------------------------------------------------
    # 예약 목록
    # ------------------------------------------------------------------
    def on_load_reservations(self):
        if not self.korail:
            return
        self.btn_rsv_refresh.configure(state="disabled")

        def done(reservations):
            self.btn_rsv_refresh.configure(state="normal")
            self.tree_rsv.delete(*self.tree_rsv.get_children())
            self._reservations.clear()
            for rsv in reservations:
                iid = self.tree_rsv.insert("", "end", values=(
                    "%s %s" % (rsv.train_type_name, rsv.train_no),
                    "%s %s ~ %s %s" % (rsv.dep_name, fmt_time(rsv.dep_time),
                                       rsv.arr_name, fmt_time(rsv.arr_time)),
                    "%s원 (%s석)" % (rsv.price, rsv.seat_no_count),
                    "%s %s" % (rsv.buy_limit_date, fmt_time(rsv.buy_limit_time)),
                ))
                self._reservations[iid] = rsv
            self.set_status("예약 %d건" % len(reservations))

        def failed(exc):
            self.btn_rsv_refresh.configure(state="normal")
            self._show_error(exc)

        self.run_async(self.korail.reservations, done, failed)

    def on_cancel_reservation(self):
        selection = self.tree_rsv.selection()
        if not selection:
            messagebox.showinfo("취소", "취소할 예약을 선택해주세요.", parent=self)
            return
        rsv = self._reservations[selection[0]]
        if not messagebox.askyesno(
                "예약 취소", "아래 예약을 취소합니다.\n\n%s\n\n계속할까요?" % repr(rsv),
                parent=self):
            return

        self.btn_rsv_cancel.configure(state="disabled")

        def done(_result):
            self.btn_rsv_cancel.configure(state="normal")
            self.set_status("예약이 취소되었습니다.")
            self.on_load_reservations()

        def failed(exc):
            self.btn_rsv_cancel.configure(state="normal")
            self._show_error(exc)

        self.run_async(lambda: self.korail.cancel(rsv), done, failed)

    # ------------------------------------------------------------------
    # 자동 좌석 대기
    # ------------------------------------------------------------------
    def on_poll_start(self):
        try:
            criteria = self._criteria()
        except ValueError as exc:
            messagebox.showwarning("입력 확인", str(exc), parent=self)
            return

        interval = max(MIN_POLL_INTERVAL, int(self.var_interval.get()))
        self.var_interval.set(interval)
        attempts = max(1, int(self.var_attempts.get()))
        auto_reserve = self.var_auto_reserve.get()

        confirm = ("%s -> %s, %s %s 부터\n조회 간격 %d초, 최대 %d회\n\n"
                   % (criteria["dep"], criteria["arr"], criteria["date"],
                      fmt_time(criteria["time"]), interval, attempts))
        confirm += ("좌석을 찾으면 자동으로 예약합니다. 결제 기한이 있는 실제 예약입니다."
                    if auto_reserve else "좌석을 찾으면 알림만 표시합니다.")
        if not messagebox.askyesno("자동 대기 시작", confirm + "\n\n계속할까요?",
                                   parent=self):
            return

        self._stop_polling.clear()
        self.btn_poll_start.configure(state="disabled")
        self.btn_poll_stop.configure(state="normal")
        self.btn_search.configure(state="disabled")
        self.btn_reserve.configure(state="disabled")
        self.log("대기 시작 — %s -> %s, %d초 간격"
                 % (criteria["dep"], criteria["arr"], interval))

        # 위젯 값은 메인 스레드인 여기서 전부 읽어 워커에 넘긴다.
        # 워커에서 Tk 위젯을 건드리면 인터프리터가 스레드 안전하지 않아 깨진다.
        self._poll_thread = threading.Thread(
            target=self._poll_worker,
            args=(criteria, interval, attempts, auto_reserve,
                  self._reserve_option(), self.var_waiting.get()),
            daemon=True)
        self._poll_thread.start()

    def on_poll_stop(self):
        if self._poll_thread and self._poll_thread.is_alive():
            self._stop_polling.set()
            self.log("중지 요청됨. 현재 조회가 끝나면 멈춥니다.")
        self.btn_poll_stop.configure(state="disabled")

    def _poll_finished(self, message):
        self.btn_poll_start.configure(state="normal")
        self.btn_poll_stop.configure(state="disabled")
        if self.korail:
            self.btn_search.configure(state="normal")
            self.btn_reserve.configure(state="normal")
        self.log(message)
        self.set_status(message)

    def _poll_worker(self, criteria, interval, max_attempts, auto_reserve,
                     option, include_waiting):
        """워커 스레드.

        위젯과 Tk 변수는 절대 읽지도 쓰지도 않는다. 필요한 값은 전부 인자로
        받고, 화면 갱신은 self.post 로 메인 스레드에 넘긴다.
        """
        passengers = criteria["passengers"]
        consecutive_errors = 0

        for attempt in range(1, max_attempts + 1):
            if self._stop_polling.is_set():
                self.post(lambda: self._poll_finished("사용자가 중지했습니다."))
                return

            try:
                with self._api_lock:
                    # 폴링에는 단발 조회만 쓴다. allday 는 한 번에 15회를 호출한다.
                    trains = self.korail.search_train(
                        criteria["dep"], criteria["arr"], criteria["date"],
                        criteria["time"], criteria["train_type"], passengers,
                        include_waiting_list=include_waiting)
            except NoResultsError:
                consecutive_errors = 0
                self.post(lambda a=attempt: self.log("%d회차 — 좌석 없음" % a))
            except NeedToLoginError:
                try:
                    with self._api_lock:
                        self.korail.login()
                    self.post(lambda: self.log("세션이 만료되어 다시 로그인했습니다."))
                    consecutive_errors = 0
                except KorailError as exc:
                    self.post(lambda e=exc: self._poll_finished("재로그인 실패: %s" % e))
                    return
            except KorailError as exc:
                consecutive_errors += 1
                self.post(lambda a=attempt, e=exc:
                          self.log("%d회차 — 오류: %s" % (a, e)))
                if consecutive_errors >= 5:
                    self.post(lambda: self._poll_finished(
                        "연속 오류가 5회여서 중단합니다. 차단되었을 수 있으니 "
                        "잠시 후 다시 시도하세요."))
                    return
            else:
                consecutive_errors = 0
                train = trains[0]
                self.post(lambda t=train: self.log("좌석 발견 — %s" % repr(t)))
                if not auto_reserve:
                    self.post(lambda t=train: self._poll_found_no_reserve(t))
                    return
                try:
                    with self._api_lock:
                        rsv = self.korail.reserve(train, passengers=passengers,
                                                  option=option)
                except SoldOutError:
                    self.post(lambda: self.log("예약 직전에 매진되었습니다. 계속합니다."))
                except KorailError as exc:
                    self.post(lambda e=exc: self._poll_finished("예약 실패: %s" % e))
                    return
                else:
                    self.post(lambda r=rsv: self._poll_reserved(r))
                    return

            if self._stop_polling.wait(interval):
                self.post(lambda: self._poll_finished("사용자가 중지했습니다."))
                return

        self.post(lambda: self._poll_finished("최대 시도 횟수에 도달했습니다."))

    def _poll_found_no_reserve(self, train):
        self._poll_finished("좌석을 찾았습니다.")
        messagebox.showinfo("좌석 발견", repr(train), parent=self)

    def _poll_reserved(self, rsv):
        self._poll_finished("예약 완료 — %s" % repr(rsv))
        self.on_load_reservations()
        messagebox.showinfo("예약 완료", repr(rsv), parent=self)

    # ------------------------------------------------------------------
    def _on_close(self):
        self._stop_polling.set()
        # 예약된 콜백이 파괴된 위젯을 건드리지 않도록 먼저 취소한다.
        if self._drain_job is not None:
            self.after_cancel(self._drain_job)
            self._drain_job = None
        self.destroy()


def main():
    KorailApp().mainloop()


if __name__ == "__main__":
    main()
