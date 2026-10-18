"""Farm navigation over the existing stable page registry and lazy workflows.

The legacy tab containers remain page owners; only their navigation chrome is
hidden. This preserves extension indices, lazy loading and year-lock guards.
"""
from dataclasses import dataclass

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QToolButton, QTreeView, QVBoxLayout, QWidget

from .icon_theme import _icon_for_text
from .localized_messages import _text
from .navigation_view import NavigationTree


@dataclass(frozen=True)
class Destination:
    title: str
    page: int
    detail: str = ""


class BackupPanel(QWidget):
    def __init__(self, dashboard, navigate):
        super().__init__()
        self.dashboard = dashboard
        layout = QVBoxLayout(self)
        layout.addWidget(dashboard.safety_box)
        settings = QPushButton("Ρυθμίσεις αντιγράφων ασφαλείας")
        settings.clicked.connect(lambda: navigate("backup_settings"))
        layout.addWidget(settings)
        profiles = QPushButton("Προφίλ")
        profiles.clicked.connect(lambda: navigate("profiles"))
        layout.addWidget(profiles)
        layout.addStretch()

    def refresh(self):
        self.dashboard.backup_manager = self.dashboard._build_backup_manager()
        self.dashboard._refresh_backup_status()


class ReportsHub(QWidget):
    """Actions into the existing report implementations, without new calculations."""
    def __init__(self, navigate):
        super().__init__()
        from .ui_helpers import scrollable_entry_layout
        layout = scrollable_entry_layout(self)
        title = QLabel("Αναφορές")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.buttons = []
        for caption, route, icon_label in (("Επισκόπηση", "overview", "Dashboard"),
                ("Παραγωγή", "overview", "Παραγωγή"), ("Οικονομικά", "finance", "Έσοδα"),
                ("Πωλήσεις", "sales_report", "Πωλήσεις"), ("Χωράφια", "field_finance", "Αγροτεμάχια"),
                ("Αποθήκη", "inventory_report", "Αποθήκη"), ("Ετήσια Αναφορά", "annual_report", "Ετήσια Αναφορά")):
            button = QPushButton(caption)
            button.setProperty("mastixaPresentationIcon", True)
            button.setIcon(_icon_for_text(icon_label))
            button.setIconSize(QSize(32, 32))
            button.setMinimumHeight(56)
            button.setStyleSheet("QPushButton { text-align:left; padding:12px 18px; }")
            button.clicked.connect(lambda _checked=False, key=route: navigate(key))
            layout.addWidget(button)
            self.buttons.append(button)
        layout.addStretch()


