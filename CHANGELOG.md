# Fieltra 1.0.0 Stable

- First production identity: Fieltra — Farm Management, executable `Fieltra.exe`.
- Stable `1.0.0` / Windows `1.0.0.0` metadata and consistent application/Setup branding.
- New per-user installation and Fieltra data/preferences; no pre-release migration.
- Existing offline farm-management behavior, icon and dependency stack retained.
- AGPL-3.0-only and historical/third-party notices preserved.
- Final installer owner-accepted for Sandbox installation, startup and branding/version;
  source publication metadata records content matching and the closed launcher provenance result and matching source downloads.

---

Historical records and retained technical instructions follow. Earlier status statements
do not override the Fieltra v1.0.0 preparation status above.

# Public source preparation — 2026-10-09 (unpublished)

- First-party AGPL-3.0-only scope and owner contribution-rights baseline recorded;
  inherited third-party license texts and EPSG/PROJ obligations retained.
- Public installation/development/release-status documentation and hosted Windows/
  Android verification prepared; regular CI creates no installers or artifacts.
- Local paths and signed public-download URLs sanitized; source privacy and
  secret checks added. Private history and existing local work preserved.
- Current source targets Windows rc.2; rc.1 owner findings require the new
  candidate. Android remains in development. See docs/RELEASE_STATUS.md.

---

# Changelog

## Windows rc.2 — external VC++ launch prerequisite, 2026-10-12 (not published)

- Next candidate installs without bundling, downloading or executing Microsoft
  Visual C++ Redistributable. x64 >=14.51.36247.0 remains required to run.
- Small CRT-independent native launcher checks the prerequisite before Python/Qt
  and offers a Greek Microsoft-download/Recheck/Cancel dialog when needed.
- Start Menu, Desktop and post-install opening share the root launcher; accepted
  frozen application bytes, AppId, profiles/preferences and uninstall policy stay
  intact. Runtime installation is a separate user action under Microsoft's terms.
- Installer compilation/file read-back and disposable Windows acceptance remain
  open; source validation is not public release approval. Old bundled artifacts
  and their unresolved Microsoft agreement issue remain historical evidence.

## Windows v1.0.0-rc.1 — preparation, 2026-10-07 (not published)

- AGPL-3.0-only application licensing, local legal links and contributor intake
  policy preserving future commercial-licensing intent.
- Windows RC version/channel metadata; unsigned internal candidate configuration.
- Offline staging JSON feed, strict RC/stable channel consistency and preserved
  failed-download retry / SHA-256 / explicit installation confirmation.
- Exclude unused Qt VirtualKeyboard module/plugin/resources; check output absence.
- Artwork provenance ledger and third-party license text collection.
- RC build remains blocked by exact native notices/source/redist closure and
  matching corresponding-source delivery. No installer or RC artifact built.
- Android parity is recorded for after Windows v1; Android is not version-bumped.

## v0.40.0-alpha.1 — 2026-08-29

- Προστέθηκε αναπαραγώγιμο Windows packaging με PyInstaller και Inno Setup.
- Η εγκατεστημένη εφαρμογή κρατά βάσεις, προφίλ, backups και logs στο
  `%LOCALAPPDATA%\MastixaManager`, εκτός του φακέλου προγράμματος και του
  installer.
- Προστέθηκαν application/installer icon, version metadata, packaged smoke
  test και SHA-256 checksum για το release artifact.
- Οι περιγραφές πωλήσεων και συνεργατών έγιναν ουδέτερες ως προς το προϊόν
  και οι νέες βάσεις δεν δημιουργούν πλέον αυτόματα προϊόν «Μαστίχα».

## v0.40.0-alpha — 2026-08-29

