from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_uninstaller_keeps_user_data_by_default_and_supports_explicit_full_purge() -> None:
    iss = (ROOT / "installer" / "MastixaManager.iss").read_text(encoding="utf-8")

    # Normal uninstall only removes the dedicated install directory.
    assert '[UninstallDelete]' in iss
    assert 'Type: filesandordirs; Name: "{app}"' in iss
    assert 'Type: filesandordirs; Name: "{localappdata}\\Fieltra"' not in iss

    # Full purge is opt-in and targets only Fieltra user data.
    assert "DeleteUserDataOnUninstall" in iss
    assert "MB_YESNO or MB_DEFBUTTON2" in iss
    assert "IDNO) = IDYES" in iss
    assert "CmdLineParamExists('/PURGEDATA')" in iss
    assert "ExpandConstant('{localappdata}\\Fieltra')" in iss
    assert "DelTree(UserDataDir, True, True, True)" in iss
    assert "RegDeleteKeyIncludingSubkeys(HKCU, 'Software\\Fieltra\\Fieltra')" in iss
    assert "τοπικά δεδομένα, οι προτιμήσεις, τα προφίλ" in iss

    # Silent uninstall preserves data unless /PURGEDATA was explicitly supplied.
    assert "CmdLineParamExists('/SILENT')" in iss
    assert "CmdLineParamExists('/VERYSILENT')" in iss
