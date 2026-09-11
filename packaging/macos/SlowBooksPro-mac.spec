# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the native macOS build (.app bundle).
#
# STARTING POINT — adapted from packaging/windows/SlowBooksPro.spec and
# not yet validated on real Apple hardware. Expected iteration areas:
#   * WeasyPrint natives: on macOS these come from Homebrew (pango,
#     fontconfig, gobject-introspection). PyInstaller's hooks usually pick
#     the dylibs up automatically from the brew prefix; if PDF rendering
#     fails in the frozen app, stage them explicitly like the Windows
#     build stages its gtk-dlls.
#   * pywebview uses the Cocoa/WebKit backend on macOS (pyobjc) — no
#     pythonnet, no WebView2, one less runtime dependency than Windows.
#   * Icon: assets/icon-256.png → .icns (see the workflow step).

import os
import subprocess

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))


def _tree(src_rel, dest):
    """Recursively collect a repo directory as data files, skipping caches."""
    out = []
    src_root = os.path.join(ROOT, src_rel)
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fname in filenames:
            if fname.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(dirpath, fname)
            rel_dir = os.path.relpath(dirpath, src_root)
            target = dest if rel_dir == "." else os.path.join(dest, rel_dir)
            out.append((full, target))
    return out


def _brew_library(formula, filename):
    """Resolve one required Homebrew dylib or fail the build loudly."""
    prefix = subprocess.run(
        ["brew", "--prefix", formula],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    path = os.path.join(prefix, "lib", filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"required {formula} library not found: {path}")
    return path


datas = [
    (os.path.join(ROOT, "index.html"), "."),
    (os.path.join(ROOT, "alembic.ini"), "."),
    (os.path.join(ROOT, ".env.example"), "."),
]
datas += _tree("app/static", "app/static")
datas += _tree("app/templates", "app/templates")
# Alembic loads migration scripts as FILES at runtime (script_location) —
# they must exist on disk in the bundle, not just inside the PYZ.
datas += _tree("migrations", "migrations")

# PyInstaller's WeasyPrint hook uses ctypes.util.find_library(), which does
# not find Homebrew libraries on Apple Silicon. Seed the six libraries that
# WeasyPrint dlopens; PyInstaller follows and rewrites their dependency
# closure into Contents/Frameworks.
binaries = [
    (_brew_library("glib", "libgobject-2.0.0.dylib"), "."),
    (_brew_library("pango", "libpango-1.0.dylib"), "."),
    (_brew_library("pango", "libpangoft2-1.0.dylib"), "."),
    (_brew_library("harfbuzz", "libharfbuzz.0.dylib"), "."),
    (_brew_library("harfbuzz", "libharfbuzz-subset.0.dylib"), "."),
    (_brew_library("fontconfig", "libfontconfig.1.dylib"), "."),
]

hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + collect_submodules("alembic")
    + [
        # pywebview's macOS backend (Cocoa/WebKit via pyobjc)
        "webview.platforms.cocoa",
        # alembic.ini logging config and desktop SQLite dialect
        "logging.config",
        "sqlalchemy.dialects.sqlite",
        # WeasyPrint is imported lazily since #121 (so the suite runs on a
        # machine without the native stack). PyInstaller's scanner does walk
        # function-level imports, but the PDF engine is not something to
        # leave to "usually" — name it, so its hook always fires.
        "weasyprint",
    ]
)

# Built-in OCR: Apple Vision via pyobjc (requirements-build.txt), imported
# lazily inside VisionEngine._bridge — invisible to the scanner. Guarded so
# a build env without the Vision wheels still bundles (tesseract fallback).
for _mod in ("Vision", "Quartz", "objc", "Foundation"):
    try:
        hiddenimports += collect_submodules(_mod)
    except Exception:
        pass

