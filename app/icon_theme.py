from __future__ import annotations

import re
import weakref
from pathlib import Path

from shiboken6 import isValid

from PySide6.QtCore import QEvent, QObject, QSize, QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QLabel,
    QListWidget,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolBox,
    QTreeWidget,
)

# MASTIXA_ICON_PATCH: generated icon theme loader.
# v18: fine-tunes only the four requested icon sizes and keeps the pre-dark-mode icon behavior.
# IMPORTANT: QIcon objects are created lazily, only after QApplication exists.
_ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons" / "mastixa_menu"
_ICON_SIZE = QSize(34, 34)
_TAB_LIKE_ICON_SIZE = QSize(54, 54)
_TAB_ICON_SIZE = QSize(54, 54)
_TAB_MIN_HEIGHT = 72
_TITLE_ICON_SIZE = QSize(64, 64)
_TITLE_ICON_SIZE_LARGE = QSize(96, 96)
_TITLE_ICON_GAP = 16
_QT_MAX_SIZE = 16777215

_ICON_ALIASES = {
    "irrigation_fertilization.png": (
        "Άρδευση & Λίπανση", "Άρδευση / Λίπανση", "Άρδευση-Λίπανση",
        "Άρδευση Λίπανση", "Άρδευση", "Λίπανση", "Irrigation & Fertilization",
    ),
    # More specific warehouse child category first; longest normalized match wins.
    "warehouse_supplies.png": (
        "Αποθήκη Εφόδια", "Αποθήκη & Εφόδια", "Αποθήκη / Εφόδια",
        "Εφόδια Αποθήκης", "Αποθήκη Εφοδίων", "Inventory & Supplies",
    ),
    "warehouse.png": (
        "Αποθήκη", "Αποθήκη Μέσα", "Αποθήκη & Αξία Stock", "Αποθήκη και Αξία Stock", "Inventory", "Inventory & Stock Value",
    ),
    # Finance icon remains ONLY for the parent Οικονομικά category.
    "finance.png": ("Οικονομικά", "Finances"),
    # Έσοδα and Έξοδα are separate categories with their own approved icons.
    "income.png": ("Έσοδα", "Έσοδο", "Income"),
    "expenses.png": ("Έξοδα", "Έξοδο", "Expenses"),
    "sales.png": (
        "Πωλήσεις", "Πωλήσεις Παραγωγής", "Πωλήσεις παραγωγής", "Sales", "Production Sales",
    ),
    "plant_protection.png": (
        "Φυτοπροστασία",
        "Ημερολόγιο Προστασίας",
        "Ημερολόγιο Φυτοπροστασίας",
        "Ημερολόγιο φυτοπροστασίας",
        "Plant Protection",
    ),
    "suppliers_buyers.png": (
        "Προμηθευτές & Αγοραστές", "Προμηθευτές και Αγοραστές",
        "Προμηθευτές / Αγοραστές", "Προμηθευτές Αγοραστές",
        "Προμηθευτές-Αγοραστές",
        "Suppliers & Buyers",
    ),
    "invoice_documents.png": (
        "Έγγραφα Τιμολογίων", "Έγγραφα & Τιμολόγια", "Έγγραφα και Τιμολόγια",
        "Τιμολόγια / Έγγραφα", "Τιμολόγια Έγγραφα", "Τιμολόγια", "Invoice Documents",
    ),
    "partners.png": (
        "Συνεργάτες", "Συνεργάτες Έγγραφα", "Συνεργάτες & Έγγραφα", "Partners", "Partners & Documents",
    ),
    "machinery_maintenance.png": (
        "Μηχανήματα Συντήρηση", "Μηχανήματα & Συντήρηση", "Μηχανήματα / Συντήρηση",
        "Συντήρηση Μηχανημάτων", "Μηχανήματα και Συντήρηση", "Machinery & Maintenance",
    ),
    "cultivation.png": ("Καλλιέργεια", "Cultivation"),
    "labor.png": ("Εργατικά", "Εργατικά & Προσωπικό", "Εργατικά και Προσωπικό", "Εργατικά Προσωπικό", "Labor", "Labor & Personnel"),
    "tree_planting.png": (
        "Φυτεύσεις Δέντρα", "Φυτεύσεις Δέντρων", "Φυτεύσεις", "Plantings & Trees",
    ),
    "production.png": ("Παραγωγή", "Παραγωγή ανά αγροτεμάχιο", "Production"),
}

