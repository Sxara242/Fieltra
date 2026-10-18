import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit
from unittest.mock import patch
from PySide6.QtCore import Qt
from app.database import Database
from app.gis.geometry import manual_coordinates
from app.gis.store import GeometryStore
from app.gis.dialog import ParcelMapDialog


class MapUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])

    def test_local_map_and_toggles_do_not_require_network(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Database(Path(directory)/'fixture.db')
            field=db.execute('INSERT INTO fields(name,kaek) VALUES(?,?)',('Synthetic parcel','TEST-001'))
            geometry=manual_coordinates('26 38\n26.001 38\n26.001 38.001\n26 38.001','EPSG:4326')
            store=GeometryStore(db);parcel=store.save(field,geometry)
            store.save_point(parcel,'tree','Synthetic tree','',26.0005,38.0005,5)
            dialog=ParcelMapDialog(db,field)
            try:
                dialog.show();self.qt.processEvents()
                self.assertEqual(4,len(dialog.map.markers))
                self.assertEqual(1,len(dialog.map.point_markers))
                dialog.map.set_track([[26,38,5,1000],[26.0005,38.0005,5,2000],[27,38,5,5000]],[0,2])
                self.assertEqual(1,len(dialog.map.track_items))
                self.assertEqual(3,dialog.map.track_items[0].path().elementCount())
                def inspect_sources(modal):
                    editor=modal.findChild(QPlainTextEdit)
                    self.assertTrue(editor.isReadOnly())
                    self.assertIn('EPSG:4326',editor.toPlainText())
                    return QDialog.DialogCode.Rejected
                with patch.object(QDialog,'exec',new=inspect_sources):
                    dialog.show_sources()
                self.assertEqual(Qt.TextFormat.PlainText,dialog.info.textFormat())
                self.assertFalse(dialog.map.pending)
                dialog.map.show_vertices(False)
                self.assertTrue(all(not item.isVisible() for item in dialog.map.markers))
                dialog.map.show_boundaries(False)
                self.assertFalse(dialog.map.boundaries[0].isVisible())
                dialog.map.show_vertices(True);dialog.map.show_boundaries(True)
                self.assertGreater(dialog.map.transform().m11(),0)
            finally:
                dialog.close();dialog.deleteLater();self.qt.processEvents()


if __name__=='__main__':unittest.main()