- Προστέθηκε ζωντανή επιλογή Ελληνικά/English χωρίς επανεκκίνηση.
- Η γλώσσα αποθηκεύεται ανεξάρτητα ανά προφίλ και μεταφέρεται με profile export/import.
- Προστέθηκε επιλογέας γλώσσας πριν από το login στην οθόνη προφίλ.
- Προστέθηκαν επεκτάσιμα JSON language packs με ασφαλές ελληνικό fallback.
- Μεταφράστηκαν πλοήγηση, σελίδες, controls, dialogs, tooltips και βασικά reports/exports.
- Στην αγγλική λειτουργία η μονάδα `στρέμμα` εμφανίζεται ως `decare`, με επεξήγηση `1 decare = 1,000 m²`.
- Διορθώθηκαν οι μικτές ελληνικές/αγγλικές ενδείξεις στις σελίδες Αγροτεμαχίων, Παραγωγής, Δήλωσης, Φυτοπροστασίας και Φυτεύσεων.
- Ολοκληρώθηκε δεύτερο πέρασμα αγγλικών σε Global Search, Άρδευση/Λίπανση, Συνεργάτες, Package Preview, Sales/Stock, Ετήσια Αναφορά και Κόστη ανά Αγροτεμάχιο, μαζί με τα δυναμικά μηνύματα και tooltips τους.
- Ολοκληρώθηκε τρίτο πέρασμα σε Labor, Income/Expenses, Production Sales, Reports, Year Lock, Products και Backups, συμπεριλαμβανομένων επιλογών και καταστάσεων πινάκων από τη βάση.
- Μεταφράστηκαν πλήρως οι προκαθορισμένες κατηγορίες και τα tooltips του Inventory, καθώς και τα κείμενα που ζωγραφίζονται απευθείας μέσα στα charts.
- Αντικαταστάθηκαν τα Qt fallback icons των Data Checks, Annual Report και Costs by Field με βελτιστοποιημένα icons της ίδιας navy/silver οικογένειας και βελτιώθηκε το tooltip υπολογισμού stock.
- Οι μεταφρασμένες επιλογές διατηρούν σταθερές τις εσωτερικές τιμές της βάσης.
- Προστέθηκε privacy-safe rotating application log με πρόσβαση από τις Ρυθμίσεις.
- Προστέθηκαν αυτοματοποιημένοι έλεγχοι live αλλαγής, profile persistence, exports και logs.
- Ο ενισχυμένος έλεγχος αγγλικών ολοκληρώνεται με μηδενικά κενά UI και dialogs.
- Τεκμηριώθηκε ότι το Tesseract OCR είναι προαιρετική εξωτερική εξάρτηση και δεν περιλαμβάνεται στο πακέτο.

## v0.39.0-alpha — 2026-08-28

- Προστέθηκαν ανεξάρτητα προφίλ με ξεχωριστές βάσεις και backups.
- Προστέθηκαν PIN, avatar/χρώμα, επιλογέας εκκίνησης και import/export προφίλ.
- Προστέθηκε πλήρες, αποδοτικό light/dark mode.
- Ολοκληρώθηκε το νέο σύστημα icons, με text-only αριστερό sidebar.
- Προστέθηκαν μητρώο προϊόντων και σχέσεις προϊόντων–αγροτεμαχίων.
- Διατηρήθηκε μόνο offline προεπισκόπηση πακέτων, χωρίς server ή συγχρονισμό.
- Βελτιώθηκαν backups, SQLite connection cleanup και σταθερότητα αλλαγής προφίλ.
- Διορθώθηκαν επιλογές δήλωσης, disabled controls και συμπαγής εμφάνιση έκτασης.
- Προστέθηκε εκτεταμένη αυτοματοποιημένη κάλυψη σταθερότητας και προφίλ.
- Αφαιρέθηκε εξαγόμενο CSV από το repository και ενισχύθηκαν οι privacy ignores.

## v0.2.0-alpha

- Added database package skeleton.
- Added schema_version and audit_log schema.
- Added migration infrastructure placeholder.
- Added backup helper.

## v0.1.0
- Δημιουργήθηκε η βασική εφαρμογή.
- Προστέθηκε SQLite βάση δεδομένων.
- Προστέθηκαν Dashboard, Παραγωγός, Αγροτεμάχια, Παραγωγή, Έσοδα και Έξοδα.
- Προστέθηκε χειροκίνητο backup της βάσης δεδομένων.
