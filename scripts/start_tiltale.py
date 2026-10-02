"""start_TilTale: a small window that sets up and starts TilTale, for people who never open a terminal.

Started by ``start_TilTale_Windows.bat``, ``start_TilTale_Mac.command`` or ``start_TilTale_Linux.sh``,
which make sure Python exists, download TilTale when it is not there yet, and then run this file.
Standard library only (tkinter), because it runs before ``requirements.txt`` is installed.

What it does, as a visible to-do list with a Start and a Stop button:

1. Detect the operating system.
2. Check Git (any version counts) and install it in the background when missing.
3. Check the folder this launcher sits in:
   - empty: clone https://github.com/tiltale/tiltale-refactor into it;
   - an unpacked ZIP of the repository (``README.md`` and ``studio/`` exist, no ``.git``): connect it
     to GitHub without touching the files;
   - a working copy: fetch, then offer the newer version when there is one. Saying no keeps the
     current version; the question returns at the next start.
4. Create ``.venv`` and install ``requirements.txt`` (the steps of the README, automated).
5. Open TilTale in the browser (``manage.py runserver``; this window stays open and shows the log),
   or open the folder in an editor for people who want to see the source.

Every line of the log panel is also written to ``start_TilTale.log`` next to this launcher.
"""

from __future__ import annotations

from pathlib import Path
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

REPOSITORY: str = "https://github.com/tiltale/tiltale-refactor"
STUDIO_URL: str = "http://127.0.0.1:8000/"
STUDIO_PORT: int = 8000
ROOT: Path = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "scripts" else Path.cwd()
LOG_FILE: Path = ROOT / "start_TilTale.log"
WINDOWS: bool = platform.system() == "Windows"


def write_log(line: str) -> None:
    """Add one line to start_TilTale.log. Never raises: a log problem must not stop the start."""
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')}  {line}\n")
    except OSError:
        pass


def log_crash(kind: type, error: BaseException, trace) -> None:
    write_log("Crashed:\n" + "".join(traceback.format_exception(kind, error, trace)).rstrip())


# The log starts before anything else can go wrong, even before tkinter loads. The launcher
# begins the log itself and sets TILTALE_LOG_STARTED; started any other way, this is a new log.
if not os.environ.get("TILTALE_LOG_STARTED"):
    try:
        LOG_FILE.write_text("", encoding="utf-8")
    except OSError:
        pass
write_log(f"start_tiltale.py on {platform.platform()}, Python {platform.python_version()} ({sys.executable})")
_print_crash = sys.excepthook
sys.excepthook = lambda kind, error, trace: (log_crash(kind, error, trace), _print_crash(kind, error, trace))
_print_thread_crash = threading.excepthook
threading.excepthook = lambda args: (log_crash(args.exc_type, args.exc_value, args.exc_traceback), _print_thread_crash(args))

import tkinter as tk  # noqa: E402  (after the log, so a Python without tkinter is logged too)
from tkinter import font as tkfont, messagebox, ttk  # noqa: E402

# What may sit in the folder before TilTale is there: the launcher itself, the copy of this app it
# downloads when the repository is not there yet, its log, and OS clutter. Such a folder counts as empty.
LAUNCHER_FILES: frozenset[str] = frozenset({
    "start_TilTale_Windows.bat", "start_TilTale_Mac.command", "start_TilTale_Linux.sh",
    "start_TilTale.bat", "start_TilTale.command", "start_TilTale.sh",  # names before 2.6.7
    "start_tiltale_tmp.py", "start_TilTale.log", "__pycache__", ".DS_Store", "Thumbs.db", "desktop.ini",
})
GIT_INSTALLS: dict[str, list[str]] = {  # per OS: the quiet installer most machines have
    "Windows": ["winget", "install", "-e", "--id", "Git.Git", "--source", "winget", "--silent",
                "--disable-interactivity", "--accept-package-agreements", "--accept-source-agreements"],
    "Darwin": ["xcode-select", "--install"],  # macOS asks the user to confirm in its own dialog
    "Linux": ["sudo", "apt-get", "install", "-y", "git"],
}
# Where Git for Windows installs itself (machine-wide, or for one user).
GIT_FOLDERS: tuple[str, ...] = (r"%ProgramFiles%\Git\cmd", r"%ProgramW6432%\Git\cmd", r"%LocalAppData%\Programs\Git\cmd")
GIT: str = "git"  # becomes the full path of git once check_requirements has found it

STEPS: tuple[tuple[str, str], ...] = (
    ("os", "Detect your computer"),
    ("requirements", "Check Python and Git"),
    ("root", "Get or update TilTale"),
    ("packages", "Install TilTale's packages"),
    ("open", "Open TilTale"),
)

# The studio's own colours (studio/static: --bg, --surface, --text, --muted, --line, --navy, ...).
BG, SURFACE, TEXT, MUTED, LINE = "#f3f5f9", "#ffffff", "#14203a", "#5b6781", "#dfe4ee"
NAVY, ON_NAVY, GOLD = "#142850", "#b8c4dc", "#eecf5a"
ACCENT, ACCENT_DARK, ACCENT_OFF = "#2552d0", "#1c41a8", "#a9b9e8"
OK, DANGER = "#1f8a4c", "#d0342c"
WARN, WARN_SOFT = "#a56300", "#fff4dc"

