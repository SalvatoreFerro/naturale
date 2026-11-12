# Verifica degli aggiornamenti Dependabot

La verifica del 12 novembre 2026 delle PR #1, #2 e #3 ha ricondotto i run rossi
alla versione 0.1.0: i test confrontavano alias di percorsi su macOS (`/var` e
`/private/var`) e Windows (`RUNNER~1` e `runneradmin`). Questi confronti sono
già corretti nella 0.2.0. I log esaminati non dimostrano una regressione delle
action o di Pillow.

La CI ora usa `actions/checkout` 7.0.1 e `actions/setup-python` 7.1.0, con SHA
immutabili verificati nei repository ufficiali. Restano `contents: read` e
`persist-credentials: false` per entrambi i checkout. Linux con Python 3.13
si aggiunge alla matrice e installa anche l'integrazione C2PA facoltativa;
ExifTool su Linux resta fissato al sorgente ufficiale 13.63.

Il limite `Pillow>=11,<13` rimane coerente fra pacchetto, skill e diagnostica.
Una prova separata sullo snapshot 0.2.0 `3c6f7d3`, Linux, Python 3.12.14,
Pillow 13.0.0, c2pa-python 0.38.1 ed ExifTool 13.63 ha passato 146 test e
37 sottocasi. Questa prova non copre tutta la matrice di supporto: l'eventuale
ampliamento a Pillow 13 va valutato separatamente, senza attribuirgli i
fallimenti storici dei percorsi. Le PR precedenti possono essere chiuse come
sostituite dalla correzione coordinata della 0.2.1.

Riprodurre i controlli locali della policy con:

```sh
python -m pytest tests/test_ci_policy.py tests/test_doctor.py
```

L'esecuzione delle action aggiornate richiede la verifica della PR su GitHub;
i test locali controllano i pin e le garanzie del workflow.
