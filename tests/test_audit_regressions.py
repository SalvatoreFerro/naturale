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


# Invented correspondence only; no messages from the private mail evaluation.
EMAIL_SAFE_CASES = [
    ("A1", "Ti richiamo qualora servisse.", "Ti richiamo se servisse."),
    ("A2", "Se confermi, procedo.", "Nel caso in cui confermi, procedo."),
    ("A3", "Ti mando il file nel caso in cui ti serva.", "Se ti serve, ti mando il file."),
    ("A4", "In caso di ritardo avvisami.", "Se c'è un ritardo, avvisami."),
    ("A5", "Passo da te, anche se arrivo tardi.", "Passo da te, nonostante arrivi tardi."),
    ("A6", 'Mi avete indicato come “dottore” anche se sono ancora studente.',
     'Mi avete indicato come “dottore”: sono ancora studente.'),
    ("A7", "Prima di procedere con l'invio ricontrollo tutto.", "Prima dell'invio ricontrollo tutto."),
    ("A8", "Nessun costo di attivazione e nessun rinnovo automatico.",
     "Nessun costo di attivazione né rinnovo automatico."),
    ("A9", "Non sono dati definitivi o ufficiali.", "Non sono dati definitivi né ufficiali."),
    ("A10", "Cerchiamo un sponsor principale.", "Cerchiamo uno sponsor principale."),
    ("A11", "Sei tra i primi utenti.", "Rientri tra i primi utenti."),
    ("A12", "Se sei in zona uno di questi giorni, chiamami.",
     "Se uno di questi giorni sei in zona, chiamami."),
    ("A13", "Grazie mille per l'aiuto.", "Grazie davvero per l'aiuto."),
    ("A14", "Ci vediamo dalle 19:30 alle 20:15.", "Ci vediamo dalle 19.30 alle 20.15."),
    ("A15", "Ho inviato la domanda in data odierna.", "Ho inviato la domanda oggi."),
    ("A16", "Trovi tutto su Esempio.it.", "Trovi tutto su esempio.it."),
    ("A17", "Ci sentiamo dieci minuti.", "Ci sentiamo 10 minuti."),
    ("A18", "Le condizioni sono queste.", "Le condizioni sono le seguenti."),
    ("A19", "Marta mi ha risposto, la ringrazio. Ti scrivo per due cose.",
     "Marta mi ha risposto e la ringrazio. Ti scrivo per due cose."),
    ("A20", "Il file è in Base64.", "Il file è in base64."),
    ("A21", "Ci sentiamo la prossima settimana.", "Ci sentiamo la settimana prossima."),
]
EMAIL_ERROR_CASES = [
    ("B1", "Il volo AB1234 parte alle 7.", "Il volo AB1243 parte alle 7.", "finding", "identifier"),
    ("B2", "Il poster S05-7 è pronto.", "Il poster S06-7 è pronto.", "finding", "identifier"),
    ("B3", "Stampa in formato A0.", "Stampa in formato A1.", "finding", "identifier"),
    ("B4", "Te l'ho scritto oggi.", "Te l'ho scritto ieri.", "finding", "relative_day"),
    ("B5", "Ne parliamo domani.", "Ne parliamo dopodomani.", "finding", "relative_day"),
    ("B6", "Ci sentiamo questa settimana.", "Ci sentiamo la prossima settimana.", "review", "relative_period"),
    ("B7", "Le condizioni sono su esempio.it.", "Le condizioni sono su esempio.com.", "finding", "domain"),
    ("B8", "Scrivi a info@esempio.it.", "Scrivi a inf@esempio.it.", "finding", "email"),
    ("B9", "Prima della firma riceverai la bozza.", "Dopo la firma riceverai la bozza.", "review", "deadline"),
    ("B10", "Ti mando il link nel caso in cui vada bene anche a te.",
     "Quando va bene anche a te, ti mando il link.", "review", "condition"),
    ("B11", "Se approvate partiamo lunedì; in caso di rinvio vi avviso.",
     "Partiamo lunedì; se c'è un rinvio vi avviso.", "review", "condition"),
    ("B12", "Ti scrivo per confermarti l'orario.", "Le scrivo per confermarLe l'orario.", "review", "register"),
    ("B13", "Gentile dottoressa, Le invio il file.", "Gentile dottoressa, ti invio il file.", "review", "register"),
    ("B14", "Firmo anche se il prezzo sale.", "Firmo se il prezzo sale.", "review", "condition"),
    ("B15", "Servono sei foto.", "Servono cinque foto.", "finding", "number"),
]


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

    def stdin(self, source, revision, constraints=None):
        payload = {"source": source, "revision": revision}
        if constraints is not None:
            payload["constraints"] = constraints
        result = subprocess.run([sys.executable, str(SCRIPT), "audit", "--stdin-json"],
                                input=json.dumps(payload), capture_output=True,
                                encoding="utf-8", timeout=10)
        self.assertIn(result.returncode, (0, 1, 3), result.stderr)
        return result, json.loads(result.stdout)

    def test_email_tokens_are_bounded_and_protect_their_inner_words_and_digits(self):
        cases = [
            ("long_non_address", "+" * 50_000, "+" * 50_000, 0),
            ("address_tokens", "Scrivi a domani12+note@esempio.it.",
             "Scrivi a ieri13+note@esempio.it.", 1),
        ]
        for case, source, revision, expected in cases:
            with self.subTest(case=case):
                result, report = self.stdin(source, revision)
                self.assertEqual(result.returncode, expected)
                if expected:
                    self.assertEqual({item["kind"] for item in report["findings"]}, {"email"})
                else:
                    self.assertEqual(report["findings"], [])
                    self.assertEqual(report["review_flags"], [])

    def test_email_safe_rewrites_are_silent(self):
        for case, source, revision in EMAIL_SAFE_CASES:
            with self.subTest(case=case):
                result, report = self.stdin(source, revision)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(report["findings"], [])
                self.assertEqual(report["review_flags"], [])
                self.assertEqual(report["review_status"], "not_required")

    def test_email_visible_errors_keep_the_expected_signal(self):
        for case, source, revision, signal, category in EMAIL_ERROR_CASES:
            with self.subTest(case=case):
                result, report = self.stdin(source, revision)
                self.assertIn(result.returncode, (1, 3), result.stdout)
                if signal == "finding":
                    self.assertEqual(result.returncode, 1)
                    self.assertTrue(any(item["kind"] == category for item in report["findings"]), result.stdout)
                else:
                    self.assertTrue(any(flag["category"] == category for flag in report["review_flags"]), result.stdout)

    def test_quoted_conversation_scope_and_preservation(self):
        current = "Va bene, confermo giovedì alle 10:00."
        revised = "Perfetto, confermo giovedì alle 10:00."
        italian = "Il giorno mar 3 nov 2026 alle ore 09:12 Nilo Falenzi <nilo@esempio.it> ha scritto:"
        english = "On Tue, 3 Nov 2026 at 09:12, Nilo Falenzi <nilo@esempio.it> wrote:"
        quoted = "> Possiamo fare giovedì alle 10:00?\n> Il preventivo è di 300 €."
        for case, header, keep_history in (("C1", italian, False), ("C2", italian, True), ("C3", english, False)):
            with self.subTest(case=case):
                source = current + "\n\n" + header + "\n" + quoted
                revision = revised
                if keep_history:
                    revision += "\n\n" + header + "\n" + quoted.replace("300 €", "350 €")
                result, report = self.stdin(source, revision)
                self.assertEqual(report["counts"], {"source_characters": len(source), "revision_characters": len(revision)})
                if case == "C1":
                    self.assertIn("300 €", audit.audit_text(source, revision, include_diff=True)["diff"])
                if keep_history:
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertTrue(any(item["kind"] == "number" for item in report["findings"]))
                    self.assertFalse(report["comparison_scope"]["source_history_excluded"])
                    self.assertFalse(report["comparison_scope"]["revision_history_excluded"])
                else:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertEqual(report["findings"], [])
                    self.assertEqual(report["review_flags"], [])
                    self.assertTrue(report["comparison_scope"]["source_history_excluded"])
                    self.assertFalse(report["comparison_scope"]["revision_history_excluded"])

    def test_history_exclusion_does_not_hide_unquoted_or_newly_added_content(self):
        current = "Confermo."
        history = "\n\nIl giorno mar 3 nov 2026 alle ore 09:12 Nilo Falenzi <nilo@esempio.it> ha scritto:\n> Totale 300 €."
        cases = [
            ("mixed_tail", current + history + "\n\nNuova nota: budget 500 €.", current),
            ("newly_added_history", current, current + history),
        ]
        for case, source, revision in cases:
            with self.subTest(case=case):
                result, report = self.stdin(source, revision)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(any(item["kind"] == "number" for item in report["findings"]))
                self.assertFalse(report["comparison_scope"]["source_history_excluded"])
                self.assertFalse(report["comparison_scope"]["revision_history_excluded"])

    def test_review_contexts_are_short_bounded_and_locate_condition(self):
        for case, source, revision, signal, _ in EMAIL_ERROR_CASES:
            if signal != "review":
                continue
            with self.subTest(case="D-" + case):
                _, report = self.stdin(source, revision)
                self.assertTrue(report["review_flags"])
                for flag in report["review_flags"]:
                    contexts = flag["contexts"]
                    self.assertEqual(set(contexts), {"source", "revision"})
                    self.assertTrue(contexts["source"] or contexts["revision"])
                    for version, fragments in contexts.items():
                        self.assertIsInstance(fragments, list)
                        self.assertLessEqual(len(fragments), 2)
                        for fragment in fragments:
                            self.assertIsInstance(fragment, str)
                            self.assertLessEqual(len(fragment), 60)
                            excerpt = fragment.strip("…")
                            self.assertTrue(excerpt)
                            self.assertIn(excerpt, source if version == "source" else revision)
                if case == "B10":
                    flag = next(flag for flag in report["review_flags"] if flag["category"] == "condition")
                    self.assertTrue(any("nel caso in cui" in fragment.casefold() for fragment in flag["contexts"]["source"]))

    def test_history_scope_keeps_explicit_constraints_and_unmarked_text(self):
        current = "Confermo giovedì alle 10:00."
        history = "Il giorno mar 3 nov 2026 alle ore 09:12 Nilo Falenzi <nilo@esempio.it> ha scritto:\n> Totale 300 €."
        cases = [
            ("explicit_constraint", current + "\n\n" + history, {"preserve_exact": ["300 €"]}, "required_text"),
            ("unmarked_text", current + "\n\nPromemoria non citato: totale 300 €.", None, "number"),
        ]
        for case, source, constraints, kind in cases:
            with self.subTest(case=case):
                result, report = self.stdin(source, current, constraints)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(any(item["kind"] == kind for item in report["findings"]), result.stdout)

    def test_marker_classes_register_and_unicode_keep_expected_signals(self):
        cases = [
            ("third_person", "Lei mi ha risposto. Ti scrivo per due cose.",
             "La dottoressa mi ha risposto. Ti scrivo per due cose.", None),
            ("condition_nfc_nfd", "Purché confermi, procedo.", "Purche\u0301 confermi, procedo.", None),
            ("negation_nfc_nfd", "Né confermo né annullo.", "Ne\u0301 confermo ne\u0301 annullo.", None),
            ("condition_nfd_removed", "Purche\u0301 confermi, procedo.", "Procedo.", "condition"),
            ("exception_equivalence", "Partiamo salvo pioggia.", "Partiamo a meno che piova.", None),
            ("requirement_equivalence", "Partiamo solo se confermi.", "Partiamo a condizione che confermi.", None),
        ]
        for case, source, revision, category in cases:
            with self.subTest(case=case):
                result, report = self.stdin(source, revision)
                if category is None:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertEqual(report["findings"], [])
                    self.assertEqual(report["review_flags"], [])
                else:
                    self.assertEqual(result.returncode, 3, result.stdout)
                    self.assertTrue(any(flag["category"] == category for flag in report["review_flags"]))

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