# Files and folders a working TilTale folder always has. One missing: the folder is damaged.
REQUIRED: tuple[str, ...] = ("README.md", "manage.py", "requirements.txt", "config/settings.py", "studio", "runtime")
# Things only a TilTale folder has: with one of them, a damaged folder may be repaired.
TILTALE_SIGNS: tuple[str, ...] = ("studio", "frame-types", "components", "runtime/tiltale.js",
                                  "branding/logo-tiltale.png", "project/project.sqlite3")
# Code editors "Open in my code editor" looks for: name, command on PATH, Windows install places,
# macOS app name, and the link type the editor registers when it is installed (vscode://file/...).
EDITORS: tuple[tuple[str, str, tuple[str, ...], str, str], ...] = (
    ("Visual Studio Code", "code", (r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe",
                                    r"%ProgramFiles%\Microsoft VS Code\Code.exe"), "Visual Studio Code", "vscode"),
    ("Cursor", "cursor", (r"%LocalAppData%\Programs\cursor\Cursor.exe",), "Cursor", "cursor"),
    ("PyCharm", "pycharm", (), "PyCharm", ""),
)


class NeedsRepair(Exception):
    """The folder was a TilTale folder, but some of TilTale's own files are missing."""


def version_in(settings_text: str) -> str:
    found = re.search(r"TILTALE_VERSION[^\"']*[\"']([^\"']+)[\"']", settings_text)
    return found.group(1) if found else "unknown"


def venv_python() -> Path:
    """The Python inside ROOT/.venv. Packages and the studio only ever run with this one, never with
    the computer's own Python, which merely starts this window (standard library only)."""
    return ROOT / ".venv" / ("Scripts" if WINDOWS else "bin") / ("python.exe" if WINDOWS else "python")