class DesktopNavigation:
    def __init__(self, window):
        self.window = window
        self._opening = False
        self.items = {}
        self.targets = {}
        dashboard = window.pages[0][1]
        backup_index = len(window.pages)
        window.pages.append(("Αντίγραφα ασφαλείας", BackupPanel(dashboard, self.open)))
        # Appended only; all original page indices remain valid.
        window.navigation_categories[6][1].append(("Αντίγραφα ασφαλείας", backup_index))
        reports_index = len(window.pages)
        window.pages.append(("Αναφορές", ReportsHub(self.open)))
        window.navigation_categories[6][1].append(("Αναφορές", reports_index))
        self.tree = NavigationTree(window.sidebar)
        self.tree.setObjectName("farmNavigation")
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setIconSize(QSize(28, 28))
        self.tree.setIndentation(14)
        self.tree.setMouseTracking(True)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.model = QStandardItemModel(self.tree)
        self.tree.setModel(self.model)
        window.category_list.hide()
        window.sidebar.setFixedWidth(245)
        window.sidebar.layout().addWidget(self.tree)
        # One presentation header above the existing page container. A selector
        # changes the workflow type; independent utilities remain actions.
        container = QWidget(window)
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 0, 0)
        self.header = QWidget(container)
        self.header_layout = QHBoxLayout(self.header)
        self.selector_label = QLabel()
        self.selector = QComboBox()
        self.selector.setProperty("mastixaI18nSkipItems", True)
        self.header_layout.addWidget(self.selector_label)
        self.header_layout.addWidget(self.selector)
        self.header_layout.addStretch()
        self.field_tools = QWidget(self.header)
        field_tools_layout = QHBoxLayout(self.field_tools)
        field_tools_layout.setContentsMargins(0, 0, 0, 0)
        field_tools_layout.setSpacing(4)
        self.header_layout.addWidget(self.field_tools)
        self.actions = {}
        for key, caption in (("map", "Χάρτης"), ("field_profile", "Καρτέλα Αγροτεμαχίου"),
                ("plants", "Μεμονωμένα Φυτά / Δέντρα"), ("crop_program", "Πρόγραμμα Καλλιέργειας"),
                ("year_lock", "Κλείδωμα Έτους"), ("data_export", "Εξαγωγή Δεδομένων"),
                ("declaration", "Δήλωση Καλλιέργειας"), ("package", "Προεπισκόπηση Πακέτου"),
                ("sensors", "Αισθητήρες / API"), ("reports", "Επιστροφή στις Αναφορές"),
                ("settings", "Επιστροφή στις Ρυθμίσεις")):
            button = QPushButton(caption)
            button.clicked.connect(lambda _checked=False, route=key: self.context_action(route))
            if key in ("map", "field_profile", "plants"):
                button.setProperty("mastixaPresentationIcon", True)
                button.setIconSize(QSize(28, 28))
                button.setFixedHeight(50)
                field_tools_layout.addWidget(button)
            else:
                self.header_layout.addWidget(button)
            self.actions[key] = button
        self.tools = QToolButton()
        self.tools.setStyleSheet(
            f"QToolButton {{ font-size: {14 * 72 / window.logicalDpiY():g}pt; "
            "background: white; color: #26382F; border: 1px solid #C4CEC8; "
            "border-radius: 6px; padding: 10px 18px; font-weight:600; }"
            "QToolButton:hover { background: #F1F4F2; }")
        self.tools.setText("Περισσότερα εργαλεία")
        self.tools.setMinimumHeight(42)
        self.tools.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.tools)
        for key in ("year_lock", "data_export", "declaration", "package", "sensors"):
            action = menu.addAction(self.actions[key].text())
            action.triggered.connect(lambda _checked=False, route=key: self.open(route))
        self.tools.setMenu(menu)
        self.tools_panel = QWidget(self.header)
        tools_layout = QVBoxLayout(self.tools_panel)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(4)
        tools_layout.addWidget(self.tools)
        self.tools_description = QLabel("Κλείδωμα έτους, εξαγωγές και βοηθητικά εργαλεία.")
        self.tools_description.setObjectName("mutedLabel")
        self.tools_description.setWordWrap(True)
        tools_layout.addWidget(self.tools_description)
        self.header_layout.addWidget(self.tools_panel)
        window.tabs.parentWidget().layout().replaceWidget(window.tabs, container)
        content.addWidget(self.header)
        content.addWidget(window.tabs, 1)
        self.selector.currentIndexChanged.connect(self._type_changed)
        groups = [
            ("Αρχική", "Dashboard", []),
            ("Αγρόκτημα", "Αγροτεμάχια", [("fields", "Χωράφια", 2), ("products", "Προϊόντα", 30),
                ("inventory", "Αποθήκη", 13), ("producer", "Εκμετάλλευση", 1)]),
            ("Εργασίες", "Ημερολόγιο", [("activity", "Καταχώριση εργασίας", 12), ("calendar", "Πρόγραμμα εργασιών", 24),
                ("production", "Παραγωγή", 3), ("labor", "Εργάτες", 21), ("equipment", "Μηχανήματα", 16)]),
            ("Οικονομικά", "Έσοδα", [("revenue", "Έσοδα & Πωλήσεις", 26), ("expense", "Έξοδα", 5),
                ("finance", "Οικονομική εικόνα", 8), ("partners", "Συναλλασσόμενοι", 17), ("invoices", "Παραστατικά", 18)]),
            ("Αναφορές", "Αναφορές", []),
            ("Σύστημα", "Ρυθμίσεις", [("settings", "Ρυθμίσεις", 31), ("backup", "Backup & Profiles", backup_index),
                ("history", "Ιστορικό", 9), ("quality", "Έλεγχος Δεδομένων", 10), ("updates", "Ενημερώσεις", 31, "updates")]),
        ]
        # Extensions keep their original page instances, including existing gates.
        extensions = {"Πρόγραμμα Καλλιέργειας": (2, "crop_program"),
                      "Μεμονωμένα Φυτά / Δέντρα": (1, "plants"), "Αισθητήρες / API": (5, "sensors")}
        for index, (title, _page) in enumerate(window.pages):
            if title in extensions:
                _group, key = extensions[title]
                self.targets[key] = Destination(title, index)
        for title, icon_label, entries in groups:
            parent = QStandardItem(title)
            font = parent.font()
            font.setBold(True)
            parent.setFont(font)
            parent.setData(title, Qt.ItemDataRole.UserRole + 1)
            parent.setIcon(_icon_for_text(icon_label))
            self.model.appendRow(parent)
            if not entries:
                key, page = ("home", 0) if title == "Αρχική" else ("reports", reports_index)
                parent.setData(key, Qt.ItemDataRole.UserRole)
                self.items[key] = parent
                self.targets[key] = Destination(title, page)
            for entry in entries:
                key, label, page, *detail = entry
                item = QStandardItem(label)
                item.setData(key, Qt.ItemDataRole.UserRole)
                item.setData(label, Qt.ItemDataRole.UserRole + 1)
                parent.appendRow(item)
                self.items[key] = item
                if page >= 0:
                    self.targets[key] = Destination(label, page, detail[0] if detail else "")
        for key, label, page in (("sale", "Πώληση προϊόντος", 26), ("income", "Άλλο έσοδο", 4),
                ("planting", "Φυτεύσεις", 23), ("protection", "Φυτοπροστασία", 19), ("alerts", "Ειδοποιήσεις", 15),
                ("search", "Αναζήτηση", 22), ("overview", "Επισκόπηση", 8), ("sales_report", "Πωλήσεις", 27),
                ("field_finance", "Κόστη ανά Αγροτεμάχιο", 20), ("inventory_report", "Αποθήκη", 28),
                ("annual_report", "Ετήσια Αναφορά", 29), ("field_profile", "Καρτέλα Αγροτεμαχίου", 25),
                ("year_lock", "Κλείδωμα Έτους", 14), ("data_export", "Εξαγωγή Δεδομένων", 11),
                ("declaration", "Δήλωση Καλλιέργειας", 6), ("package", "Προεπισκόπηση Πακέτου", 7)):
            self.targets[key] = Destination(label, page)
        self.targets["profiles"] = Destination("Προφίλ", 31, "profiles")
        self.targets["map"] = Destination("Χάρτης", 2, "map")
        self.targets["backup_settings"] = Destination("Ρυθμίσεις αντιγράφων ασφαλείας", 31, "backup")
        self.tree.selectionModel().currentChanged.connect(self._selected)
        self.tree.clicked.connect(self._clicked)
        window.language.language_changed.connect(self.translate)
        self.translate()
        self.sync_current()

    def translate(self, *_args):
        def visit(item):
            title = _text(item.data(Qt.ItemDataRole.UserRole + 1))
            item.setText(title)
            item.setToolTip(title)
            for row in range(item.rowCount()):
                visit(item.child(row))
        for row in range(self.model.rowCount()):
            visit(self.model.item(row))
        self.refresh_header()

    def _type_changed(self):
        key = self.selector.currentData()
        if key in ("irrigation", "fertilization"):
            self.open("activity")
            page = self.window.pages[12][1].resolved_page()
            page.category.setCurrentIndex(page.category.findData(key))
            self.refresh_header()
        elif key:
            self.open(key)

    def context_action(self, key):
        field_id = None
        if key in ("field_profile", "plants"):
            fields = self.window.pages[2][1].resolved_page()
            field_id = fields.selected_field_id
        self.open(key)
        if field_id is not None:
            page = self.window.pages[self.targets[key].page][1].resolved_page()
            combo = page.field if key == "field_profile" else page.field_filter
            value = field_id if key == "field_profile" else str(field_id)
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)

    def refresh_header(self, *_args):
        index = self.window._current_page_index()
        self.selector.blockSignals(True)
        self.selector.clear()
        choices = []
        current = None
        if index in (12, 19, 23):
            self.selector_label.setText(_text("Είδος εργασίας"))
            choices = [("Πότισμα", "irrigation"), ("Λίπανση", "fertilization"),
                       ("Φύτευση", "planting"), ("Φυτοπροστασία", "protection"), ("Άλλο — μη διαθέσιμο", "other")]
            current = {19: "protection", 23: "planting"}.get(index)
            if index == 12 and self.window.pages[12][1].is_loaded:
                page = self.window.pages[12][1].resolved_page()
                current = page.category.currentData()
                if not getattr(page, "_work_header_connected", False):
                    page.category.currentIndexChanged.connect(self.refresh_header)
                    page._work_header_connected = True
                form = page.form_box.layout()
                if isinstance(form, QFormLayout):
                    form.setRowVisible(page.category, False)
        elif index in (4, 26):
            self.selector_label.setText(_text("Είδος εσόδου"))
            choices = [("Πώληση προϊόντος", "sale"), ("Άλλο έσοδο", "income")]
            current = "sale" if index == 26 else "income"
        for title, key in choices:
            self.selector.addItem(_text(title), key)
            if key == "other":
                item = self.selector.model().item(self.selector.count()-1)
                item.setEnabled(False)
                item.setToolTip(_text("Η γενική καταχώριση εργασίας θα προστεθεί σε ξεχωριστό βήμα."))
        self.selector.setCurrentIndex(self.selector.findData(current))
        self.selector.blockSignals(False)
        self.selector.setVisible(bool(choices))
        self.selector_label.setVisible(bool(choices))
        visible = set()
        if index in (2, 25) or index == self.targets.get("plants", Destination("", -1)).page:
            visible = {"map", "field_profile", "plants"}
        elif index == 24 or index == self.targets.get("crop_program", Destination("", -1)).page:
            visible = {"crop_program"}
        elif index == 31:
            visible = {"tools"}
        elif index in (8, 20, 27, 28, 29):
            visible = {"reports"}
        elif index in (6, 7, 11, 14, self.targets.get("sensors", Destination("", -1)).page):
            visible = {"settings"}
        for key, button in self.actions.items():
            button.setVisible(key in visible and key in self.targets)
        self.tools.setVisible("tools" in visible)
        self.tools_panel.setVisible("tools" in visible)
        self.field_tools.setVisible("map" in visible)
        self.header.setVisible(bool(choices or visible))

    def _selected(self, index, _previous):
        if self._opening:
            return
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        if item.hasChildren():
            self.tree.expand(index)
            self.tree.setCurrentIndex(item.child(0).index())
        else:
            self.open(item.data(Qt.ItemDataRole.UserRole))

    def _clicked(self, index):
        # Tool pages retain Settings as their sidebar owner. Clicking that
        # already-selected item must still open the Settings landing page.
        item = self.model.itemFromIndex(index)
        if (not self._opening and item is not None
                and item.data(Qt.ItemDataRole.UserRole) == "settings"
                and self.window._current_page_index() != self.targets["settings"].page):
            self.open("settings")

    def open(self, key):
        target = self.targets[key]
        map_field_id = None
        if target.detail == "map":
            source_index = self.window._current_page_index()
            source = self.window.pages[source_index][1]
            source = source.resolved_page() if hasattr(source, "resolved_page") else source
            if source_index == self.targets["field_profile"].page:
                map_field_id = source.field.currentData()
            else:
                map_field_id = getattr(source, "selected_field_id", None)
        self._opening = True
        try:
            self.window.change_page(target.page)
            page = self.window.pages[target.page][1]
            if target.detail:
                page = page.resolved_page() if hasattr(page, "resolved_page") else page
                if target.detail == "map":
                    if map_field_id is not None and page.selected_field_id != map_field_id:
                        for row in range(page.table.rowCount()):
                            item = page.table.item(row, 0)
                            if item is not None and item.data(Qt.ItemDataRole.UserRole) == map_field_id:
                                page.table.selectRow(row)
                                page.load_selected(row, 0)
                                break
                    if map_field_id is not None and page.selected_field_id == map_field_id:
                        page.open_map()
                        return
                    if not hasattr(page, "farm_map_hint"):
                        page.farm_map_hint = QLabel(_text("Επίλεξε χωράφι και πάτησε «Χάρτης αγροτεμαχίου»."), page)
                        page.farm_map_hint.setWordWrap(True)
                        page.layout().addWidget(page.farm_map_hint)
                    page.table.setFocus()
                    for scroll in page.findChildren(QScrollArea):
                        scroll.ensureWidgetVisible(page.table)
                elif target.detail == "profiles":
                    page.tabs.setCurrentIndex(0)
                    for scroll in page.findChildren(QScrollArea):
                        scroll.ensureWidgetVisible(page.profile_combo)
                    page.profile_combo.setFocus()
                elif target.detail == "backup":
                    page.tabs.setCurrentIndex(1)
                elif target.detail == "updates":
                    ensure_tab = getattr(page, "_ensure_settings_tab", None)
                    if ensure_tab is not None:
                        ensure_tab(3)
                    button = getattr(page, "_mastixa_check_updates_button", None)
                    if button is not None:
                        for i in range(page.tabs.count()):
                            if page.tabs.widget(i).isAncestorOf(button):
                                page.tabs.setCurrentIndex(i)
                                break
                        button.setFocus()
            item = self.items.get(key)
            if item:
                self.tree.setCurrentIndex(item.index())
                self.tree.scrollTo(item.index())
        finally:
            self._opening = False
            self.hide_legacy_chrome()
            self.refresh_header()
            self.sync_current()

    def hide_legacy_chrome(self):
        self.window.tabs.setProperty("mastixaHiddenNavigation", True)
        self.window.tabs.tabBar().hide()
        for tabs in self.window._recording_group_tabs + self.window._report_group_tabs:
            tabs.setProperty("mastixaHiddenNavigation", True)
            tabs.tabBar().hide()

    def sync_current(self):
        self.hide_legacy_chrome()
        if self._opening:
            return
        page = self.window._current_page_index()
        self.refresh_header()
        current = self.model.itemFromIndex(self.tree.currentIndex())
        key = current.data(Qt.ItemDataRole.UserRole) if current else None
        if key in self.targets and self.targets[key].page == page:
            return
        owners = {4: "revenue", 26: "revenue", 19: "activity", 23: "activity", 25: "fields",
                  20: "reports", 27: "reports", 28: "reports", 29: "reports", 6: "settings", 7: "settings", 11: "settings", 14: "settings"}
        for extension, owner in (("plants", "fields"), ("crop_program", "calendar"), ("sensors", "settings")):
            if extension in self.targets:
                owners[self.targets[extension].page] = owner
        owner = owners.get(page)
        if owner:
            self._opening = True
            self.tree.setCurrentIndex(self.items[owner].index())
            self.tree.scrollTo(self.items[owner].index())
            self._opening = False
            return
        for key, target in self.targets.items():
            if target.page == page and key in self.items:
                self._opening = True
                item = self.items[key]
                ancestor = item.parent()
                while ancestor:
                    self.tree.expand(ancestor.index())
                    ancestor = ancestor.parent()
                self.tree.setCurrentIndex(item.index())
                self._opening = False
                break

    def quick_entry(self, key):
        self.open(key)
        page = self.window.pages[self.targets[key].page][1]
        page = page.resolved_page() if hasattr(page, "resolved_page") else page
        # Do not erase an unsaved draft or an existing read-only selection.
        form = getattr(page, "form_box", None)
        if form:
            for scroll in page.findChildren(QScrollArea):
                scroll.ensureWidgetVisible(form)
            form.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            form.setFocus()


