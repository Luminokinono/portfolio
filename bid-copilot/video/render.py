"""Rend promo.html image par image puis encode en MP4 (H.264)."""
import subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path(__file__).resolve().parent / "promo.html"
OUT = Path(sys.argv[1])
FPS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
STILLS = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else None

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto(HTML.as_uri()); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    if STILLS:
        for t in STILLS:
            pg.evaluate(f"setTime({t})"); pg.screenshot(path=str(OUT / f"still_{t:05.1f}.png"))
    else:
        dur = pg.evaluate("window.DURATION")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT)],
                              stdin=subprocess.PIPE)
        n = int(dur * FPS)
        for i in range(n):
            pg.evaluate(f"setTime({i / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=95))
            if i % 150 == 0: print(f"{i}/{n}", flush=True)
        ff.stdin.close(); ff.wait()
    b.close()