def base_python() -> str:
    """The computer's Python as a console program: python.exe even when this window runs on pythonw.exe."""
    console = Path(sys.executable).with_name("python.exe")
    return str(console) if WINDOWS and console.is_file() else sys.executable


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command without opening a console window; output goes to the log. Output is read as
    UTF-8 (what git, winget and Python print), so nothing turns into strange characters."""
    flags = subprocess.CREATE_NO_WINDOW if WINDOWS else 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run(command, cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=flags, env=env)


SPINNER_OR_BAR = re.compile(r"[█▒]|^\s*[-\\|/]\s*$")


def tidy(output: str) -> str:
    """Installer output without spinners and progress bars, which only make sense live on a screen."""
    lines = (line.rstrip() for line in output.replace("\r", "\n").splitlines())
    return "\n".join(line for line in lines if line.strip() and not SPINNER_OR_BAR.search(line))


def refresh_path() -> None:
    """Windows: read PATH again from the registry. An installer (Git) adds itself there, but a program
    that is already running keeps its old copy of PATH until it restarts."""
    if not WINDOWS:
        return
    import winreg
    parts: list[str] = []
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(hive, key) as handle:
                parts.append(os.path.expandvars(winreg.QueryValueEx(handle, "Path")[0]))
        except OSError:
            pass
    os.environ["PATH"] = os.pathsep.join(parts + [os.environ.get("PATH", "")])


def find_git() -> str:
    """The full path of git, or "" when it is not installed. Also finds a Git that was installed a
    moment ago, which the PATH of this running program does not know yet."""
    found = shutil.which("git")
    if not found:
        refresh_path()
        found = shutil.which("git")
    if not found and WINDOWS:
        for folder in GIT_FOLDERS:
            candidate = Path(os.path.expandvars(folder)) / "git.exe"
            if candidate.is_file():
                os.environ["PATH"] = f"{candidate.parent}{os.pathsep}{os.environ.get('PATH', '')}"
                found = str(candidate)
                break
    return found or ""


def looks_like_tiltale() -> bool:
    """Signs that this folder was a TilTale folder once, and is not a folder of unrelated files."""
    if any((ROOT / sign).exists() for sign in TILTALE_SIGNS):
        return True
    for path in (ROOT / ".git" / "config", ROOT / "README.md", ROOT / "config" / "settings.py"):
        try:
            if "tiltale" in path.read_text(encoding="utf-8", errors="ignore").lower():
                return True
        except OSError:
            pass
    return False


def find_editor() -> tuple[str, list[str]] | None:
    """A code editor on this computer: (its name, the command that opens a folder with it)."""
    for name, command, windows_places, app, _ in EDITORS:
        for place in windows_places if WINDOWS else ():
            program = Path(os.path.expandvars(place))
            if program.is_file():
                return name, [str(program)]
        if platform.system() == "Darwin" and Path(f"/Applications/{app}.app").is_dir():
            return name, ["open", "-a", app]
        found = shutil.which(command)
        if found:
            return name, [found]
    return None


def open_editor_at(folder: Path, log) -> str:
    """Open a folder in a code editor and return the editor's name. Tries, in order: the editor's
    program (started the way a double-click would), then the editor's own link type (vscode://file/…),
    which the editor registers when it is installed. Raises ValueError when no editor is found."""
    tried: list[str] = []
    editor = find_editor()
    if editor:
        name, command = editor
        log(f"Editor found: {name}: {' '.join(command)}")
        try:
            if WINDOWS:
                # ShellExecute, exactly like a double-click: no console, no inherited handles, no PATH.
                os.startfile(command[0], arguments=f'"{folder}"', cwd=str(folder))  # type: ignore[call-arg]
            else:
                subprocess.Popen(command + [str(folder)], cwd=folder, start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return name
        except (OSError, TypeError) as error:
            tried.append(f"{name} ({error})")
            log(f"Could not start {name}: {error}")
    for name, _, _, _, scheme in EDITORS:
        if not scheme:
            continue
        link = f"{scheme}://file/{folder.as_posix().lstrip('/')}"
        log(f"Trying the link {link}")
        try:
            if WINDOWS:
                os.startfile(link)
            elif platform.system() == "Darwin":
                if subprocess.run(["open", link], capture_output=True).returncode != 0:
                    raise OSError("no app for this link")
            elif subprocess.run(["xdg-open", link], capture_output=True).returncode != 0:
                raise OSError("no app for this link")
            return name
        except OSError as error:
            log(f"The link did not work: {error}")
    names = ", ".join(name for name, *_ in EDITORS[:-1]) + f" or {EDITORS[-1][0]}"
    raise ValueError((f"{tried[0]} could not be started." if tried else f"No code editor found: TilTale looks for {names}.")
                     + " Show details has more.")


def show_folder(folder: Path) -> None:
    """Open a folder in Explorer (Windows), Finder (macOS) or the file manager (Linux)."""
    if WINDOWS:
        os.startfile(folder)  # noqa: S606  (only ever a folder of TilTale's)
    else:
        subprocess.Popen(["open" if platform.system() == "Darwin" else "xdg-open", str(folder)])


def sharp_text() -> None:
    """Windows: draw this window at the screen's real resolution. Without this, Windows stretches it
    on screens set to 125% or 150%, which makes all text blurry."""
    if not WINDOWS:
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class StepRow:
    """One line of the to-do list: a round status icon, the step's title and a note underneath."""

    def __init__(self, parent: tk.Widget, title: str, px, fonts: dict) -> None:
        self.frame = tk.Frame(parent, bg=SURFACE)
        self.size: int = px(22)
        self.icon = tk.Canvas(self.frame, width=self.size, height=self.size, bg=SURFACE, highlightthickness=0)
        self.icon.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, px(14)), pady=(px(1), 0))
        self.title = tk.Label(self.frame, text=title, bg=SURFACE, fg=MUTED, font=fonts["step"], anchor="w")
        self.title.grid(row=0, column=1, sticky="w")
        self.note = tk.Label(self.frame, bg=SURFACE, fg=MUTED, font=fonts["small"], anchor="w",
                             justify="left", wraplength=px(430))
        self.note.grid(row=1, column=1, sticky="w")
        self.note.grid_remove()
        self.angle: int = 90
        self.job: str | None = None
        self.set("waiting")

    def set(self, state: str, note: str = "") -> None:
        """state: waiting, running, done or failed."""
        if self.job:
            self.icon.after_cancel(self.job)
            self.job = None
        canvas, size = self.icon, self.size
        width = max(2, round(size / 10))
        inset = width
        canvas.delete("all")
        self.title.configure(fg=MUTED if state == "waiting" else TEXT)
        if state in ("waiting", "running"):
            canvas.create_oval(inset, inset, size - inset, size - inset, outline=LINE, width=width)
        if state == "running":
            self.arc = canvas.create_arc(inset, inset, size - inset, size - inset, start=self.angle, extent=110,
                                         style="arc", outline=ACCENT, width=width)
            self.spin()
        elif state == "done":
            canvas.create_oval(1, 1, size - 1, size - 1, fill=OK, outline=OK)
            canvas.create_line(size * .29, size * .52, size * .44, size * .67, size * .72, size * .37,
                               fill="white", width=width, capstyle="round", joinstyle="round")
        elif state == "failed":
            canvas.create_oval(1, 1, size - 1, size - 1, fill=DANGER, outline=DANGER)
            low, high = size * .35, size * .65
            canvas.create_line(low, low, high, high, fill="white", width=width, capstyle="round")
            canvas.create_line(low, high, high, low, fill="white", width=width, capstyle="round")
        if note:
            self.note.configure(text=note, fg=DANGER if state == "failed" else MUTED)
            self.note.grid()
        else:
            self.note.grid_remove()

    def spin(self) -> None:
        self.angle = (self.angle - 10) % 360
        self.icon.itemconfigure(self.arc, start=self.angle)
        self.job = self.icon.after(30, self.spin)