def install_desktop_navigation():
    from . import main_window
    from .farm_home import FarmHome
    current = main_window.MainWindow
    if getattr(current, "_farm_navigation_v1", False):
        return

    class FarmWindow(current):
        _farm_navigation_v1 = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.desktop_navigation = DesktopNavigation(self)
            dashboard = self.pages[0][1]
            self.farm_home = FarmHome(dashboard, self.desktop_navigation, self.profile_manager.active_profile.name)
            dashboard.farm_home = self.farm_home
            self.farm_home.refresh()
            self.language.apply_to(self)

        def _refresh_current_tab(self):
            if getattr(self, "_farm_navigating", False):
                return
            super()._refresh_current_tab()
            if hasattr(self, "desktop_navigation"):
                self.desktop_navigation.sync_current()

        def _presentation_token(self):
            # File revisions detect writes from every existing DB handle (also
            # transactions/import/restore), without changing persistence APIs.
            from pathlib import Path
            from PySide6.QtWidgets import QApplication
            path = Path(self.db.path)
            revisions = []
            for candidate in (path, Path(str(path) + "-wal")):
                try:
                    info = candidate.stat()
                    revisions.append((info.st_mtime_ns, info.st_size, info.st_ino))
                except FileNotFoundError:
                    revisions.append(None)
            app = QApplication.instance()
            return (str(path), tuple(revisions), QDate.currentDate().toJulianDay(),
                    *(app.property(name) for name in ("mastixaActiveWorkingYear", "mastixaEffectiveWorkingYear",
                                                      "mastixaCorrectionYear", "mastixaCorrectionReason")))

        def _tab_icon_for_page(self, page_index):
            if hasattr(self, "desktop_navigation"):
                # These tab bars are permanently hidden by this navigation.
                from PySide6.QtGui import QIcon
                return QIcon()
            return super()._tab_icon_for_page(page_index)

        def change_page(self, index):
            if not hasattr(self, "desktop_navigation"):
                return super().change_page(index)
            if not 0 <= index < len(self.pages):
                return
            self._farm_navigating = True
            try:
                # Legacy containers still own the pages, but their intermediate
                # tab signals must not refresh/construct transient destinations.
                super().change_page(index)
            finally:
                self._farm_navigating = False
            if not hasattr(self, "_farm_rendered_tokens"):
                self._farm_rendered_tokens = {}
            token = self._presentation_token()
            if self._farm_rendered_tokens.get(index) != token:
                self._refresh_current_tab()
                self._farm_rendered_tokens[index] = self._presentation_token()
            self.desktop_navigation.sync_current()

    main_window.MainWindow = FarmWindow
