"""Small reusable user-confirmed locality editor; no network or automatic writes."""
from html import escape
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QGroupBox, QDialog,
                              QLabel, QLineEdit, QPushButton, QVBoxLayout,QSizePolicy)

from ..localized_messages import _text
from .kaek_lookup import StaleLookup
from .toponyms import ToponymStore, gazetteer


class ToponymWidget(QGroupBox):
    changed = Signal()

    def __init__(self, db, field_id, parent=None):
        super().__init__(parent)
        self.db, self.field_id = db, field_id
        self.store = ToponymStore(db)
        self.context = None
        self.candidates = []
        self._candidate = {}
        self._dirty = False
        self._editing = False
        self.setProperty("mastixaI18nSkipText", True)
        layout = QVBoxLayout(self)
        self.suggested_label = QLabel()
        self.suggested_label.setProperty('mastixaI18nSkipText',True)
        layout.addWidget(self.suggested_label)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setProperty("mastixaI18nSkipText", True)
        self.suggestions = QComboBox()
        self.suggestions.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.suggestions.setMinimumContentsLength(12)
        self.suggestions.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.suggestions.setProperty("mastixaI18nSkipItems", True)
        self.suggestions.currentIndexChanged.connect(self._select)
        layout.addWidget(self.suggestions)
        self.name = QLineEdit()
        self.name.setMaxLength(200)
        self.name.setProperty("mastixaI18nSkipText", True)
        self.name.textEdited.connect(self._edited)
        layout.addWidget(self.name)
        row = QVBoxLayout()
        layout.addLayout(row)
        self.confirm = QPushButton()
        self.edit = QPushButton()
        self.clear = QPushButton()
        self.reject = self.clear  # Preserve callers of the existing clear/reject action.
        for button in (self.confirm, self.edit, self.clear):
            button.setProperty("mastixaI18nSkipText", True)
            row.addWidget(button)
        self.confirm.clicked.connect(lambda: self._save("confirmed"))
        self.edit.clicked.connect(self._edit)
        self.clear.clicked.connect(self._clear)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setProperty("mastixaI18nSkipText", True)
        layout.addWidget(self.status)
        layout.addWidget(self.notice)
        self.attribution = QLabel()
        self.attribution.setTextFormat(Qt.TextFormat.RichText)
        self.attribution.setWordWrap(True)
        self.attribution.setProperty("mastixaI18nSkipText", True)
        self.attribution.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.attribution.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.attribution)
        self.attribution.linkActivated.connect(self.show_sources)
        for label in (self.notice,self.status,self.attribution):
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        controller = getattr(QApplication.instance(), "_mastixa_language_controller", None)
        if controller:
            controller.language_changed.connect(self.refresh)
        self.refresh()

    def _edited(self, *_):
        self._dirty = True

    def _edit(self):
        self._editing = True
        self.refresh()
        self.name.setFocus();self.name.selectAll()

    def _clear(self):
        decision = self.store.load(self.field_id)['decision']
        self._save('unspecified' if decision == 'confirmed' else 'rejected')

    def show_sources(self, *_):
        dialog=QDialog(self);dialog.setWindowTitle(_text('Πηγές / Άδειες'))
        layout=QVBoxLayout(dialog)
        metadata=self._candidate
        if not metadata:
            try:metadata=gazetteer().metadata
            except (OSError,ValueError,KeyError):metadata={}
        original_credit=escape(metadata.get('attribution',''))
        original_source=escape(metadata.get('source','https://www.geonames.org/'),quote=True)
        label=QLabel(_text('GeoNames · CC BY 4.0 · τοπικό φιλτραρισμένο ευρετήριο · οι θέσεις είναι σημεία, όχι όρια τοπωνυμίων.')
            + '<br><a href="https://www.geonames.org/">GeoNames</a> · '
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a><br>'
            + _text('Τροποποιήσεις: φιλτράρισμα ελληνικών τοπωνυμίων και τοπική κατάταξη προτάσεων. Οι επιβεβαιωμένες ονομασίες είναι αλλαγές του χρήστη.')
            + '<br>'+original_credit+'<br><a href="'+original_source+'">GeoNames</a>')
        label.setWordWrap(True);label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        label.setFocusPolicy(Qt.FocusPolicy.StrongFocus);layout.addWidget(label)
        close=QPushButton(_text('Κλείσιμο'));close.clicked.connect(dialog.accept);layout.addWidget(close)
        dialog.resize(460,240);dialog.exec()

    def _select(self, index):
        self._candidate = self.candidates[index] if 0 <= index < len(self.candidates) else {}
        if self._candidate:
            self.name.setText(self._candidate["name"])
        self._editing = True
        self.name.show();self.confirm.show();self.edit.hide()
        self.suggestions.setToolTip(self.suggestions.currentText())
        self._dirty = True

    def refresh(self, *_):
        previous_context = self.context
        draft, candidate = self.name.text(), self._candidate
        selected_id = candidate.get('geonames_id')
        self.context = self.store.context(self.field_id)
        same = previous_context is not None and self.context is not None and all(
            previous_context[key] == self.context[key] for key in ("field_uuid", "kaek", "result_hash"))
        keep_draft = self._dirty and same
        if not same:self._editing = False
        state = self.store.load(self.field_id)
        self.setTitle(_text("Τοπωνύμιο"))
        self.suggested_label.setText(_text('Προτεινόμενο τοπωνύμιο:'))
        self.suggestions.setAccessibleName(_text('Προτεινόμενο τοπωνύμιο:'))
        self.notice.setText(_text('Πρόταση ονομασίας· όχι επίσημος κτηματολογικός προσδιορισμός.'))
        self.name.setPlaceholderText(_text('Ονομασία τοπωνυμίου'))
        self.name.setAccessibleName(_text("Τοπωνύμιο που επιβεβαιώνει ο χρήστης"))
        self.confirm.setText(_text("Επιβεβαίωση"))
        self.edit.setText(_text('Επεξεργασία'))
        self.clear.setText(_text('Εκκαθάριση') if state['decision']=='confirmed' else _text('Απόρριψη'))
        self.candidates = []
        error = ""
        try:
            if self.context:
                self.candidates = gazetteer().suggestions(self.context["geometry"])
        except (OSError, ValueError, KeyError):
            error = _text('Δεν υπάρχουν προτάσεις. Γράψε ονομασία.')
        self.suggestions.blockSignals(True)
        self.suggestions.clear()
        for item in self.candidates:
            self.suggestions.addItem(_text('{name} — GeoNames', name=item['name']))
            index=self.suggestions.count()-1
            self.suggestions.setItemData(index,_text('{name} — GeoNames (~{distance:.0f} m) · {kind}',
                name=item['name'],distance=item['distance_m'],kind=item['feature']),Qt.ItemDataRole.ToolTipRole)
        selected_id = selected_id if keep_draft else state['candidate'].get('geonames_id')
        selected = next((i for i,item in enumerate(self.candidates) if item['geonames_id']==selected_id),0)
        if not self.candidates:self.suggestions.addItem(_text('Δεν υπάρχουν προτάσεις'))
        self.suggestions.setCurrentIndex(selected)
        self.suggestions.blockSignals(False)
        self.suggestions.setToolTip(self.suggestions.currentText())
        self._candidate = (candidate if keep_draft else state['candidate'] or
            (self.candidates[selected] if self.candidates else {}))
        initial_name=state['confirmed_name']
        if state['decision']=='unspecified' and self._candidate:initial_name=self._candidate['name']
        self.name.setText(draft if keep_draft else initial_name)
        editing = self._editing or keep_draft or state['decision'] != 'confirmed'
        self.name.setVisible(editing);self.confirm.setVisible(editing);self.edit.setVisible(not editing)
        self._dirty = keep_draft
        enabled = self.context is not None
        for control in (self.name, self.confirm, self.edit, self.clear):
            control.setEnabled(enabled)
        self.suggestions.setEnabled(enabled and bool(self.candidates))
        if not enabled:
            message = _text('Απαιτείται κτηματολογικό πολύγωνο.')
        elif state["decision"] == "confirmed":
            message = _text('Επιβεβαιωμένο τοπωνύμιο: {name}', name=state['confirmed_name'])
        elif state["decision"] == "rejected":
            message = _text('Η πρόταση απορρίφθηκε.')
        else:
            message = _text('Επιβεβαιωμένο τοπωνύμιο: Δεν έχει οριστεί')
        self.status.setText(error or message)
        self.attribution.setText('<a href="sources">GeoNames · CC BY 4.0 — '+_text('Πηγές / Άδειες')+'</a>')
        from ..ui_helpers import configure_combo_popup
        configure_combo_popup(self.suggestions)

    def _save(self, decision):
        try:
            self.store.save(self.field_id, self.context, decision=decision,
                            name=self.name.text(), candidate=self._candidate)
        except StaleLookup:
            self.refresh()
            self.status.setText(_text("Το αγροτεμάχιο ή ο ΚΑΕΚ άλλαξε. Έλεγξε ξανά πριν την επιβεβαίωση."))
            return
        except ValueError:
            self.status.setText(_text("Γράψε έγκυρη ονομασία έως 200 χαρακτήρες για επιβεβαίωση."))
            return
        self._dirty = False
        self._editing = False
        self.refresh()
        self.changed.emit()