class Launcher:
    """The window: a header, the to-do list, a hint, buttons and a collapsible log panel."""

    def __init__(self) -> None:
        sharp_text()
        self.window = tk.Tk()
        # Errors in button handlers: into the log too, not only to the console.
        self.window.report_callback_exception = lambda kind, error, trace: (
            log_crash(kind, error, trace), traceback.print_exception(kind, error, trace))
        self.window.title("Start TilTale")
        self.window.configure(bg=BG)
        self.aborted = False
        self.repairing = False  # True for one run after the user chose Repair
        self.server: subprocess.Popen | None = None
        self.python: Path = venv_python()  # always the project's .venv: the computer's own Python stays untouched

        self.scale: float = max(1.0, self.window.winfo_fpixels("1i") / 96)  # 1.0 at 100 %, 1.5 at 150 %
        px = lambda value: round(value * self.scale)  # noqa: E731  (pixel sizes that grow with the screen)
        self.fonts = self.make_fonts()
        self.style_widgets(px)
        self.set_icon()

        # Header: the logo on TilTale's navy.
        header = tk.Frame(self.window, bg=NAVY, padx=px(28), pady=px(18))
        header.pack(fill="x")
        self.logo = self.load_logo()
        if self.logo:
            tk.Label(header, image=self.logo, bg=NAVY).pack(anchor="w")
        else:
            tk.Label(header, text="TilTale", bg=NAVY, fg=GOLD, font=self.fonts["title"]).pack(anchor="w")
        tk.Label(header, text="Set up and start TilTale", bg=NAVY, fg=ON_NAVY,
                 font=self.fonts["body"]).pack(anchor="w", pady=(px(6), 0))

        # Footer, always at the bottom: a reminder to keep a copy of the project somewhere else.
        tip = tk.Frame(self.window, bg=WARN_SOFT, padx=px(28), pady=px(12))
        tip.pack(side="bottom", fill="x")
        tk.Label(tip, text="Tip", bg=WARN_SOFT, fg=WARN, font=self.fonts["button"]).pack(side="left", anchor="n")
        ttk.Button(tip, text="Show project folder", style="TipLink.TButton",
                   command=self.show_project).pack(side="right", anchor="n")
        tk.Label(tip, text="Now and then, copy your project folder to a safe place outside the TilTale folder, "
                           "such as a USB stick or a cloud drive. Your stories live in that folder.",
                 bg=WARN_SOFT, fg=TEXT, font=self.fonts["small"], justify="left", anchor="w",
                 wraplength=px(390)).pack(side="left", fill="x", padx=(px(10), px(10)))

        body = tk.Frame(self.window, bg=BG, padx=px(28), pady=px(20))
        body.pack(fill="both", expand=True)
        tk.Label(body, text=f"Folder:  {ROOT}", bg=BG, fg=MUTED, font=self.fonts["small"],
                 anchor="w").pack(fill="x", pady=(0, px(10)))

        # The to-do list, on a white card.
        card = tk.Frame(body, bg=SURFACE, highlightthickness=1, highlightbackground=LINE,
                        padx=px(22), pady=px(16))
        card.pack(fill="x")
        self.rows: dict[str, StepRow] = {}
        for key, title in STEPS:
            self.rows[key] = StepRow(card, title, px, self.fonts)
            self.rows[key].frame.pack(fill="x", pady=px(6))
        self.progress = ttk.Progressbar(card, mode="indeterminate", style="Tilt.Horizontal.TProgressbar")

        self.hint = tk.Label(body, bg=BG, fg=TEXT, font=self.fonts["body"], anchor="w", justify="left",
                             wraplength=px(500))
        self.hint.pack(fill="x", pady=(px(16), px(12)))

        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x")
        self.buttons = tk.Frame(bar, bg=BG)
        self.buttons.pack(side="left")
        self.details_button = ttk.Button(bar, text="Show details", style="Link.TButton", command=self.toggle_log)
        self.details_button.pack(side="right")

        self.log_box = tk.Text(body, height=12, state="disabled", wrap="word", relief="flat", bg=NAVY, fg=ON_NAVY,
                               insertbackground=ON_NAVY, font=self.fonts["mono"], padx=px(12), pady=px(10),
                               highlightthickness=0)
        self.show_ready()

        # Centre on the screen and come to the front once, instead of opening behind another window.
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        left = max(0, (self.window.winfo_screenwidth() - width) // 2)
        top = max(0, (self.window.winfo_screenheight() - height) // 3)
        self.window.geometry(f"+{left}+{top}")
        self.window.minsize(width, height)
        self.window.lift()
        self.window.attributes("-topmost", True)
        self.window.after(500, lambda: self.window.attributes("-topmost", False))
        self.window.focus_force()
        # The launchers wait for this exact line before it closes its own window.
        self.log(f"Window open. Folder: {ROOT}")

    # ------------------------------------------------------------- looks
    def make_fonts(self) -> dict:
        family = "Segoe UI" if WINDOWS else tkfont.nametofont("TkDefaultFont").actual("family")
        strong = ("Segoe UI Semibold", "normal") if WINDOWS else (family, "bold")
        mono = "Consolas" if WINDOWS else tkfont.nametofont("TkFixedFont").actual("family")
        return {
            "title": tkfont.Font(family=strong[0], size=20, weight=strong[1]),
            "step": tkfont.Font(family=strong[0], size=11, weight=strong[1]),
            "body": tkfont.Font(family=family, size=10),
            "small": tkfont.Font(family=family, size=9),
            "button": tkfont.Font(family=strong[0], size=10, weight=strong[1]),
            "mono": tkfont.Font(family=mono, size=9),
        }

    def style_widgets(self, px) -> None:
        style = ttk.Style(self.window)
        style.theme_use("clam")  # the one built-in theme whose colours can all be set
        flat = {"borderwidth": 1, "focusthickness": 0, "relief": "flat", "font": self.fonts["button"],
                "padding": (px(20), px(8))}
        style.configure("Accent.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT,
                        lightcolor=ACCENT, darkcolor=ACCENT, **flat)
        style.map("Accent.TButton",
                  background=[("disabled", ACCENT_OFF), ("pressed", ACCENT_DARK), ("active", ACCENT_DARK)],
                  bordercolor=[("disabled", ACCENT_OFF), ("active", ACCENT_DARK)],
                  lightcolor=[("disabled", ACCENT_OFF), ("active", ACCENT_DARK)],
                  darkcolor=[("disabled", ACCENT_OFF), ("active", ACCENT_DARK)],
                  foreground=[("disabled", "white")])
        style.configure("Quiet.TButton", background=SURFACE, foreground=TEXT, bordercolor=LINE,
                        lightcolor=SURFACE, darkcolor=SURFACE, **flat)
        style.map("Quiet.TButton", background=[("active", BG), ("pressed", LINE)],
                  lightcolor=[("active", BG)], darkcolor=[("active", BG)], foreground=[("disabled", "#a3abbd")])
        style.configure("Link.TButton", background=BG, foreground=ACCENT, bordercolor=BG, lightcolor=BG,
                        darkcolor=BG, borderwidth=0, focusthickness=0, padding=(px(4), px(8)), font=self.fonts["small"])
        style.map("Link.TButton", background=[("active", BG)], foreground=[("active", ACCENT_DARK)])
        style.configure("TipLink.TButton", background=WARN_SOFT, foreground=WARN, bordercolor=WARN_SOFT,
                        lightcolor=WARN_SOFT, darkcolor=WARN_SOFT, borderwidth=0, focusthickness=0,
                        padding=(px(4), 0), font=self.fonts["small"])
        style.map("TipLink.TButton", background=[("active", WARN_SOFT)], foreground=[("active", TEXT)])
        style.configure("Tilt.Horizontal.TProgressbar", troughcolor=BG, background=ACCENT, bordercolor=BG,
                        lightcolor=ACCENT, darkcolor=ACCENT, thickness=px(4))

    def load_logo(self) -> tk.PhotoImage | None:
        name = "launcher-logo@2x.png" if self.scale >= 1.5 else "launcher-logo.png"
        for path in (ROOT / "branding" / name, ROOT / "branding" / "launcher-logo.png"):
            try:
                return tk.PhotoImage(file=str(path))
            except tk.TclError:
                continue
        return None

    def set_icon(self) -> None:
        try:
            if WINDOWS:
                self.window.iconbitmap(default=str(ROOT / "branding" / "favicon.ico"))
            else:
                self.icon_image = tk.PhotoImage(file=str(ROOT / "branding" / "logo.png")).subsample(16)
                self.window.iconphoto(True, self.icon_image)
        except tk.TclError:
            pass  # no icon is fine

    def show_buttons(self, *buttons: tuple[str, str, object]) -> None:
        """Replace the buttons: each is (text, "Accent" or "Quiet", command)."""
        for old in self.buttons.winfo_children():
            old.destroy()
        for index, (text, kind, command) in enumerate(buttons):
            ttk.Button(self.buttons, text=text, style=f"{kind}.TButton", command=command).pack(
                side="left", padx=(0 if index == 0 else round(10 * self.scale), 0))

    def show_ready(self) -> None:
        self.hint.configure(text="Press Start to finish setting up TilTale. The first time takes a few minutes; "
                                 "after that, starting is quick.", fg=TEXT)
        self.show_buttons(("Start", "Accent", self.start))

    def show_project(self) -> None:
        project = ROOT / "project"
        if project.is_dir():
            show_folder(project)
            return
        messagebox.showinfo("No project yet", "There is no project folder yet. It appears in the TilTale folder "
                            f"as soon as you create your first project:\n\n{project}", parent=self.window)

    def working(self, busy: bool) -> None:
        """Show or hide the moving bar under the to-do list."""
        if busy:
            self.progress.pack(fill="x", pady=(round(12 * self.scale), 0))
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    # ------------------------------------------------------------- window helpers
    def log(self, line: str) -> None:
        write_log(line)
        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.window.after(0, append)

    def toggle_log(self) -> None:
        if self.log_box.winfo_ismapped():
            self.log_box.pack_forget()
            self.details_button.configure(text="Show details")
            return
        self.log_box.pack(fill="both", expand=True, pady=(round(12 * self.scale), 0))
        self.details_button.configure(text="Hide details")

    def mark(self, key: str, state: str, note: str = "") -> None:
        self.window.after(0, lambda: self.rows[key].set(state, note))

    def ask(self, question: str) -> bool:
        """A yes/no dialog from the worker thread; waits for the answer."""
        answer: list[bool] = []
        done = threading.Event()
        def show() -> None:
            answer.append(messagebox.askyesno("TilTale", question, parent=self.window))
            done.set()
        self.window.after(0, show)
        done.wait()
        return answer[0]

    def abort(self) -> None:
        if self.server:  # TilTale is running: stop it
            self.server.terminate()
            self.server = None
            self.log("TilTale stopped.")
            self.rows["open"].set("waiting", "Stopped")
            self.show_ready()
            return
        # The steps are running: stop after the current one (a running installer cannot be cut off safely).
        self.aborted = True
        self.log("Stopping after the current step…")
        self.hint.configure(text="Stopping after the current step…", fg=TEXT)
        self.show_buttons()

    def stopped(self) -> None:
        self.working(False)
        self.repairing = False
        self.log("Stopped. Press Start to try again.")
        self.show_ready()

    def start(self) -> None:
        self.aborted = False
        for row in self.rows.values():
            row.set("waiting")
        self.hint.configure(text="Working on it. You can follow every detail under Show details.", fg=TEXT)
        self.show_buttons(("Stop", "Quiet", self.abort))
        self.working(True)
        threading.Thread(target=self.steps, daemon=True).start()

    # ------------------------------------------------------------- the steps
    def steps(self) -> None:
        for key, work in (("os", self.detect_os), ("requirements", self.check_requirements),
                          ("root", self.check_root), ("packages", self.install_packages)):
            if self.aborted:
                self.window.after(0, self.stopped)
                return
            self.mark(key, "running")
            try:
                note = work()
            except NeedsRepair as problem:
                self.mark(key, "failed", str(problem))
                self.log(f"Damaged folder: {problem}")
                self.window.after(0, self.stopped if self.aborted else self.offer_repair)
                return
            except Exception as error:  # any failed step stops the list; the log has the details
                self.mark(key, "failed", str(error))
                self.log(f"Failed: {error}")
                self.window.after(0, self.stopped if self.aborted else self.show_failed)
                return
            self.mark(key, "done", note)
            self.log(f"Done: {dict(STEPS)[key]}: {note}")
        self.window.after(0, self.stopped if self.aborted else self.offer_open)

    def offer_repair(self) -> None:
        self.working(False)
        self.repairing = False
        self.hint.configure(text="If this is your TilTale folder, Repair puts back all of TilTale's own files, "
                                 "in the newest version. Your project folder, and any other files of your own, "
                                 "stay exactly as they are.", fg=TEXT)
        self.show_buttons(("Repair TilTale", "Accent", self.confirm_repair), ("Start again", "Quiet", self.start))

    def confirm_repair(self) -> None:
        if not messagebox.askyesno(
                "Repair TilTale?",
                f"Repair the TilTale folder\n{ROOT}\n\n"
                "TilTale's own files are downloaded again, in the newest version, and put back. "
                "Changes made to TilTale's own files are undone.\n\n"
                "Not touched: your project folder, and any file that is not part of TilTale.\n\n"
                "Only repair when this folder really is your TilTale folder.",
                icon="warning", parent=self.window):
            return
        self.repairing = True
        self.start()

    def show_failed(self) -> None:
        self.working(False)
        self.repairing = False
        self.hint.configure(text="Something went wrong: see the red message above. "
                                 "Press Start to try again.", fg=TEXT)
        self.show_buttons(("Start again", "Accent", self.start))

    def detect_os(self) -> str:
        system = platform.system()
        if system not in GIT_INSTALLS:
            raise ValueError(f"Unknown operating system: {system}")
        return {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}[system]

    def check_requirements(self) -> str:
        # Python runs this file, so it exists; the launcher scripts installed it if needed.
        global GIT
        if platform.system() == "Darwin":
            self.install_apple_tools()
        git = find_git()
        if not git:
            installer = GIT_INSTALLS[platform.system()]
            self.mark("requirements", "running",
                      "Installing Git. Windows asks once for permission: click Yes." if WINDOWS else "Installing Git…")
            self.log("Git not found. Installing it: " + " ".join(installer))
            try:
                install = run(installer)
            except FileNotFoundError:
                raise ValueError(f"Git is missing, and {installer[0]} is not available to install it. "
                                 "Install Git from https://git-scm.com, then press Start again.") from None
            self.log(tidy(install.stdout + install.stderr) or "(no output)")
            self.log(f"Git installer finished with code {install.returncode}")
            git = find_git()
        if not git:
            raise ValueError("Git could not be installed automatically. Install it from https://git-scm.com, "
                             "then press Start again. Show details says what went wrong.")
        GIT = git
        version = run([GIT, "--version"]).stdout.strip().replace("git version ", "")
        return f"Python {platform.python_version()}, Git {version}"

    def install_apple_tools(self) -> None:
        """macOS: /usr/bin/git exists on every Mac but only works once Apple's command line tools are
        installed. Start that install (macOS shows its own dialog) and wait for it."""
        if run(["xcode-select", "-p"]).returncode == 0:
            return
        self.log("Apple's command line tools (Git) are not installed yet. Starting the install…")
        self.mark("requirements", "running", "macOS asks to install the command line tools (Git): click Install "
                                             "and wait. This can take 10 to 20 minutes.")
        run(["xcode-select", "--install"])
        for _ in range(40 * 60):  # up to 40 minutes
            if self.aborted:
                raise ValueError("Stopped while waiting for the command line tools.")
            if run(["xcode-select", "-p"]).returncode == 0:
                self.log("Command line tools installed.")
                return
            time.sleep(1)
        raise ValueError("The command line tools were not installed. Press Start to try again.")

    def check_root(self) -> str:
        contents = [item.name for item in ROOT.iterdir() if item.name not in LAUNCHER_FILES]
        if not contents:
            return self.clone()
        if self.repairing:
            return self.repair()
        missing = [name for name in REQUIRED if not (ROOT / name).exists()]
        if missing:
            if not looks_like_tiltale():
                raise ValueError("This folder is not a TilTale folder: none of TilTale's files are here. "
                                 "Put start_TilTale in a new, empty folder.")
            shown = ", ".join(missing[:4]) + (", …" if len(missing) > 4 else "")
            raise NeedsRepair(f"Some of TilTale's own files are missing: {shown}")
        fresh: bool = not (ROOT / ".git").is_dir()
        if fresh:
            self.connect()
        return self.offer_update(fresh)

    def clone(self) -> str:
        self.log(f"Empty folder: downloading TilTale from {REPOSITORY}…")
        self.mark("root", "running", "Downloading TilTale…")
        result = run([GIT, "clone", REPOSITORY, "_tiltale_tmp"])
        if result.returncode != 0:
            raise ValueError(f"git clone failed: {result.stderr.strip()}")
        temp = ROOT / "_tiltale_tmp"
        for item in temp.iterdir():  # the files belong in the root itself, next to start_TilTale
            if (ROOT / item.name).exists():  # the launcher that is running right now: keep it, the clone has the same
                continue
            shutil.move(str(item), str(ROOT / item.name))
        shutil.rmtree(temp, ignore_errors=True)
        return f"Downloaded TilTale {version_in((ROOT / 'config' / 'settings.py').read_text(encoding='utf-8'))}"

    def repair(self) -> str:
        """Put back every file of TilTale itself (newest version from GitHub). Git only replaces the
        files it tracks: /project/, .venv and anything else that is not part of TilTale stay untouched."""
        self.repairing = False
        self.log("Repair: putting back TilTale's own files from GitHub…")
        self.mark("root", "running", "Repairing: downloading TilTale's files…")
        git_folder = ROOT / ".git"
        if git_folder.exists() and run([GIT, "rev-parse", "--git-dir"]).returncode != 0:
            aside = ROOT / f".git-broken-{time.strftime('%Y%m%d-%H%M%S')}"
            git_folder.rename(aside)  # keep it, just in case; Git starts afresh
            self.log(f"The folder's Git data was damaged; moved it aside to {aside.name}.")
        if not git_folder.exists():
            result = run([GIT, "init", "-b", "main"])
            if result.returncode != 0:
                raise ValueError(f"Repair failed: git init: {result.stderr.strip()}")
        has_origin = run([GIT, "remote", "get-url", "origin"]).returncode == 0
        run([GIT, "remote", "set-url" if has_origin else "add", "origin", REPOSITORY])
        result = run([GIT, "fetch", "origin", "main"])
        if result.returncode != 0:
            self.log(result.stderr.strip())
            raise ValueError("Repair needs the internet, and GitHub could not be reached. "
                             "Check the connection and press Start again.")
        result = run([GIT, "reset", "--hard", "origin/main"])
        if result.returncode != 0:
            raise ValueError(f"Repair failed: {result.stderr.strip()}")
        version = version_in((ROOT / "config" / "settings.py").read_text(encoding="utf-8"))
        return f"Repaired: TilTale {version} is complete again"

    def connect(self) -> None:
        """An unpacked ZIP: connect it to GitHub so future updates can be seen, touching no files."""
        self.log("Connecting this folder to GitHub to stay up to date on future updates…")
        self.mark("root", "running", "Connecting this folder to GitHub, for future updates…")
        for command in ([GIT, "init", "-b", "main"], [GIT, "remote", "add", "origin", REPOSITORY]):
            result = run(command)
            if result.returncode != 0:
                raise ValueError(f"{' '.join(command[1:])} failed: {result.stderr.strip()}")

    def offer_update(self, fresh: bool) -> str:
        self.mark("root", "running", "Checking for a newer version…")
        result = run([GIT, "fetch", "origin", "main"])
        if result.returncode != 0:
            self.log(f"Could not reach GitHub ({result.stderr.strip()}); continuing with the version on this computer.")
            return "Offline: update check skipped"
        if fresh:  # point the new repository at what GitHub has; the files themselves stay untouched
            run([GIT, "reset", "--mixed", "origin/main"])
        local = version_in((ROOT / "config" / "settings.py").read_text(encoding="utf-8"))
        newest = version_in(run([GIT, "show", "origin/main:config/settings.py"]).stdout)
        if local == newest:
            return f"You have the newest version (TilTale {local})"
        if not self.ask(f"You have TilTale version {local} on your computer, but version {newest} is available.\n\n"
                        "Update now? Your /project/ folder (your story) is kept either way."):
            return f"Staying on {local}; {newest} is available"
        result = run([GIT, "reset", "--hard", "origin/main"])
        if result.returncode != 0:
            raise ValueError(f"Update failed: {result.stderr.strip()}")
        return f"Updated to TilTale {newest}"

    def install_packages(self) -> str:
        venv = ROOT / ".venv"
        python = venv_python()
        if not python.exists():
            self.log("Creating the project's own Python environment (.venv)…")
            self.mark("packages", "running", "Preparing TilTale's own Python environment…")
            result = run([base_python(), "-m", "venv", str(venv)])
            if result.returncode != 0:
                raise ValueError(f"Could not create .venv: {result.stderr.strip()}")
        self.log("Installing the packages from requirements.txt (first time: a few minutes)…")
        self.mark("packages", "running", "Downloading and installing. The first time takes a few minutes…")
        result = run([str(python), "-m", "pip", "install", "-r", "requirements.txt", "--quiet",
                      "--disable-pip-version-check"])
        if result.returncode != 0:
            self.log(result.stdout + result.stderr)
            raise ValueError(f"Installing the packages failed: {result.stderr.strip()[-300:]}")
        return "All packages are installed"

    # ------------------------------------------------------------- opening TilTale
    def offer_open(self) -> None:
        self.working(False)
        self.rows["open"].set("waiting")
        self.hint.configure(text="Everything is ready. How would you like to open TilTale?", fg=TEXT)
        self.show_buttons(("Open in my browser", "Accent", self.open_browser),
                          ("Open in my code editor", "Quiet", self.open_editor))

    def open_browser(self) -> None:
        # --noreload: one process, so Stop really stops TilTale (with the auto-reloader a second process
        # would keep running and keep port 8000 busy).
        self.log("Starting TilTale (python manage.py runserver)… keep this window open while you work.")
        self.rows["open"].set("running", "Starting TilTale…")
        self.show_buttons(("Stop TilTale", "Quiet", self.abort))
        flags = subprocess.CREATE_NO_WINDOW if WINDOWS else 0
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.server = subprocess.Popen([str(self.python), "manage.py", "runserver", "--noreload"], cwd=ROOT, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       encoding="utf-8", errors="replace", creationflags=flags)
        threading.Thread(target=self.relay_server_log, daemon=True).start()
        threading.Thread(target=self.open_when_ready, daemon=True).start()

    def relay_server_log(self) -> None:
        server = self.server
        for line in server.stdout:
            self.log(line.rstrip())

    def open_when_ready(self) -> None:
        for _ in range(120):  # two minutes; the first start migrates the database
            if not self.server:
                return
            try:
                socket.create_connection(("127.0.0.1", STUDIO_PORT), timeout=1).close()
            except OSError:
                time.sleep(1)
                continue
            webbrowser.open(STUDIO_URL)
            self.log(f"TilTale is open: {STUDIO_URL}")
            self.mark("open", "done", f"TilTale is running at {STUDIO_URL}")
            self.window.after(0, self.show_running)
            return
        self.log("TilTale did not start; the log above says why.")
        self.mark("open", "failed", "TilTale did not start. Show details says why.")
        self.window.after(0, self.show_failed)

    def show_running(self) -> None:
        self.hint.configure(text="TilTale is open in your browser. Keep this window open while you work: "
                                 "closing it stops TilTale.", fg=TEXT)
        self.show_buttons(("Open in browser again", "Accent", lambda: webbrowser.open(STUDIO_URL)),
                          ("Stop TilTale", "Quiet", self.abort))

    def open_editor(self) -> None:
        self.rows["open"].set("running", "Opening your code editor…")
        try:
            name = open_editor_at(ROOT, self.log)
        except ValueError as problem:
            self.log(str(problem))
            self.rows["open"].set("failed", str(problem))
            self.hint.configure(text="Visual Studio Code is free to download. Or simply open TilTale in your "
                                     "browser: that is all you need to make stories.", fg=TEXT)
            self.show_buttons(("Open in browser", "Accent", self.open_browser),
                              ("Get VS Code", "Quiet", lambda: webbrowser.open("https://code.visualstudio.com/")),
                              ("Show folder", "Quiet", lambda: show_folder(ROOT)))
            return
        self.log(f"Opened the folder in {name}. To run TilTale from there: python manage.py runserver")
        self.rows["open"].set("done", f"The TilTale folder is open in {name}.")
        self.hint.configure(text=f"README.md, section 'Run TilTale', explains how to start TilTale from {name}. "
                                 "Or open it in your browser from here.", fg=TEXT)
        self.show_buttons(("Open in browser", "Accent", self.open_browser),
                          ("Close this window", "Quiet", self.window.destroy))


def main() -> None:
    launcher = Launcher()
    launcher.window.mainloop()
    if launcher.server:
        launcher.server.terminate()


if __name__ == "__main__":
    main()
