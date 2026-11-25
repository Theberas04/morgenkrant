#!/usr/bin/env python3
"""Schermafbeeldingen van de krantenpagina (headless Chromium via CDP).

  python scripts/shoot.py [url] [uitmap]
"""
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/home/hermes/tools")
from cdp import CDP  # noqa: E402

CHROME_CANDIDATES = sorted(pathlib.Path.home().glob(".hermes/tools/chromium-*/chrome-linux64/chrome"))
LIB_DIRS = [
    str(pathlib.Path.home() / ".local/lib"),
    str(pathlib.Path.home() / ".local/chromelibs/usr/lib/x86_64-linux-gnu"),
    str(pathlib.Path.home() / ".local/chromedeps/root/usr/lib/x86_64-linux-gnu"),
]


def start_chrome(profile):
    chrome = str(CHROME_CANDIDATES[-1])
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join(LIB_DIRS + [env.get("LD_LIBRARY_PATH", "")])
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={profile}",
         "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars",
         "--force-color-profile=srgb", "about:blank"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port_file = pathlib.Path(profile) / "DevToolsActivePort"
    for _ in range(100):
        if port_file.exists() and port_file.read_text().strip():
            return proc, int(port_file.read_text().split()[0])
        time.sleep(0.15)
    proc.kill()
    raise RuntimeError("Chromium startte niet (geen DevToolsActivePort)")


def open_tab(port, url):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{url}", method="PUT")
    with urllib.request.urlopen(req, timeout=10) as antwoord:
        import json
        return json.load(antwoord)["webSocketDebuggerUrl"]


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8420/"
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/home/hermes/.hermes/cache/scratch")
    out.mkdir(parents=True, exist_ok=True)
    profile = pathlib.Path("/tmp/krant-profiel")
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True)

    proc, port = start_chrome(profile)
    try:
        cdp = CDP(open_tab(port, "about:blank"))
        cdp.call("Page.enable")
        cdp.call("Emulation.setEmulatedMedia", media="screen")

        # laptop
        cdp.call("Emulation.setDeviceMetricsOverride", width=1440, height=1000,
                 deviceScaleFactor=1, mobile=False)
        cdp.call("Page.navigate", url=url)
        cdp.wacht(2.5)
        print("titel:", cdp.js("document.title"))
        print("artikelen:", cdp.js("document.querySelectorAll('article').length"))
        print("viewport:", cdp.js("document.documentElement.clientWidth + 'x' + window.innerHeight"))
        cdp.schermafbeelding(str(out / "web-laptop.png"))

        # telefoon
        cdp.call("Emulation.setDeviceMetricsOverride", width=390, height=844,
                 deviceScaleFactor=2, mobile=True)
        cdp.call("Page.navigate", url=url)
        cdp.wacht(2.0)
        print("telefoon viewport:", cdp.js("document.documentElement.clientWidth"))
        cdp.schermafbeelding(str(out / "web-telefoon.png"))

        cdp.js("document.querySelector('#techniek') ? document.querySelector('#techniek').scrollIntoView() : window.scrollBy(0, 2400)")
        cdp.wacht(1.0)
        cdp.schermafbeelding(str(out / "web-telefoon-tech.png"))
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()