a = Analysis(
    [os.path.join(ROOT, "desktop_launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["psycopg2", "psycopg2_binary"],
    noarchive=False,
)
# ---------------------------------------------------------------------------
# One HarfBuzz, and it must be Homebrew's (issue #141, reported by mdornich)
# ---------------------------------------------------------------------------
# PyInstaller collects TWO HarfBuzz builds into the bundle:
#
#   Contents/Frameworks/PIL/.dylibs/libharfbuzz.0.dylib   Pillow's,   ~1.81 MB
#   Contents/Frameworks/libharfbuzz.dylib                 Homebrew's, ~1.32 MB
#   Contents/Frameworks/libharfbuzz-subset.0.dylib        Homebrew's, ~1.36 MB
#
# Both answer to the install name @rpath/libharfbuzz.0.dylib, so whichever
# loads first wins for the whole process. The `binaries` list above seeds
# Homebrew's under the VERSIONED name, but PyInstaller's PIL hook wins the
# filename collision and turns Contents/Frameworks/libharfbuzz.0.dylib into a
# symlink into PIL/. Homebrew's real library then sits in the bundle under the
# unversioned name where nothing resolves to it.
#
# Pango therefore gets Pillow's HarfBuzz while libharfbuzz-subset is
# Homebrew's — and `libharfbuzz-subset` only exists in the Homebrew build. The
# first PDF render dies in native code.
#
# Dropping Pillow's copy is safe, and that was checked rather than assumed:
# the pinned pillow wheel ships neither libraqm nor libfribidi, so complex
# shaping is off and `PIL.features.check('harfbuzz')` is False; and nothing in
# app/ draws text with Pillow at all — it appears only in ocr_service.py and
# ocr_regions.py, for image preprocessing. All 25 hb_* symbols _imagingft
# imports are exported by Homebrew's build.
#
# The assertion below is the important half. Getting this wrong in the other
# direction — removing Pillow's copy while Homebrew's sits under the
# unversioned name — turns a PDF crash into an import failure, which is worse
# and easier to ship by accident. So the build FAILS here rather than
# producing a bundle nobody looks inside.
_PIL_HARFBUZZ = [
    (dest, src, kind)
    for (dest, src, kind) in a.binaries
    if "libharfbuzz" in os.path.basename(dest) and "PIL" in dest.split(os.sep)
]
for entry in _PIL_HARFBUZZ:
    a.binaries.remove(entry)
    print(f"[spec] #141: dropped Pillow's HarfBuzz: {entry[0]}")

_HARFBUZZ_VERSIONED = [
    dest
    for (dest, _src, _kind) in a.binaries
    if os.path.basename(dest) == "libharfbuzz.0.dylib"
]
if len(_HARFBUZZ_VERSIONED) != 1:
    raise SystemExit(
        f"[spec] #141: expected exactly one libharfbuzz.0.dylib in the bundle, "
        f"found {len(_HARFBUZZ_VERSIONED)}: {_HARFBUZZ_VERSIONED}. Pango "
        f"resolves @rpath/libharfbuzz.0.dylib; zero copies is an import "
        f"failure and two is a silent collision that kills the first PDF "
        f"render."
    )
if "PIL" in _HARFBUZZ_VERSIONED[0].split(os.sep):
    raise SystemExit(
        f"[spec] #141: the only libharfbuzz.0.dylib is Pillow's "
        f"({_HARFBUZZ_VERSIONED[0]}); libharfbuzz-subset is Homebrew's and "
        f"they are not interchangeable."
    )
print(f"[spec] #141: one HarfBuzz, at {_HARFBUZZ_VERSIONED[0]}")


pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="SlowBooksPro",
    console=False,
    icon=os.path.join(SPECPATH, "slowbookspro.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="SlowBooksPro",
)

def _build_sha() -> str:
    sha = os.environ.get("APP_BUILD_SHA", "").strip()
    if not sha:
        try:
            import subprocess

            sha = subprocess.run(
                ["git", "-C", ROOT, "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        except Exception:
            sha = ""
    return sha[:12] or "unknown"


def _bundle_version() -> str:
    return f"{os.environ.get('APP_VERSION', '0.0.0')}+{_build_sha()}"


app = BUNDLE(
    coll,
    name="SlowBooks Pro.app",
    icon=os.path.join(SPECPATH, "slowbookspro.icns"),
    bundle_identifier="com.vonholtencodes.slowbookspro",
    info_plist={
        "CFBundleShortVersionString": os.environ.get("APP_VERSION", "0.0.0"),
        # Build identity (testing-repo #28): two builds of one release must
        # be distinguishable from the bundle alone. CI passes APP_BUILD_SHA;
        # a local build reads the checkout. The workflow refuses a bundle
        # whose CFBundleVersion is just the short version.
        "CFBundleVersion": _bundle_version(),
        "LSMinimumSystemVersion": "14.0",
        "LSArchitecturePriority": ["arm64"],
        "NSHighResolutionCapable": True,
        # The app runs a local web server for its own UI
        "NSLocalNetworkUsageDescription": (
            "SlowBooks Pro runs a loopback server for its desktop interface."
        ),
        # TCC usage strings. macOS shows these in the consent prompt the
        # first time the app writes to a protected folder; without them
        # the prompt has no explanation and looks like malware asking.
        # Save PDF writes under Documents; Download Backup writes to
        # Downloads. Keep them in step with desktop_launcher._reports_dir
        # and save_backup_file.
        "NSDocumentsFolderUsageDescription": (
            "SlowBooks Pro saves the reports you export to "
            "Documents/SlowBooks Pro/Reports."
        ),
        "NSDownloadsFolderUsageDescription": (
            "SlowBooks Pro saves company backups to your Downloads folder."
        ),
    },
)
