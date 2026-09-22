"""start_TilTale: a small window that sets up and starts TilTale, for people who never open a terminal.

Started by ``start_TilTale.bat`` (Windows), ``start_TilTale.command`` (macOS) or ``start_TilTale.sh``
(Linux), which only make sure Python exists and then run this file. Standard library only (tkinter),
because it runs before ``requirements.txt`` is installed.

What it does, as a visible to-do list with a Start and an Abort button:

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

from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.request
import webbrowser

REPOSITORY: str = "https://github.com/tiltale/tiltale-refactor"
STUDIO_URL: str = "http://127.0.0.1:8000/"
STUDIO_PORT: int = 8000
ROOT: Path = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "scripts" else Path.cwd()
LOG_FILE: Path = ROOT / "start_TilTale.log"
# What may sit in the folder before TilTale is there: the launcher itself, the copy of this app it
# downloads when the repository is not there yet, its log, and OS clutter. Such a folder counts as empty.
LAUNCHER_FILES: frozenset[str] = frozenset({
    "start_TilTale.bat", "start_TilTale.command", "start_TilTale.sh", "start_tiltale_tmp.py",
    "start_TilTale.log", "__pycache__", ".DS_Store", "Thumbs.db", "desktop.ini",
})
GIT_INSTALLS: dict[str, list[str]] = {  # per OS: the quiet installer most machines have
    "Windows": ["winget", "install", "-e", "--id", "Git.Git", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
    "Darwin": ["xcode-select", "--install"],  # macOS asks the user to confirm in its own dialog
    "Linux": ["sudo", "apt-get", "install", "-y", "git"],
}

STEPS: tuple[tuple[str, str], ...] = (
    ("os", "Detecting your OS…"),
    ("requirements", "Checking requirements (Python, Git)…"),
    ("root", "Checking root (get or update TilTale)…"),
    ("packages", "Installing requirements.txt…"),
    ("open", "Opening TilTale…"),
)


def version_in(settings_text: str) -> str:
    found = re.search(r"TILTALE_VERSION[^\"']*[\"']([^\"']+)[\"']", settings_text)
    return found.group(1) if found else "unknown"


def venv_python() -> Path:
    """The Python inside ROOT/.venv. Packages and the studio only ever run with this one, never with
    the computer's own Python, which merely starts this window (standard library only)."""
    windows: bool = platform.system() == "Windows"
    return ROOT / ".venv" / ("Scripts" if windows else "bin") / ("python.exe" if windows else "python")


def run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    """Run a command without opening a console window; output goes to the log."""
    flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, creationflags=flags)


