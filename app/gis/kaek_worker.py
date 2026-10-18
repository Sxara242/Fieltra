"""One background lookup per profile; Qt-thread persistence and presentation."""
import threading

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtNetwork import QNetworkInformation

from .kaek_lookup import LookupStore, StaleLookup, LookupConflict
from .kaek_provider import NorthAegeanProvider, ProviderFailure

STATUS_TEXT = {
    "pending": "Σε αναμονή",
    "retrieving": "Ανάκτηση",
    "retrieved": "Ανακτήθηκε",
    "temporary_failure": "Προσωρινή αποτυχία · αυτόματη επανάληψη",
    "unavailable": "Μη διαθέσιμο / μη υποστηριζόμενο",
}
REASON_TEXT = {
    "unsupported_region": "Επαληθευμένη κάλυψη: μόνο Βόρειο Αιγαίο (πρόθεμα ΚΑΕΚ 33, 43, 51).",
    "not_in_snapshot": "Ο ΚΑΕΚ δεν βρέθηκε στο διαθέσιμο κτηματολογικό στιγμιότυπο.",
    "provider_unavailable": "Δεν υπάρχει επαληθευμένος πάροχος για αυτό το αίτημα.",
    "retry_limit": "Παρατεταμένη απουσία σύνδεσης · η αυτόματη ανάκτηση θα συνεχιστεί.",
    "not_in_cached_snapshot": "Δεν βρέθηκε στο παλιό τοπικό στιγμιότυπο · αναμονή ενημέρωσης με σύνδεση.",
}


class LookupController(QObject):
    changed = Signal(int)
    _completed = Signal(object, object)

    def __init__(self, db, provider, parent=None, clock=None):
        super().__init__(parent)
        self.store = LookupStore(db, clock)
        self.provider = provider
        self.active = None
        self.stopped = False
        self.last_error = ""
        self.timer = QTimer(self)
        self.timer.setInterval(15_000)
        self.timer.timeout.connect(self.tick)
        self._completed.connect(self._finish, Qt.ConnectionType.QueuedConnection)
        self.timer.start()
        # Passive OS reachability only: no probe URL, listener, discovery or sync.
        QNetworkInformation.loadDefaultBackend()
        self.network_info = QNetworkInformation.instance()
        self.reachability = self.network_info.reachability() if self.network_info else None
        if self.network_info:
            self.network_info.reachabilityChanged.connect(self._reachability_changed)
        QTimer.singleShot(0, self.tick)  # Resume persistent jobs after restart.

    def _reachability_changed(self, state):
        previous, self.reachability = self.reachability, state
        if (not self.stopped and state == QNetworkInformation.Reachability.Online
                and previous != QNetworkInformation.Reachability.Online):
            try:
                self.store.connectivity_restored()
                QTimer.singleShot(0, self.tick)
            except Exception:
                self.last_error = "Δεν ήταν δυνατή η ενημέρωση της ουράς ΚΑΕΚ."

    def schedule(self, field_id):
        try:
            self.store.enqueue(field_id, self.provider)
            self.last_error = ""
        except Exception:
            self.last_error = "Το αγροτεμάχιο αποθηκεύτηκε, αλλά η ουρά ΚΑΕΚ δεν ενημερώθηκε."
        self.changed.emit(field_id)
        QTimer.singleShot(0, self.tick)

    def retry(self, field_id):
        try:
            self.store.retry(field_id, self.provider)
            self.last_error = ""
        except Exception:
            self.last_error = "Δεν ήταν δυνατή η ενημέρωση της ουράς ΚΑΕΚ."
        self.changed.emit(field_id)
        QTimer.singleShot(0, self.tick)

    def stop(self):
        self.stopped = True
        self.timer.stop()

    @Slot()
    def tick(self):
        if self.stopped or self.active is not None or self.provider is None:
            return
        try:
            request = self.store.claim(self.provider)
        except Exception:
            self.last_error = "Δεν ήταν δυνατή η ενημέρωση της ουράς ΚΑΕΚ."
            self.changed.emit(0)
            return
        if request is None:
            return
        # The worker never writes the application DB or touches widgets. Daemon
        # shutdown leaves a recoverable lease, without blocking application exit.
        self.active = threading.Thread(target=self._run, args=(request,), daemon=True)
        self.active.start()
        self.changed.emit(0)

    def _run(self, request):
        try:
            outcome = self.provider.fetch(request)
            cache_info = getattr(self.provider, 'cache_info', lambda: {})()
            outcome = (outcome, cache_info)
        except ProviderFailure as error:
            outcome = error
        except Exception:
            outcome = ProviderFailure("invalid_provider_response")
        try:
            self._completed.emit(request, outcome)
        except RuntimeError:
            pass  # Controller was destroyed; the persisted lease will recover.

    @Slot(object, object)
    def _finish(self, request, outcome):
        self.active = None
        if self.stopped:
            return
        try:
            if isinstance(outcome, ProviderFailure):
                self.store.fail(request, outcome.reason, outcome.temporary)
            else:
                payload, snapshot = outcome if isinstance(outcome, tuple) else (outcome, None)
                self.store.complete(payload, self.provider, snapshot=snapshot)
            self.last_error = ""
        except (StaleLookup, LookupConflict):
            # Ignore an obsolete attempt; reject a malformed current response
            # without leaving it stuck Retrieving until its crash lease expires.
            self.store.fail(request, "stale_or_mismatched_response")
        except Exception:
            try:
                self.store.fail(request, "invalid_provider_response")
            except Exception:
                self.last_error = "Δεν ήταν δυνατή η ενημέρωση της ουράς ΚΑΕΚ."
        self.changed.emit(0)
        QTimer.singleShot(0, self.tick)


def controller_for(db, parent):
    controller = getattr(db, "_kaek_lookup_controller", None)
    if controller is None:
        controller = LookupController(db, NorthAegeanProvider(db.path.parent / "kaek-cache"), parent)
        db._kaek_lookup_controller = controller
    return controller
