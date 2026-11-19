# Strumenti open source: cosa scaricare e come usarli

SPECCHIO funziona da solo. I progetti qui sotto servono come **riferimento** o per **potenziare** singole parti: simulazione sociale su larga scala, questionari posti ad agenti, interfacce già pronte.

## Cosa scaricare

| Progetto | Repository | Licenza | Per cosa usarlo in SPECCHIO |
|---|---|---|---|
| **OASIS** (CAMEL-AI) | `camel-ai/oasis` · `pip install camel-oasis` | Apache-2.0 | Motore social su larga scala (fino a un milione di agenti, 23 azioni tipo post, commento, like). Candidato a sostituire `engine.py` nella fase di passaparola |
| **AgentSociety** (Tsinghua) | `tsinghua-fib-lab/AgentSociety` | Apache-2.0, esclusa la cartella `commercial` | Simulazioni di città e risposte alle politiche pubbliche con agenti dotati di bisogni ed emozioni |
| **Concordia** (Google DeepMind) | `google-deepmind/concordia` · `pip install gdm-concordia` | Apache-2.0 | Scenari con un «game master» che gestisce l'ambiente: utile per simulare un'assemblea pubblica o una trattativa |
| **TinyTroupe** (Microsoft) | `microsoft/tinytroupe` | MIT | Schede persona dettagliate ed esperimenti controllati: riferimento per arricchire le personas |
| **EDSL** (Expected Parrot) | `expectedparrot/edsl` · `pip install edsl` | da verificare nel file LICENSE | Porre questionari strutturati alle personas: utile per la **taratura** sulle domande tenute da parte |
| **MiroFish** | `666ghj/MiroFish` | **AGPL-3.0** | Applicazione completa (documenti → grafo → personas → social simulato → report). Da usare come **banco di prova**, non da copiare nel codice |
| **MiroFish-Offline** | `nikmcfly/MiroFish-Offline` | **AGPL-3.0** | Versione locale di MiroFish con Neo4j e Ollama (serve una GPU con circa 24 GB) |

**Da evitare:** fork di MiroFish che si dichiarano MIT. Il codice di partenza è AGPL e un terzo non può cambiarne la licenza.

## Scaricarli

```bash
./scripts/scarica_open_source.sh
```

Lo script clona i progetti nella cartella `upstream/`, esclusa da git: restano sul tuo computer come riferimento e non entrano nel repository.

## Regola delle licenze

- Nel codice di SPECCHIO si possono **integrare** solo progetti con licenza permissiva (Apache-2.0, MIT), citandoli nel file `NOTICE`.
- **MiroFish e i suoi fork (AGPL-3.0)** si usano come applicazioni separate. Se se ne modifica il codice e lo si offre online ad altri, va reso disponibile tutto il codice modificato.
- Questo repository è pubblico: i dati dei clienti non vanno mai qui, nemmeno anonimizzati.

## Come collegare un motore esterno

Il punto di innesto è la funzione `esegui_una` in `backend/app/engine.py`. Un motore esterno deve restituire, per ogni round:

```python
{"informati": %, "indice": 0-100, "positivi": %, "negativi": %, "neutri": %}
```

e, per ogni unità, i conteggi `pos`, `neu`, `neg`, `non` usati dalla mappa. Il resto (classifica, obiezioni, consigli, interfaccia) non cambia.

Percorso consigliato:

1. **Taratura con EDSL**: si pongono alle personas 2–3 domande dell'indagine reale e si confrontano le risposte.
2. **Passaparola con OASIS**: si sostituisce la fase dei round con una simulazione OASIS sugli stessi agenti, mantenendo le reazioni iniziali calcolate da SPECCHIO o dal modello linguistico.
3. **Confronto con MiroFish**: si fa girare lo stesso scenario su MiroFish come controllo esterno e si confrontano le direzioni dei risultati.