class Launcher:
    """The window: a to-do list, Start/Abort buttons and a collapsible log panel."""

    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title("Start TilTale")
        self.window.minsize(460, 300)
        self.aborted = False
        self.server: subprocess.Popen | None = None
        self.python: Path = venv_python()  # always the project's .venv: the computer's own Python stays untouched

        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="TilTale", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Folder: {ROOT}", foreground="#677084").pack(anchor="w", pady=(0, 10))
        self.rows: dict[str, ttk.Label] = {}
        for key, title in STEPS:
            self.rows[key] = ttk.Label(frame, text=f"○  {title}")
            self.rows[key].pack(anchor="w", pady=1)

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w", pady=12)
        self.start_button = ttk.Button(buttons, text="START", command=self.start)
        self.start_button.pack(side="left")
        self.abort_button = ttk.Button(buttons, text="ABORT", command=self.abort, state="disabled")
        self.abort_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Show log", command=self.toggle_log).pack(side="left")

        self.log_box = tk.Text(frame, height=10, state="disabled", font=("Courier", 9))
        LOG_FILE.write_text("", encoding="utf-8")
        self.log(f"start_TilTale on {platform.platform()}, Python {platform.python_version()}")

    # ------------------------------------------------------------- window helpers
    def log(self, line: str) -> None:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')}  {line}\n")
        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.window.after(0, append)

    def toggle_log(self) -> None:
        if self.log_box.winfo_ismapped():
            self.log_box.pack_forget()
            return
        self.log_box.pack(fill="both", expand=True)

    def mark(self, key: str, symbol: str, note: str = "") -> None:
        title = dict(STEPS)[key]
        self.window.after(0, lambda: self.rows[key].configure(text=f"{symbol}  {title}{'  — ' + note if note else ''}"))

    def ask(self, question: str) -> bool:
        """A yes/no dialog from the worker thread; waits for the answer."""
        answer: list[bool] = []
        done = threading.Event()
        def show() -> None:
            answer.append(messagebox.askyesno("TilTale", question))
            done.set()
        self.window.after(0, show)
        done.wait()
        return answer[0]

    def abort(self) -> None:
        self.aborted = True
        if self.server:
            self.server.terminate()
        self.log("Aborted. Close this window, or press START to try again.")
        self.window.after(0, lambda: (self.start_button.configure(state="normal"), self.abort_button.configure(state="disabled")))

    def start(self) -> None:
        self.aborted = False
        self.start_button.configure(state="disabled")
        self.abort_button.configure(state="normal")
        threading.Thread(target=self.steps, daemon=True).start()

    # ------------------------------------------------------------- the steps
    def steps(self) -> None:
        for key, work in (("os", self.detect_os), ("requirements", self.check_requirements),
                          ("root", self.check_root), ("packages", self.install_packages)):
            if self.aborted:
                return
            self.mark(key, "⏳")
            try:
                note = work()
            except Exception as error:  # any failed step stops the list; the log has the details
                self.mark(key, "✗", str(error))
                self.log(f"Failed: {error}")
                self.window.after(0, lambda: self.start_button.configure(state="normal"))
                return
            self.mark(key, "✓", note)
            self.log(f"Done: {dict(STEPS)[key]} {note}")
        self.mark("open", "⏳")
        self.window.after(0, self.offer_open)

    def detect_os(self) -> str:
        system = platform.system()
        if system not in GIT_INSTALLS:
            raise ValueError(f"Unknown operating system: {system}")
        return {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}[system]

    def check_requirements(self) -> str:
        # Python runs this file, so any version of it exists; the launcher scripts installed it if needed.
        if shutil.which("git"):
            return f"Python {platform.python_version()}, {run(['git', '--version']).stdout.strip()}"
        self.log("Git not found. Installing it in the background…")
        install = run(GIT_INSTALLS[platform.system()])
        self.log(install.stdout + install.stderr)
        if not shutil.which("git"):
            raise ValueError("Git could not be installed automatically. Install it from https://git-scm.com and press START again.")
        return f"Python {platform.python_version()}, Git installed"

    def check_root(self) -> str:
        contents = [item.name for item in ROOT.iterdir() if item.name not in LAUNCHER_FILES]
        if not contents:
            return self.clone()
        if not (ROOT / "README.md").is_file() or not (ROOT / "studio").is_dir():
            raise ValueError("This folder is neither empty nor a TilTale folder. Move start_TilTale into an empty folder.")
        fresh: bool = not (ROOT / ".git").is_dir()
        if fresh:
            self.connect()
        return self.offer_update(fresh)

    def clone(self) -> str:
        self.log(f"Empty folder: downloading TilTale from {REPOSITORY}…")
        result = run(["git", "clone", REPOSITORY, "_tiltale_tmp"])
        if result.returncode != 0:
            raise ValueError(f"git clone failed: {result.stderr.strip()}")
        temp = ROOT / "_tiltale_tmp"
        for item in temp.iterdir():  # the files belong in the root itself, next to start_TilTale
            if (ROOT / item.name).exists():  # the launcher that is running right now: keep it, the clone has the same
                continue
            shutil.move(str(item), str(ROOT / item.name))
        shutil.rmtree(temp, ignore_errors=True)
        return f"downloaded TilTale {version_in((ROOT / 'config' / 'settings.py').read_text(encoding='utf-8'))}"

    def connect(self) -> None:
        """An unpacked ZIP: connect it to GitHub so future updates can be seen, touching no files."""
        self.log("Connecting this folder to GitHub to stay up to date on future updates…")
        for command in (["git", "init", "-b", "main"], ["git", "remote", "add", "origin", REPOSITORY]):
            result = run(command)
            if result.returncode != 0:
                raise ValueError(f"{' '.join(command)} failed: {result.stderr.strip()}")

    def offer_update(self, fresh: bool) -> str:
        result = run(["git", "fetch", "origin", "main"])
        if result.returncode != 0:
            self.log(f"Could not reach GitHub ({result.stderr.strip()}); continuing with the version on this computer.")
            return "offline: update check skipped"
        if fresh:  # point the new repository at what GitHub has; the files themselves stay untouched
            run(["git", "reset", "--mixed", "origin/main"])
        local = version_in((ROOT / "config" / "settings.py").read_text(encoding="utf-8"))
        newest = version_in(run(["git", "show", "origin/main:config/settings.py"]).stdout)
        if local == newest:
            return f"you are up to date (TilTale {local})"
        if not self.ask(f"You have TilTale version {local} on your computer, but version {newest} is available.\n\n"
                        "Update now? Your /project/ folder (your story) is kept either way."):
            return f"staying on {local}; {newest} is available"
        result = run(["git", "reset", "--hard", "origin/main"])
        if result.returncode != 0:
            raise ValueError(f"Update failed: {result.stderr.strip()}")
        return f"updated to TilTale {newest}"

    def install_packages(self) -> str:
        venv = ROOT / ".venv"
        python = venv_python()
        if not python.exists():
            self.log("Creating the project's own Python environment (.venv)…")
            result = run([sys.executable, "-m", "venv", str(venv)])
            if result.returncode != 0:
                raise ValueError(f"Could not create .venv: {result.stderr.strip()}")
        self.log("Installing the packages from requirements.txt (first time: a minute)…")
        result = run([str(python), "-m", "pip", "install", "-r", "requirements.txt", "--quiet"])
        if result.returncode != 0:
            raise ValueError(f"pip install failed: {result.stderr.strip()[-300:]}")
        return "packages installed in .venv"

    # ------------------------------------------------------------- opening TilTale
    def offer_open(self) -> None:
        dialog = tk.Toplevel(self.window)
        dialog.title("Open TilTale")
        box = ttk.Frame(dialog, padding=16)
        box.pack()
        ttk.Label(box, text="How would you like to open TilTale?").pack(anchor="w", pady=(0, 10))
        ttk.Button(box, text="Open TilTale in the browser (simple)",
                   command=lambda: (dialog.destroy(), self.open_browser())).pack(fill="x", pady=2)
        ttk.Button(box, text="Open TilTale in my editor (expert)",
                   command=lambda: (dialog.destroy(), self.open_editor())).pack(fill="x", pady=2)

    def open_browser(self) -> None:
        self.log("Starting TilTale (python manage.py runserver)… keep this window open while you work.")
        if not self.log_box.winfo_ismapped():
            self.toggle_log()
        flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        self.server = subprocess.Popen([str(self.python), "manage.py", "runserver"], cwd=ROOT,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=flags)
        threading.Thread(target=self.relay_server_log, daemon=True).start()
        threading.Thread(target=self.open_when_ready, daemon=True).start()
        self.mark("open", "✓", "running — ABORT stops TilTale")

    def relay_server_log(self) -> None:
        for line in self.server.stdout:
            self.log(line.rstrip())

    def open_when_ready(self) -> None:
        for _ in range(120):  # two minutes; the first start migrates the database
            try:
                socket.create_connection(("127.0.0.1", STUDIO_PORT), timeout=1).close()
                webbrowser.open(STUDIO_URL)
                self.log(f"TilTale is open: {STUDIO_URL}")
                return
            except OSError:
                time.sleep(1)
        self.log("TilTale did not start; the log above says why.")

    def open_editor(self) -> None:
        if shutil.which("code"):
            run(["code", str(ROOT), str(ROOT / "README.md")])
            self.log("Opened the folder in Visual Studio Code, with the README. Run: python manage.py runserver")
            self.countdown(5)
            return
        webbrowser.open(ROOT.as_uri())  # no editor found: at least show the folder
        self.log("No 'code' command found. Opened the folder instead; see README.md, section 'Run TilTale'.")
        self.mark("open", "✓", "folder opened")

    def countdown(self, seconds: int) -> None:
        if seconds == 0:
            self.window.destroy()
            return
        self.mark("open", "✓", f"done — closing in {seconds}…")
        self.window.after(1000, lambda: self.countdown(seconds - 1))


def main() -> None:
    launcher = Launcher()
    launcher.window.mainloop()
    if launcher.server:
        launcher.server.terminate()


if __name__ == "__main__":
    main()
