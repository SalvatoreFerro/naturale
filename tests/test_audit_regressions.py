"""Independent verification cases: exercise the real file and stdin CLI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/naturale/scripts/text.py"
SPEC = importlib.util.spec_from_file_location("audit_verification", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class AuditVerificationTests(unittest.TestCase):
    def files(self, source, revision):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            s, r = base / "s.txt", base / "r.txt"
            s.write_text(source, encoding="utf-8")
            r.write_text(revision, encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--source", str(s),
                                     "--revision", str(r)], capture_output=True, encoding="utf-8", timeout=10)
            return result, json.loads(result.stdout)

    def test_contextual_number_words_and_equivalent_times(self):
        cases = [
            (1, "Sei libera domani?", "Hai tempo domani?", 0),
            (2, "Sei sicuro di voler annullare l'ordine?", "Vuoi davvero annullare l'ordine?", 0),
            (3, "Sei in ritardo?", "Stai arrivando?", 0),
            (4, "Ti mando uno schema riassuntivo.", "Ti mando lo schema riassuntivo.", 0),
            (5, "Mille grazie per l'aiuto.", "Grazie di cuore per l'aiuto.", 0),
            (6, "Grazie mille, a domani.", "Grazie, a domani.", 0),
            (7, "Siamo aperti dalle 9:30.", "Siamo aperti dalle 9.30.", 0),
            (8, "Consegna entro le 18:00.", "Consegna entro le 18.00.", 0),
            (9, "Ci sentiamo verso le 15:00.", "Ci sentiamo verso le 15.00.", 0),
            (10, "Ho sei giorni di ferie.", "Ho cinque giorni di ferie.", 1),
            (11, "Sei persone hanno confermato.", "Cinque persone hanno confermato.", 1),
            (12, "Sono passati sei mesi.", "Sono passati sette mesi.", 1),
            (13, "Ci vediamo alle sei.", "Ci vediamo alle sette.", 1),
            (14, "Manca uno dei documenti.", "Mancano due dei documenti.", 1),
            (15, "Abbiamo mille pezzi in magazzino.", "Abbiamo cento pezzi in magazzino.", 1),
            (16, "Uno dei tre preventivi è scaduto.", "Uno dei due preventivi è scaduto.", 1),
            (17, "Siamo aperti dalle 9:30.", "Siamo aperti dalle 10:30.", 1),
        ]
        for number, source, revision, expected in cases:
            with self.subTest(case=number):
                result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--stdin-json"],
                                        input=json.dumps({"source": source, "revision": revision}),
                                        capture_output=True, encoding="utf-8", timeout=10)
                self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
                report = json.loads(result.stdout)
                self.assertEqual(report["deterministic_status"], "issues_found" if expected else "passed")
                self.assertEqual(report["review_status"], "required" if expected else "not_required")
                if expected:
                    self.assertTrue(any(item["kind"] == "number" for item in report["findings"]))
                else:
                    self.assertEqual(report["findings"], [])
                    self.assertEqual(report["review_flags"], [])

    def test_dates_word_numbers_weekdays_and_amount_changes_are_findings(self):
        pairs = [
            ("La riunione è il 15 marzo.", "La riunione è il 15 maggio."),
            ("Il rimborso arriva in tre giorni lavorativi.", "Il rimborso arriva in due giorni lavorativi."),
            ("Sara vi aggiorna lunedì alle 16.", "Sara vi aggiorna martedì alle 16."),
            ("Totale: 1.250,00 €.", "Totale: 1.520,00 €."),
        ]
        for source, revision in pairs:
            with self.subTest(source=source):
                result, report = self.files(source, revision)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(report["deterministic_status"], "issues_found")

    def test_deadline_negation_and_uncertainty_only_require_review_exit_three(self):
        pairs = [
            ("Inviaci il contratto entro venerdì.", "Inviaci il contratto venerdì."),
            ("Non possiamo garantire la consegna entro il 10.", "Possiamo garantire la consegna entro il 10."),
            ("Potremmo consegnare entro il 10.", "Consegneremo entro il 10."),
        ]
        for source, revision in pairs:
            with self.subTest(source=source):
                result, report = self.files(source, revision)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(report["review_status"], "required")
                self.assertTrue(report["review_flags"])
                self.assertEqual(report["semantic_equivalence"], "not_verified")

    def test_equivalent_euro_and_contextual_time_formats_pass(self):
        pairs = [
            ("Il budget è di € 1.500.", "Il budget è di 1.500 €."),
            ("Ci vediamo alle 9:30.", "Ci vediamo alle 9.30."),
            ("Riunione ore 09:30.", "Riunione ore 9.30."),
            ("Totale €\u00a01.250,00.", "Totale 1250,00 €.")
        ]
        for source, revision in pairs:
            with self.subTest(source=source):
                result, report = self.files(source, revision)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(report["findings"], [])

    def test_responsibility_swap_remains_an_explicitly_unverified_limit(self):
        result, report = self.files("Il fornitore invierà il preventivo entro il 3 aprile.",
                                    "Il cliente invierà il preventivo entro il 3 aprile.")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["semantic_equivalence"], "not_verified")
        self.assertTrue(any("responsabilità" in value for value in report["limitations"]))

    def test_required_additional_markers_are_reviewed(self):
        words = ("entro", "prima di", "non oltre", "fino a", "a partire da", "niente", "nulla",
                 "neanche", "nemmeno", "neppure", "dovrebbe", "dovremmo", "probabilmente", "eventualmente")
        for word in words:
            with self.subTest(word=word):
                report = audit.audit_text(f"Condizione: {word} confermare.", "Condizione: confermare.")
                self.assertTrue(report["review_flags"])
                self.assertEqual(report["review_status"], "required")

    def test_euro_sign_before_currency_is_never_discarded(self):
        for negative in ("-€ 1.500", "- € 1.500", "−€ 1.500"):
            with self.subTest(negative=negative):
                report = audit.audit_text(f"Saldo: {negative}.", "Saldo: € 1.500.")
                self.assertEqual(report["deterministic_status"], "issues_found")
                self.assertTrue(any(item.get("value", "").startswith("€-") for item in report["findings"]))

    def test_euro_sign_separated_from_digits_cannot_disappear(self):
        for negative in ("- 1.500 €", "− 1.500 €", "-\t1.500 €", "-\u00a01.500 €"):
            with self.subTest(negative=negative):
                result, report = self.files(f"Saldo: {negative}.", "Saldo: 1.500 €.")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report["deterministic_status"], "issues_found")
        result, report = self.files("Saldo: - 1.500 €.", "Saldo: € -1.500.")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["findings"], [])

    def test_euro_position_normalization_preserves_uninterpreted_number_sequence(self):
        for amount in ("1234.56", "1.50", "-1234.56", "1.234.56"):
            with self.subTest(amount=amount):
                result, report = self.files(f"Totale: € {amount}.", f"Totale: {amount} €.")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(report["findings"], [])
        # Moving the symbol must not reinterpret or conflate decimal/grouping separators.
        for source, revision in (("€ 1234.56", "1234,56 €"),
                                 ("€ 1.50", "1.500 €"),
                                 ("€ 1234.56", "1234.65 €")):
            with self.subTest(source=source, revision=revision):
                result, report = self.files(f"Totale: {source}.", f"Totale: {revision}.")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report["deterministic_status"], "issues_found")

    def test_multiline_deadline_markers_cannot_disappear_unnoticed(self):
        for marker in ("prima\ndi", "prima  di", "non\toltre", "a partire\n da"):
            with self.subTest(marker=marker):
                result, report = self.files(f"Invia il contratto {marker} venerdì.", "Invia il contratto venerdì.")
                self.assertEqual(result.returncode, 3)
                self.assertTrue(any(flag["category"] == "deadline" for flag in report["review_flags"]))
        report = audit.audit_text("Invia prima\ndi venerdì.", "Invia prima di venerdì.")
        self.assertEqual(report["review_flags"], [])

    def test_common_spelled_numbers_match_digits_and_changes_are_detected(self):
        words = ("uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
                 "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette",
                 "diciotto", "diciannove", "venti", "trenta", "quaranta", "cinquanta", "sessanta",
                 "settanta", "ottanta", "novanta", "cento", "mille")
        values = [*range(1, 21), 30, 40, 50, 60, 70, 80, 90, 100, 1000]
        for word, value in zip(words, values):
            with self.subTest(word=word):
                self.assertEqual(audit.audit_text(f"Sono {word} unità.", f"Sono {value} unità.")["findings"], [])
                self.assertEqual(audit.audit_text(f"Sono {word} unità.", f"Sono {value + 1} unità.")["deterministic_status"], "issues_found")

    def test_stdin_json_audits_without_creating_files(self):
        payload = {"source": "Potremmo consegnare tre unità entro lunedì.",
                   "revision": "Consegneremo due unità martedì.",
                   "constraints": {"preserve_exact": ["tre unità"]}}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--stdin-json"],
                                     input=json.dumps(payload), cwd=directory, capture_output=True,
                                     encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["semantic_equivalence"], "not_verified")
            self.assertTrue(any(item["kind"] == "required_text" for item in report["findings"]))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_stdin_json_rejects_mixed_modes_and_invalid_payload(self):
        for payload in ("[]", "{}", '{"source":"x","revision":"x","unexpected":true}', "{broken"):
            with self.subTest(payload=payload):
                result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--stdin-json"],
                                         input=payload, capture_output=True, encoding="utf-8", timeout=10)
                self.assertEqual(result.returncode, 2)
        result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--stdin-json", "--source", "s.txt"],
                                 input='{"source":"x","revision":"x"}', capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
