"""Render the 60s film to MP4 (deterministic frame capture)."""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = (HERE / "mosense-film-60s.html").resolve().as_uri() + "?capture"
FRAMES_DIR = HERE / "frames60"
FPS = 30
DUR = 60.0
W, H = 1920, 1080


def main() -> None:
    FRAMES_DIR.mkdir(exist_ok=True)
    total = int(DUR * FPS)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto(PAGE)
        page.wait_for_function("window.__ready === true", timeout=15000)
        page.evaluate("document.fonts.ready.then(() => true)")
        page.wait_for_timeout(1200)

        for i in range(total):
            t = i / FPS
            page.evaluate(f"window.__seek({t!r})")
            page.screenshot(path=str(FRAMES_DIR / f"f{i:05d}.png"), type="png")
            if i % 120 == 0:
                print(f"frame {i}/{total} (t={t:.1f}s)", flush=True)
        browser.close()

    out = HERE / "mosense-film-60s-silent.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES_DIR / "f%05d.png"),
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ]
    print("encoding...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:], file=sys.stderr)
        sys.exit(1)
    print(f"done: {out}")


if __name__ == "__main__":
    main()