# These page/navigation labels are deliberately exact-only. This prevents a
# category icon such as "Ρυθμίσεις" from leaking into action buttons such as
# "Αποθήκευση ρυθμίσεων" while still covering the tab and page-title wording.
_EXACT_ONLY_ICON_ALIASES = {
    "settings.png": ("Γενικές Ρυθμίσεις", "Ρυθμίσεις", "General Settings", "Settings"),
    "dashboard.png": ("Dashboard", "Fieltra"),
    "alerts.png": ("Ειδοποιήσεις", "Ειδοποιήσεις & Εκκρεμότητες", "Alerts", "Alerts & Pending Items"),
    "search.png": ("Αναζήτηση", "Γενική Αναζήτηση", "Search", "Global Search"),
    "calendar.png": ("Ημερολόγιο", "Ενιαίο Ημερολόγιο", "Calendar", "Unified Calendar"),
    "producer.png": ("Παραγωγός", "Στοιχεία παραγωγού", "Producer", "Producer details"),
    "fields.png": ("Αγροτεμάχια", "Fields"),
    "declaration.png": ("Δήλωση Καλλιέργειας", "Cultivation Declaration"),
    "package_preview.png": ("Προεπισκόπηση Πακέτου", "Κέντρο Αποστολής", "Package Preview"),
    "reports.png": ("Αναφορές", "Αναφορές & Στατιστικά", "Αναφορές & Έλεγχος", "Reports", "Reports & Checks"),
    "field_profile.png": ("Καρτέλα Αγροτεμαχίου", "Field Profile"),
    "products.png": ("Διαχείριση Προϊόντων", "Προϊόντα", "Product Management", "Products"),
    "data_quality.png": (
        "Έλεγχος Δεδομένων", "Data Check", "Data Checks", "Checks Data",
    ),
    "annual_report.png": (
        "Ετήσια Αναφορά", "Ετήσια Αναφορά Εκμετάλλευσης",
        "Annual Report", "Annual Farm Report",
    ),
    "field_costs.png": (
        "Κόστη ανά Αγροτεμάχιο", "Costs by Field",
    ),
    "year_lock.png": ("Κλείδωμα Έτους", "Year Lock"),
}


