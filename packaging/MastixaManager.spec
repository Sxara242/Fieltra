from pathlib import Path
import runpy


repo_root = Path(SPECPATH).resolve().parent
app_icon = repo_root / "packaging" / "mastixa_manager.ico"
runpy.run_path(str(repo_root / "packaging" / "validate_windows_release.py"))["require_ready"](repo_root)

tls = runpy.run_path(str(repo_root / "packaging" / "tls_inputs.py"))
tls_lock, tls_roots, tls_files = tls["prepare"](repo_root)
legal_data_entries = runpy.run_path(str(repo_root / "packaging" / "legal_inputs.py"))["legal_data_entries"]
with tls["supplier_environment"](tls_roots):
    analysis = Analysis(
        [str(repo_root / "main.py")],
        pathex=[str(repo_root)],
        binaries=[(str(source), ".") for name, (source, digest) in tls_files.items() if tls["is_openssl"](name)],
        datas=[
            (str(repo_root / "app" / "assets"), "app/assets"),
            (str(repo_root / "app" / "locales"), "app/locales"),
            (str(repo_root / "LICENSE"), "."),
            (str(repo_root / "THIRD_PARTY_NOTICES.md"), "."),
            *legal_data_entries(repo_root),
            (str(repo_root / "docs" / "DISTRIBUTION_SOURCE.md"), "."),
            (str(repo_root / "docs" / "SOURCE_DELIVERY_PLAN.md"), "."),
            (str(repo_root / "docs" / "source-artifacts.json"), "."),
            (str(repo_root / "updates" / "staging"), "updates/staging"),
        ],
        hiddenimports=[],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=["tkinter", "unittest", "test", "tests", "PySide6.QtVirtualKeyboard"],
        noarchive=False,
        optimize=1,
    )

# The Codex build runtime exposes Poppler's ICU 78 DLLs on PATH. Qt 6 on
# Windows links against the operating system ICU API; bundling Poppler's
# same-named DLL would shadow that API and prevent QtCore from loading.
incompatible_icu = {"icuuc.dll", "icudt78.dll"}
analysis.binaries = [
    entry
    for entry in analysis.binaries
    if Path(entry[0]).name.casefold() not in incompatible_icu
]

# QtGui hooks collect platforminputcontexts even without a direct import.
# Filter both binary and data TOCs, including QML resources, before COLLECT.
without_unused_windows_components = runpy.run_path(
    str(repo_root / "packaging" / "qt_exclusions.py")
)["without_unused_windows_components"]
analysis.binaries = without_unused_windows_components(analysis.binaries)
analysis.datas = without_unused_windows_components(analysis.datas)
mesa = runpy.run_path(str(repo_root / "packaging" / "mesa_policy.py"))
mesa["verify_analysis"]([*analysis.binaries, *analysis.datas])
tls["verify_analysis"](analysis.binaries, tls_files)

# B2-qualified central CRT deployment. Original supplier wheels are immutable;
# normalize only five hash-locked third-party import strings in build output.
from PyInstaller.config import CONF
epsg = runpy.run_path(str(repo_root / "packaging" / "epsg_provenance.py"))
analysis.datas = epsg["normalize_analysis"](
    analysis.datas, repo_root, Path(CONF["workpath"]) / "epsg-provenance"
)
crt = runpy.run_path(str(repo_root / "packaging" / "crt_policy.py"))
analysis.binaries = crt["normalize_analysis"](
    analysis.binaries, repo_root, Path(CONF["workpath"]) / "canonical-crt"
)
if any(crt["is_crt"](entry[0]) for entry in analysis.datas):
    raise RuntimeError("B2: Microsoft CRT unexpectedly collected as data")

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Fieltra",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_icon),
    version=str(repo_root / "packaging" / "version_info.txt"),
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Fieltra",
)
mesa["verify_bundle"](Path(bundle.name))
crt["verify_bundle"](Path(bundle.name), repo_root)
epsg["verify_bundle"](Path(bundle.name), repo_root)
