"""Browser selection shared by the local smoke scenarios."""
from pathlib import Path


def launch_chromium(playwright, executable=None):
    system_browser = Path("/usr/bin/chromium")
    if executable is None and system_browser.is_file():
        executable = str(system_browser)
    return playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
