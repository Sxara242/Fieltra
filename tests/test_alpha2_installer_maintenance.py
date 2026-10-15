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
            "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{8A6CE872-CC79-4605-9084-893E304E38AD}_is1",
            self.iss,
        )
        self.assertIn("RegKeyExists(HKCU, MastixaUninstallKey)", self.iss)
        self.assertIn("'DisplayVersion'", self.iss)

    def test_same_version_offers_repair_mode(self) -> None:
        self.assertIn("MaintenanceMode := MaintenanceModeFor", self.iss)
        self.assertIn("MaintenanceMode = 'repair'", self.iss)
        self.assertIn("GetPreviousData('BuildId', '')", self.iss)
        self.assertIn("Επιδιόρθωση εγκατάστασης (συνιστάται)", self.iss)

    def test_upgrade_and_downgrade_are_distinct(self) -> None:
        self.assertIn("MaintenanceMode = 'upgrade'", self.iss)
        self.assertIn("Αναβάθμιση εγκατάστασης (συνιστάται)", self.iss)
        self.assertIn("MaintenanceMode = 'downgrade'", self.iss)
        self.assertIn('MB_YESNO or MB_DEFBUTTON2, IDNO', self.iss)
        self.assertIn('/ALLOWDOWNGRADE', self.iss)

    def test_maintenance_modes_preserve_external_user_data(self) -> None:
        self.assertIn("Η τοπική βάση, τα προφίλ, τα έγγραφα, τα αρχεία καταγραφής και τα αντίγραφα ασφαλείας διατηρούνται.", self.iss)
        self.assertNotIn(
            'Type: filesandordirs; Name: "{%LOCALAPPDATA}\\Fieltra"',
            self.iss,
        )
        self.assertIn(
            "UserDataDir := ExpandConstant('{localappdata}\\Fieltra')",
            self.iss,
        )
        self.assertIn("and DeleteUserDataOnUninstall", self.iss)


if __name__ == "__main__":
    unittest.main()
