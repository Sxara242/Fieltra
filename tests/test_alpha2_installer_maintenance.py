from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer" / "MastixaManager.iss"


class Alpha2InstallerMaintenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.iss = INSTALLER.read_text(encoding="utf-8")

    def test_existing_installation_is_detected_from_stable_app_id(self) -> None:
        self.assertIn(
            "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{B9B946A2-8711-4B35-9BCB-B40210E67357}_is1",
            self.iss,
        )
        self.assertIn("RegKeyExists(HKCU, MastixaUninstallKey)", self.iss)
        self.assertIn("'DisplayVersion'", self.iss)

    def test_same_version_offers_repair_mode(self) -> None:
        self.assertIn("CompareText(InstalledVersion, CurrentVersion) = 0", self.iss)
        self.assertIn("MaintenanceMode := 'repair'", self.iss)
        self.assertIn("Επιδιόρθωση εγκατάστασης (συνιστάται)", self.iss)

    def test_different_version_offers_update_mode(self) -> None:
        self.assertIn("MaintenanceMode := 'update'", self.iss)
        self.assertIn("Ενημέρωση στην έκδοση ' + CurrentVersion + ' (συνιστάται)", self.iss)

    def test_maintenance_modes_preserve_external_user_data(self) -> None:
        self.assertIn("Η τοπική βάση, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας διατηρούνται.", self.iss)
        self.assertNotIn(
            'Type: filesandordirs; Name: "{%LOCALAPPDATA}\\MastixaManager"',
            self.iss,
        )
        self.assertIn(
            "UserDataDir := ExpandConstant('{localappdata}\\MastixaManager')",
            self.iss,
        )
        self.assertIn("and DeleteUserDataOnUninstall", self.iss)


if __name__ == "__main__":
    unittest.main()
