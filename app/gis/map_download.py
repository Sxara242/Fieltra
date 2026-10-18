"""One cancellable regional download outside the GUI thread."""
from PySide6.QtCore import QThread,Signal
from .offline_maps import extract_chios


class MapDownload(QThread):
    progress=Signal(int,int,int)
    completed=Signal(dict)
    failed=Signal(str)

    def __init__(self,destination,parent=None):
        super().__init__(parent);self.destination=destination

    def run(self):
        try:
            result=extract_chios(self.destination,progress=self.progress.emit,
                cancel=self.isInterruptionRequested)
            self.completed.emit(result)
        except InterruptedError:self.failed.emit('Η λήψη ακυρώθηκε / Download cancelled')
        except Exception as error:
            self.failed.emit(f'PMTiles: {type(error).__name__}: {error}')
