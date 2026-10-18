"""Desktop presentation routes reuse the existing pages and data contracts."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QDate, QEvent, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox, QTabWidget

import main  # Exercise the real, ordered desktop installers in this process.
from app import main_window, language, year_context
from app.database import Database
from app.layout_preferences import layout_mode
from app.profile_manager import ProfileManager
from app.appearance_theme import ThemeController
from app.startup_lazy_pages import LazyPage


class UiRevampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.profiles = ProfileManager(self.root)
        self.db = Database(self.profiles.active_profile.database_path)
        self.db.set_app_setting("auto_backup_enabled", "0")
        year_context.set_active_working_year(self.db, 2027, audit=False)
        self.previous_language = language._active_controller
        self.had_app_controller = hasattr(self.app, "_mastixa_language_controller")
        self.previous_app_controller = getattr(self.app, "_mastixa_language_controller", None)
        self.previous_enabled = getattr(self.previous_app_controller, "_enabled", False)
        self.controller = language.LanguageController(self.app, self.profiles)
        self.theme = ThemeController(self.app, main_window.STYLESHEET, main_window.build_app_palette())
        self.theme.apply_saved_theme()
        self.window = main_window.MainWindow(self.theme, self.profiles, self.controller)
        self.nav = self.window.desktop_navigation
        self.home = self.window.farm_home
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.window._skip_close_backup = True
        self.window.close()
        for tabs in self.window.findChildren(QTabWidget):
            tabs.blockSignals(True)
        for _title, page in self.window.pages:
            page.deleteLater()
        self.window.deleteLater()
        self.app.removeEventFilter(self.controller)
        self.app.removeEventFilter(self.theme)
        self.controller._enabled = False
        if self.had_app_controller:
            self.app._mastixa_language_controller = self.previous_app_controller
        else:
            del self.app._mastixa_language_controller
        if self.previous_app_controller is not None:
            self.previous_app_controller._enabled = self.previous_enabled
            if self.previous_enabled:
                self.app.installEventFilter(self.previous_app_controller)
        language.install_language_controller(self.previous_language)
        # Finish deletion of this fixture's widgets before its temporary DB goes.
        self.controller.deleteLater()
        self.theme.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def snapshot(self):
        with self.db.connect() as con:
            return tuple(con.iterdump())

    def test_six_groups_all_pages_reachable_without_eager_construction(self):
        self.assertEqual(["Αρχική", "Αγρόκτημα", "Εργασίες", "Οικονομικά", "Αναφορές", "Σύστημα"],
                         [self.nav.model.item(i).text() for i in range(6)])
        self.assertEqual(set(range(len(self.window.pages))), {target.page for target in self.nav.targets.values()})
        self.assertTrue(all(not page.is_loaded for _, page in self.window.pages if isinstance(page, LazyPage)))
        for i in range(6):
            self.assertFalse(self.nav.model.item(i).icon().isNull())
        self.assertTrue(all(item.icon().isNull() for item in self.nav.items.values() if item.parent() is not None))
        # Navigate the real container graph, without constructing every business UI.
        with patch.object(self.window, "_refresh_current_tab"):
            for index in range(len(self.window.pages)):
                self.window.change_page(index)
                self.assertEqual(index, self.window._current_page_index())
        self.assertEqual(26, self.nav.targets["sale"].page)
        self.assertEqual(4, self.nav.targets["income"].page)
        self.assertFalse(self.nav.items["revenue"].hasChildren())
        self.assertFalse(self.nav.items["home"].hasChildren())
        self.assertFalse(self.nav.items["reports"].hasChildren())

    def test_quick_routes_reuse_forms_preserve_drafts_and_database(self):
        for key, page_index in (("production", 3), ("sale", 26), ("expense", 5), ("income", 4), ("activity", 12), ("planting", 23)):
            self.home.quick_buttons[key].click()
            self.assertEqual(page_index, self.window._current_page_index())
            page = self.window.pages[page_index][1].resolved_page()
            self.assertIsNotNone(page.form_box)
            before = self.snapshot()
            with patch.object(page, "clear_form") as clear:
                self.home.quick_buttons[key].click()
                clear.assert_not_called()
            self.assertIs(page, self.window.pages[page_index][1].resolved_page())
            self.assertEqual(before, self.snapshot())
        page = self.window.pages[4][1].resolved_page()
        page.description.setText("unsaved Ω {name}")
        self.nav.open("home")
        self.home.quick_buttons["income"].click()
        self.assertEqual("unsaved Ω {name}", page.description.text())

    def test_language_cycle_navigation_and_raw_context_do_not_query_or_write(self):
        self.home.profile_name = "Save Αποθήκευση <raw> & {year}"
        before = self.snapshot()
        for code in ("en", "el", "en"):
            # Home presentation refresh and tree translation are cached-only.
            with patch.object(self.db, "query", side_effect=AssertionError("Unexpected read")):
                self.controller.set_language(code, persist=False)
                self.home.render()
            self.assertEqual("Home" if code == "en" else "Αρχική", self.nav.model.item(0).text())
            self.assertIn(self.home.profile_name, self.home.context.text())
            self.assertEqual(Qt.TextFormat.PlainText, self.home.context.textFormat())
        self.assertEqual(before, self.snapshot())

    def test_home_existing_alert_data_empty_history_and_fields_read_only(self):
        self.nav.open("activity")
        self.nav.open("inventory")
        self.db.execute("INSERT INTO fields(name,location) VALUES(?,?)", ("<Ω field>", "Raw Save"))
        self.db.execute("INSERT INTO farm_activities(activity_date,category,status) VALUES(?,?,?)",
                        (QDate.currentDate().addDays(-1).toString("yyyy-MM-dd"), "Πότισμα", "Προγραμματισμένη"))
        self.db.execute("INSERT INTO inventory_items(name,unit,minimum_stock) VALUES('Seed','pieces',2)")
        before = self.snapshot()
        self.home.refresh()
        self.assertEqual(1, self.home.snapshot["overdue"])
        self.assertEqual(1, self.home.snapshot["low"])
        self.assertEqual("<Ω field> · Raw Save", self.home.field_rows[0].text())
        self.assertFalse(self.home.recent_empty.isHidden())
        self.assertEqual(before, self.snapshot())

    def test_layout_preference_persists_per_profile_and_changes_same_widgets(self):
        self.assertEqual("simple", layout_mode(self.db))
        self.nav.open("settings")
        settings = self.window.pages[31][1].resolved_page()
        cards = tuple(self.window.pages[0][1].production)
        for i in range(6):
            self.db.execute("INSERT INTO fields(name) VALUES(?)", (f"Field {i}",))
        self.home.refresh()
        self.assertTrue(self.home.field_rows[3].isHidden())
        settings.layout_mode_combo.setCurrentIndex(1)
        self.assertEqual("advanced", layout_mode(Database(self.db.path)))
        self.assertFalse(self.home.field_rows[5].isHidden())
        self.assertEqual(cards, tuple(self.window.pages[0][1].production))
        other = Database(self.root / "other.db")
        self.assertEqual("simple", layout_mode(other))
        settings.layout_mode_combo.setCurrentIndex(0)
        self.assertEqual("simple", layout_mode(self.db))

    def test_reset_settings_resynchronizes_layout_preference_and_home(self):
        self.nav.open("settings")
        settings = self.window.pages[31][1].resolved_page()
        settings.layout_mode_combo.setCurrentIndex(1)
        self.assertEqual("advanced", self.home.mode)
        self.db.reset_app_settings()
        settings.refresh()
        self.assertEqual("simple", settings.layout_mode_combo.currentData())
        self.assertEqual("simple", self.home.mode)
        self.assertEqual("simple", layout_mode(self.db))

    def test_backup_profiles_updates_and_map_use_existing_controls(self):
        dashboard = self.window.pages[0][1]
        self.nav.open("backup")
        panel = self.window.pages[self.nav.targets["backup"].page][1]
        self.assertTrue(panel.isAncestorOf(dashboard.safety_box))
        for route in ("profiles", "backup_settings", "updates"):
            self.nav.open(route)
            self.assertEqual(31, self.window._current_page_index())
        settings = self.window.pages[31][1].resolved_page()
        self.assertTrue(settings.tabs.currentWidget().isAncestorOf(settings._mastixa_check_updates_button))
        self.assertIsNone(settings._mastixa_update_info)
        self.nav.open("map")
        self.assertEqual(2, self.window._current_page_index())
        self.assertTrue(hasattr(self.window.pages[2][1].resolved_page(), "open_map"))

    def test_year_lock_and_correction_context_survive_quick_navigation(self):
        self.nav.quick_entry("production")
        page = self.window.pages[3][1].resolved_page()
        self.db.execute("INSERT OR REPLACE INTO year_locks(year,is_locked,reason) VALUES(2027,1,'locked')")
        self.home.refresh()
        self.assertIn("Κλειδωμένο", self.home.context.text())
        before = self.snapshot()
        with patch("app.production.warn_locked_year") as warning:
            page.save_production()
            warning.assert_called_once()
        self.assertEqual(before, self.snapshot())
        year_context.begin_year_correction(self.db, 2027, "Ω raw reason")
        try:
            self.home.refresh()
            self.assertIn("Προσωρινή διόρθωση", self.home.context.text())
            self.assertEqual("Ω raw reason", year_context.correction_state(self.db).reason)
            self.assertIs(self.window._year_correction_guard.window, self.window)
        finally:
            year_context.finish_year_correction(self.db)

    def test_small_window_scroll_and_dark_palette(self):
        self.window.resize(950, 650)
        self.window.show()
        self.app.processEvents()
        self.assertGreater(self.home.scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.window.tabs.tabBar().isHidden())
        self.theme.set_theme("dark", persist=False)
        self.assertLess(self.nav.tree.palette().base().color().lightness(), 128)
        self.assertGreater(self.nav.tree.palette().text().color().lightness(), 128)

    def test_settings_tools_button_remains_readable_across_theme_cycle(self):
        from PySide6.QtGui import QPalette
        from tests.test_dashboard_theme_contrast import contrast
        self.nav.open("settings")
        self.window.show()
        for theme in ("light", "dark", "light"):
            self.theme.set_theme(theme, persist=False)
            self.app.processEvents()
            self.nav.tools.ensurePolished()
            palette = self.nav.tools.palette()
            self.assertTrue(self.nav.tools.isVisible())
            self.assertGreater(self.nav.tools.font().pointSizeF(), 0)
            self.assertGreaterEqual(contrast(
                palette.color(QPalette.ColorRole.ButtonText),
                palette.color(QPalette.ColorRole.Button)), 4.5)

    def test_home_recent_history_density_and_keyboard_navigation(self):
        from PySide6.QtTest import QTest
        self.nav.open("fields")  # Initialize its existing lazy schema before snapshotting.
        self.nav.open("history")
        for i in range(6):
            self.db.execute("INSERT INTO audit_events(event_time,table_name,action,record_id,details) VALUES(?,?,?,?,?)",
                            ("2027-01-01 10:00:00", "fields", "UPDATE", str(i), "<raw> Save {year}"))
        self.nav.open("home")
        before = self.snapshot()
        self.home.set_mode("simple")
        self.assertTrue(self.home.recent_rows[3].isHidden())
        self.home.set_mode("advanced")
        self.assertFalse(self.home.recent_rows[5].isHidden())
        self.assertIn("<raw> Save {year}", self.home.recent_rows[0].text())
        self.window.show()
        self.nav.tree.setFocus()
        QTest.keyClick(self.nav.tree, Qt.Key.Key_Down)
        self.assertEqual(2, self.window._current_page_index())
        self.assertEqual(before, self.snapshot())

    def test_native_profile_switch_builds_one_shared_home_with_own_preference(self):
        child = self.profiles.create("Second Ω {profile}")
        child_db = Database(child.database_path)
        child_db.set_app_setting("auto_backup_enabled", "0")
        child_db.set_app_setting("desktop_layout_mode", "advanced")
        controller = main_window.ApplicationController(self.app, self.theme, self.profiles, self.controller)
        controller.window = self.window
        controller.switch_profile(child.id)
        self.window = controller.window
        self.assertEqual(child.database_path, self.window.db.path)
        self.assertEqual("advanced", self.window.farm_home.mode)
        self.assertIn(child.name, self.window.farm_home.context.text())
        self.assertEqual(6, self.window.desktop_navigation.model.rowCount())
        self.assertTrue(all(not page.is_loaded for _, page in self.window.pages if isinstance(page, LazyPage)))

    def test_all_navigation_labels_and_layout_controls_follow_language(self):
        import re
        self.nav.open("settings")
        settings = self.window.pages[31][1].resolved_page()
        before = self.snapshot()
        for code in ("en", "el", "en"):
            self.controller.set_language(code, persist=False)
            self.assertEqual("Simple" if code == "en" else "Απλή", settings.layout_mode_combo.itemText(0))
            self.assertEqual("Advanced" if code == "en" else "Προχωρημένη", settings.layout_mode_combo.itemText(1))
            self.assertEqual("simple", settings.layout_mode_combo.currentData())
            if code == "en":
                for key, item in self.nav.items.items():
                    with self.subTest(route=key):
                        self.assertIsNone(re.search(r"[\u0370-\u03ff]", item.text()), item.text())
                for button in self.home.quick_buttons.values():
                    self.assertIsNone(re.search(r"[\u0370-\u03ff]", button.text()), button.text())
        self.assertEqual(before, self.snapshot())

    def test_resize_does_not_refresh_home_or_construct_lazy_pages(self):
        self.window.show()
        self.app.processEvents()
        before = [page.is_loaded for _, page in self.window.pages if isinstance(page, LazyPage)]
        with patch.object(self.home, "refresh") as refresh:
            for width, height in ((1000, 700), (1100, 750), (950, 650)):
                self.window.resize(width, height)
                self.app.processEvents()
            refresh.assert_not_called()
        self.assertEqual(before, [page.is_loaded for _, page in self.window.pages if isinstance(page, LazyPage)])

    def test_catalog_placeholders_and_existing_catalogs_are_preserved(self):
        import json
        from string import Formatter
        path = Path(__file__).parents[1] / "app/locales/en_ui_revamp.json"
        pairs = json.loads(path.read_text(encoding="utf-8"))["translations"]
        def slots(text):
            return sorted((field, spec, conv or "") for _, field, spec, conv in Formatter().parse(text) if field is not None)
        for source, target in pairs.items():
            self.assertTrue(target)
            self.assertEqual(slots(source), slots(target))
        for other in path.parent.glob("*.json"):
            if other != path:
                keys = json.loads(other.read_text(encoding="utf-8"))["translations"]
                self.assertFalse(set(pairs) & set(keys), other.name)

    def test_work_selector_reuses_pages_and_keeps_production_separate(self):
        self.nav.open("activity")
        activity = self.window.pages[12][1].resolved_page()
        for key, index in (("fertilization", 12), ("planting", 23), ("protection", 19), ("irrigation", 12)):
            self.nav.selector.setCurrentIndex(self.nav.selector.findData(key))
            self.assertEqual(index, self.window._current_page_index())
            self.assertEqual(self.nav.items["activity"].index(), self.nav.tree.currentIndex())
        self.assertIs(activity, self.window.pages[12][1].resolved_page())
        self.assertEqual("irrigation", activity.category.currentData())
        self.assertFalse(self.nav.selector.model().item(self.nav.selector.findData("other")).isEnabled())
        self.assertEqual(3, self.nav.targets["production"].page)
        self.assertEqual(2, activity.category.count())  # No invented generic save path.

    def test_one_refresh_no_transient_pages_and_revision_invalidation(self):
        self.nav.open("sale")
        self.assertFalse(self.window.pages[4][1].is_loaded)
        page = self.window.pages[26][1].resolved_page()
        self.nav.open("home")
        with patch.object(page, "refresh", wraps=page.refresh) as refresh:
            self.nav.open("sale")
            refresh.assert_not_called()
            self.nav.open("home")
            self.db.set_app_setting("farm_name", "Changed elsewhere")
            self.nav.open("sale")
            self.assertEqual(1, refresh.call_count)
        self.assertFalse(self.window.pages[4][1].is_loaded)

    def test_reports_and_secondary_destinations_remain_reachable(self):
        self.nav.open("reports")
        from app.desktop_navigation import ReportsHub
        self.assertIsInstance(self.window.pages[self.window._current_page_index()][1], ReportsHub)
        self.assertFalse(self.window.pages[8][1].is_loaded)
        for key in ("annual_report", "inventory_report", "field_finance", "sales_report"):
            self.nav.open(key)
            self.assertEqual(self.nav.targets[key].page, self.window._current_page_index())
            self.assertEqual(self.nav.items["reports"].index(), self.nav.tree.currentIndex())
        for key in ("declaration", "package", "invoices"):
            self.nav.open(key)
            page = self.window.pages[self.nav.targets[key].page][1].resolved_page()
            self.assertTrue(page.property("mastixaUnderConstruction"))

    def test_field_actions_preserve_selected_field_context(self):
        field_id = self.db.execute("INSERT INTO fields(name) VALUES('Context field')")
        self.nav.open("fields")
        self.window.pages[2][1].resolved_page().selected_field_id = field_id
        for key in ("field_profile", "plants"):
            self.nav.context_action(key)
            page = self.window.pages[self.nav.targets[key].page][1].resolved_page()
            combo = page.field if key == "field_profile" else page.field_filter
            self.assertEqual(str(field_id), str(combo.currentData()))

    def _cadastral_only_field(self):
        from app.gis.kaek_lookup import LookupStore
        from app.gis.kaek_provider import NorthAegeanProvider
        from app.gis.geometry import manual_coordinates
        field_id = self.db.execute("INSERT INTO fields(name,kaek) VALUES(?,?)",
                                   ("Synthetic cadastral-only field", "510000000001"))
        provider = NorthAegeanProvider(self.root / "unused-cache")
        store = LookupStore(self.db)
        store.enqueue(field_id, provider)
        request = store.claim(provider)
        geometry = manual_coordinates("26 38\n26.001 38\n26.001 38.001\n26 38.001", "EPSG:4326")
        store.complete(dict(request, kind="kaek-result", geometry=geometry.original,
                            source_crs="EPSG:4326", provider=provider.identity,
                            source_url=provider.source_url, terms_url=provider.terms_url,
                            attribution=provider.attribution, source_date="2026-10-06",
                            retrieved_at=store.clock()), provider)
        return field_id

    def _assert_cadastral_map(self, dialog, field_id):
        self.assertEqual(field_id, dialog.field_id)
        self.assertIsNone(dialog.record)  # No cultivation polygon is required.
        self.assertIsNotNone(dialog.map.cadastral_item)
        self.assertTrue(dialog.map.cadastral_item.isVisible())
        self.assertIsNotNone(dialog.map.cadastral_bounds)
        self.assertFalse(dialog.map.boundaries)
        self.assertFalse(dialog.map.pending)
        dialog.map.shutdown()
        dialog.deleteLater()
        return 0

    def test_fields_header_map_opens_cadastral_only_dialog(self):
        field_id = self._cadastral_only_field()
        self.nav.open("fields")
        fields = self.window.pages[2][1].resolved_page()
        fields.load_selected(0, 0)
        fields.name.setText("Unsaved field-name edit")
        before = self.snapshot()
        opened = []

        def open_dialog(dialog):
            result = self._assert_cadastral_map(dialog, field_id)
            opened.append(dialog.field_id)
            return result

        with patch("app.gis.kaek_provider.NorthAegeanProvider.fetch") as fetch, patch(
            "app.gis.dialog.ParcelMapDialog.exec", new=open_dialog,
        ):
            self.nav.actions["map"].click()
            self.assertEqual([field_id], opened)
            fetch.assert_not_called()
        self.assertEqual("Unsaved field-name edit", fields.name.text())
        self.assertEqual(before, self.snapshot())

    def test_parcel_card_map_uses_card_selection_instead_of_previous_fields_selection(self):
        previous = self.db.execute("INSERT INTO fields(name) VALUES('Previous Fields selection')")
        field_id = self._cadastral_only_field()
        self.nav.open("fields")
        fields = self.window.pages[2][1].resolved_page()
        for row in range(fields.table.rowCount()):
            if fields.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == previous:
                fields.load_selected(row, 0)
        self.nav.context_action("field_profile")
        card = self.window.pages[self.nav.targets["field_profile"].page][1].resolved_page()
        card.field.setCurrentIndex(card.field.findData(field_id))
        before = self.snapshot()
        opened = []

        def open_dialog(dialog):
            result = self._assert_cadastral_map(dialog, field_id)
            opened.append(dialog.field_id)
            return result

        with patch("app.gis.kaek_provider.NorthAegeanProvider.fetch") as fetch, patch(
            "app.gis.dialog.ParcelMapDialog.exec", new=open_dialog,
        ):
            self.nav.actions["map"].click()
            self.assertEqual([field_id], opened)
            fetch.assert_not_called()
        self.assertEqual(field_id, fields.selected_field_id)
        self.assertEqual("Synthetic cadastral-only field", fields.name.text())
        self.assertEqual(before, self.snapshot())

    def test_calendar_and_history_scroll_content_and_export_point_font(self):
        from PySide6.QtWidgets import QScrollArea
        self.window.resize(950, 650)
        self.window.show()
        for key in ("calendar", "history"):
            self.nav.open(key)
            self.app.processEvents()
            page = self.window.pages[self.nav.targets[key].page][1].resolved_page()
            scroll = page.findChild(QScrollArea, "entryPageScroll")
            self.assertIsNotNone(scroll)
            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            self.assertTrue(scroll.isAncestorOf(page.table))
        self.nav.open("annual_report")
        button = self.window.pages[29][1].resolved_page().export_button
        button.ensurePolished()
        self.assertGreater(button.font().pointSizeF(), 0)

    def test_work_routes_preserve_locked_year_guards_and_database(self):
        self.nav.open("activity")
        self.nav.open("planting")
        self.nav.open("protection")
        self.db.execute("INSERT OR REPLACE INTO year_locks(year,is_locked,reason) VALUES(2027,1,'locked')")
        for key, method, module in (("activity", "save_activity", "activities"),
                ("planting", "save_record", "plantings"), ("protection", "save_record", "plant_protection")):
            self.nav.open(key)
            page = self.window.pages[self.nav.targets[key].page][1].resolved_page()
            before = self.snapshot()
            with patch(f"app.{module}.warn_locked_year") as warning:
                getattr(page, method)()
                warning.assert_called_once()
            self.assertEqual(before, self.snapshot())