def _norm(text: str) -> str:
    text = (text or "").casefold()
    text = text.replace("&", " ").replace("/", " ").replace("-", " ")
    text = re.sub(r"[^\w\u0370-\u03ff\u1f00-\u1fff]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


# Store paths only. Do not create QIcon at module-import time.
_EXACT: dict[str, Path] = {}
_PARTIAL: list[tuple[str, Path]] = []
for filename, aliases in _ICON_ALIASES.items():
    path = _ICON_DIR / filename
    for alias in aliases:
        key = _norm(alias)
        _EXACT[key] = path
        _PARTIAL.append((key, path))

for filename, aliases in _EXACT_ONLY_ICON_ALIASES.items():
    path = _ICON_DIR / filename
    for alias in aliases:
        _EXACT[_norm(alias)] = path

# Longest match wins, so "παραγωγή ανά αγροτεμάχιο" wins over "παραγωγή".
_PARTIAL.sort(key=lambda pair: len(pair[0]), reverse=True)
_ICON_CACHE: dict[Path, QIcon] = {}

_LARGE_TITLE_ICON_FILES = {
    "irrigation_fertilization.png",
    "plant_protection.png",
    "labor.png",
    "suppliers_buyers.png",
    "invoice_documents.png",
    "income.png",
    "expenses.png",
    "sales.png",
    "warehouse_supplies.png",
    "machinery_maintenance.png",
}

_CUSTOM_TITLE_ICON_SIZES = {
    "tree_planting.png": QSize(76, 76),
    "irrigation_fertilization.png": QSize(104, 104),
    "production.png": QSize(72, 72),
    "sales.png": QSize(90, 90),
}



def _path_for_text(text: str) -> Path | None:
    key = _norm(text)
    if not key:
        return None
    exact = _EXACT.get(key)
    if exact is not None:
        return exact

    # Handles labels such as "Αποθήκη Μέσα" / "Συνεργάτες Έγγραφα" and
    # labels with extra words injected by the current UI version.
    for alias, path in _PARTIAL:
        if key.startswith(alias + " ") or key.endswith(" " + alias) or (" " + alias + " ") in (" " + key + " "):
            return path
    return None


def _icon_for_text(text: str) -> QIcon | None:
    path = _path_for_text(text)
    if path is None or not path.exists():
        return None
    icon = _ICON_CACHE.get(path)
    if icon is None:
        icon = QIcon(str(path))
        if icon.isNull():
            return None
        _ICON_CACHE[path] = icon
    return icon


def _apply_tree_item(item) -> int:
    changed = 0
    icon = _icon_for_text(item.text(0))
    if icon is not None:
        item.setIcon(0, icon)
        changed += 1
    for i in range(item.childCount()):
        changed += _apply_tree_item(item.child(i))
    return changed



def _apply_page_title_icons(root) -> int:
    """Show the matching 3D icon to the left of each page title.

    v11 explicitly removes fixed-height clipping from page-title labels.
    Some Fieltra pages constrain QLabel#pageTitle to the text height;
    in that case changing only the pixmap size has no visible effect because
    the child icon is clipped by the title label.  The listed categories use
    96x96 icons; existing categories keep the previous 64x64 size.
    """
    changed = 0
    protection_calendar_titles = {
        _norm("Ημερολόγιο Προστασίας"),
        _norm("Ημερολόγιο Φυτοπροστασίας"),
    }

    for label in root.findChildren(QLabel):
        is_page_title = label.objectName() == "pageTitle"
        is_protection_calendar_title = _norm(label.text()) in protection_calendar_titles
        if not (is_page_title or is_protection_calendar_title):
            continue

        path = _path_for_text(label.text())
        icon = _icon_for_text(label.text())
        icon_label = getattr(label, "_mastixa_title_icon_label", None)

        if icon is None or path is None:
            if icon_label is not None:
                icon_label.hide()
                original = getattr(label, "_mastixa_title_original_margins", None)
                if original is not None:
                    label.setContentsMargins(
                        original.left(), original.top(), original.right(), original.bottom()
                    )
            continue

        icon_size = _CUSTOM_TITLE_ICON_SIZES.get(
            path.name,
            _TITLE_ICON_SIZE_LARGE
            if path.name in _LARGE_TITLE_ICON_FILES
            else _TITLE_ICON_SIZE,
        )

        if not hasattr(label, "_mastixa_title_original_margins"):
            label._mastixa_title_original_margins = label.contentsMargins()

        original = label._mastixa_title_original_margins

        # Critical v11 fix: undo any fixed-height / maximum-height clipping.
        # setMinimumHeight() alone cannot enlarge a QLabel that previously
        # received setFixedHeight(), because maximumHeight remains small.
        label.setMaximumHeight(_QT_MAX_SIZE)
        label.setMinimumHeight(icon_size.height() + 8)

        left_pad = original.left() + icon_size.width() + _TITLE_ICON_GAP
        label.setContentsMargins(left_pad, original.top(), original.right(), original.bottom())

        if icon_label is None:
            icon_label = QLabel(label)
            icon_label.setObjectName("mastixaPageTitleIcon")
            icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label._mastixa_title_icon_label = icon_label

        icon_label.setMaximumSize(_QT_MAX_SIZE, _QT_MAX_SIZE)
        icon_label.setMinimumSize(0, 0)
        icon_label.setFixedSize(icon_size)
        icon_label.setPixmap(icon.pixmap(icon_size))
        x = original.left()
        y = max(0, (label.height() - icon_size.height()) // 2)
        icon_label.move(x, y)
        icon_label.show()
        icon_label.raise_()
        changed += 1

    return changed

def _apply_icon_theme_impl(root) -> int:
    """Apply visual icons only. Never changes data, DB, navigation, or page logic."""
    changed = 0

    # Large icon next to the title of the page that is currently/openly rendered.
    changed += _apply_page_title_icons(root)

    # Buttons / tool buttons / radio-like navigation items.
    for button in root.findChildren(QAbstractButton):
        if button.property("mastixaPresentationIcon"):
            continue
        icon = _icon_for_text(button.text())
        if icon is not None:
            if button.icon().cacheKey() != icon.cacheKey():
                button.setIcon(icon)
            # The current Fieltra renders the upper navigation tabs as
            # QAbstractButton-derived widgets. Give those icon-bearing category
            # controls the same larger visual weight as the main categories.
            # v11: remove fixed-height clipping before enlarging the icon.
            button.setMaximumHeight(_QT_MAX_SIZE)
            button.setIconSize(_TAB_LIKE_ICON_SIZE)
            button.setMinimumHeight(_TAB_MIN_HEIGHT)
            changed += 1

    # List-based navigation.
    for widget in root.findChildren(QListWidget):
        if widget.objectName() == "categoryList":
            # The left sidebar is intentionally text-only. Clear any icon that
            # may have been assigned by an earlier theme pass and never add
            # category icons there.
            for i in range(widget.count()):
                if not widget.item(i).icon().isNull():
                    widget.item(i).setIcon(QIcon())
            continue
        widget.setIconSize(_ICON_SIZE)
        for i in range(widget.count()):
            item = widget.item(i)
            icon = _icon_for_text(item.text())
            if icon is not None:
                if item.icon().cacheKey() != icon.cacheKey():
                    item.setIcon(icon)
                changed += 1

    # Trees.
    for tree in root.findChildren(QTreeWidget):
        tree.setIconSize(_ICON_SIZE)
        for i in range(tree.topLevelItemCount()):
            changed += _apply_tree_item(tree.topLevelItem(i))

    # Standard tab widgets.
    for tabs in root.findChildren(QTabWidget):
        if tabs.property("mastixaHiddenNavigation"):
            continue
        tabs.setIconSize(_TAB_ICON_SIZE)
        tabs.setMaximumHeight(_QT_MAX_SIZE)
        tabs.tabBar().setMaximumHeight(_QT_MAX_SIZE)
        tabs.tabBar().setIconSize(_TAB_ICON_SIZE)
        tabs.tabBar().setMinimumHeight(_TAB_MIN_HEIGHT)
        for i in range(tabs.count()):
            icon = _icon_for_text(tabs.tabText(i))
            if icon is not None:
                if tabs.tabIcon(i).cacheKey() != icon.cacheKey():
                    tabs.setTabIcon(i, icon)
                changed += 1

    # Direct QTabBar support is important because the current Fieltra
    # uses tab-like navigation that can be populated/wrapped dynamically.
    for bar in root.findChildren(QTabBar):
        if bar.parent() is not None and bar.parent().property("mastixaHiddenNavigation"):
            continue
        bar.setMaximumHeight(_QT_MAX_SIZE)
        bar.setIconSize(_TAB_ICON_SIZE)
        bar.setMinimumHeight(_TAB_MIN_HEIGHT)
        for i in range(bar.count()):
            icon = _icon_for_text(bar.tabText(i))
            if icon is not None:
                if bar.tabIcon(i).cacheKey() != icon.cacheKey():
                    bar.setTabIcon(i, icon)
                changed += 1

    for toolbox in root.findChildren(QToolBox):
        for i in range(toolbox.count()):
            icon = _icon_for_text(toolbox.itemText(i))
            if icon is not None:
                if toolbox.itemIcon(i).cacheKey() != icon.cacheKey():
                    toolbox.setItemIcon(i, icon)
                changed += 1

    for action in root.findChildren(QAction):
        icon = _icon_for_text(action.text())
        if icon is not None:
            if action.icon().cacheKey() != icon.cacheKey():
                action.setIcon(icon)
            changed += 1

    return changed


def _is_alive(root) -> bool:
    try:
        return root is not None and isValid(root)
    except RuntimeError:
        return False


def apply_icon_theme(root) -> int:
    """Safely ignore delayed callbacks for a window already replaced."""
    if not _is_alive(root):
        return 0
    try:
        return _apply_icon_theme_impl(root)
    except RuntimeError:
        # Live profile switching deletes the previous MainWindow while older
        # icon refresh timers may still be queued. Visual refreshes must never
        # keep or access an already deleted C++ object.
        return 0


class _LazyIconFilter(QObject):
    """Keep the title icons deterministic during startup and lazy page creation.

    v5 watched only the MainWindow itself. Child widgets deeper in the tree can be
    shown/polished/resized after the first startup pass, which is why a title icon
    could be missing until the user changed tabs. v6 installs this filter on the
    QApplication, so late events from every descendant are observed.
    """

    _WATCHED_EVENTS = {
        QEvent.Type.ChildAdded,
        QEvent.Type.Show,
        QEvent.Type.Polish,
        QEvent.Type.LayoutRequest,
        QEvent.Type.Resize,
        QEvent.Type.WindowActivate,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.FocusIn,
    }

    def __init__(self, root) -> None:
        super().__init__(root)
        self.root = root
        self._pending = False

    def _belongs_to_root(self, obj) -> bool:
        if not _is_alive(self.root):
            return False
        # QApplication events have no widget-parent chain; allow them because
        # WindowActivate/Polish during startup should refresh the active page.
        if obj is self.root or obj is QApplication.instance():
            return True
        try:
            current = obj
            while current is not None:
                if current is self.root:
                    return True
                current = current.parent()
        except Exception:
            return False
        return False

    def _schedule(self, delay: int = 0) -> None:
        if self._pending:
            return
        self._pending = True

        def run() -> None:
            self._pending = False
            # The window may already be closing. Guarding here keeps this visual
            # helper from ever affecting application shutdown.
            try:
                apply_icon_theme(self.root)
            except RuntimeError:
                pass

        QTimer.singleShot(delay, run)

    def eventFilter(self, obj, event):
        if event.type() in self._WATCHED_EVENTS and self._belongs_to_root(obj):
            # Defer until Qt has finished the current show/layout/polish operation.
            # Mouse/focus events also cover dynamically-created tab-like controls
            # that did not exist yet when install_icon_theme() first ran.
            self._schedule(0)
            if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.FocusIn):
                root_ref = weakref.ref(self.root)
                QTimer.singleShot(120, lambda ref=root_ref: _apply_weak(ref))
        return False


def _apply_weak(root_ref) -> None:
    root = root_ref()
    if _is_alive(root):
        apply_icon_theme(root)


def _schedule_apply(root, delay: int = 0) -> None:
    root_ref = weakref.ref(root)
    QTimer.singleShot(delay, lambda ref=root_ref: _apply_weak(ref))


def install_icon_theme(root) -> None:
    # Apply immediately, then at several event-loop points. The extra startup
    # passes are cheap (visual-only) and remove timing differences between pages.
    apply_icon_theme(root)
    for delay in (0, 50, 150, 350, 750, 1500, 3000, 5000, 8000):
        _schedule_apply(root, delay)

    # Keep a strong reference for the whole window lifetime. Install globally so
    # Show/Polish/Layout/Resize events from nested/lazy page widgets are observed.
    filt = _LazyIconFilter(root)
    root._mastixa_icon_filter = filt
    app = QApplication.instance()
    if app is not None:
        app.installEventFilter(filt)
    else:
        root.installEventFilter(filt)

    # Re-apply after navigation changes, because several current pages are built lazily.
    for stack in root.findChildren(QStackedWidget):
        stack.currentChanged.connect(lambda _i, r=root: _schedule_apply(r, 0))
        stack.currentChanged.connect(lambda _i, r=root: _schedule_apply(r, 120))

    for tabs in root.findChildren(QTabWidget):
        tabs.currentChanged.connect(lambda _i, r=root: _schedule_apply(r, 0))
        tabs.currentChanged.connect(lambda _i, r=root: _schedule_apply(r, 120))

    for toolbox in root.findChildren(QToolBox):
        toolbox.currentChanged.connect(lambda _i, r=root: _schedule_apply(r, 0))

    for lst in root.findChildren(QListWidget):
        lst.currentRowChanged.connect(lambda _i, r=root: _schedule_apply(r, 0))
        lst.currentRowChanged.connect(lambda _i, r=root: _schedule_apply(r, 120))

    for button in root.findChildren(QAbstractButton):
        button.clicked.connect(lambda _checked=False, r=root: _schedule_apply(r, 80))
