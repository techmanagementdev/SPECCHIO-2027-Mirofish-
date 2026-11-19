# Il metodo di simulazione

## 1. Dal dato alla persona

Una **persona di opinione** è un profilo tipo che riassume un gruppo di rispondenti. Ogni persona ha:

| Parametro | Significato | Da dove viene |
|---|---|---|
| `atteggiamento` (−1…1) | Clima e giudizio di partenza verso l'organizzazione o l'amministrazione | Media delle domande di clima o soddisfazione |
| `fiducia` (0…1) | Fiducia nel mittente | Domanda di fiducia nella direzione o nell'ente |
| `scetticismo` (0…1) | Quanto diffida di annunci e promesse | Inverso della fiducia, affinato con le risposte aperte |
| `influenza` (0…1) | Peso nel passaparola | Ruolo (caposquadra, sindaco, attivista…) e reti informali |
| `sensibilita` | Importanza dei temi (turni, sicurezza, pedaggi, servizi…) | Domande di importanza e matrice delle priorità |
| `canali` | Fiducia in ciascun canale | Domande sulla dieta informativa |
| `posizioni` | Reazioni a parole chiave specifiche (es. «ZTL» per i commercianti) | Risposte aperte e interviste |
| `criticita`, `aspettative`, `frasi`, `obiezioni` | Contenuti qualitativi | Risposte aperte codificate |

Con **Importa dati** il sistema calcola automaticamente atteggiamento e fiducia per ogni gruppo con almeno 10 risposte. I campi qualitativi si completano poi a mano nel file JSON del mondo, con la revisione scientifica di chi ha condotto l'indagine.

## 2. Dalla persona alla popolazione

La composizione (`unità → persona → numero`) genera fino a 400 agenti. Ogni agente eredita i parametri della propria persona con piccole variazioni casuali e un'inclinazione individuale: due agenti della stessa persona non reagiscono in modo identico.

Gli agenti sono collegati in una **rete sociale**: legami soprattutto dentro la stessa unità (reparto o quartiere), alcuni ponti tra unità, più legami per gli agenti influenti.

## 3. La reazione al messaggio

1. **Analisi del messaggio**: temi toccati e loro verso (un aumento è positivo se riguarda stipendi o servizi, negativo se riguarda tasse o pedaggi), concretezza (date, numeri), ascolto (proposte, confronto), enfasi (superlativi), incertezza (condizionali).
2. **Raggiungimento**: il canale scelto raggiunge un agente con una probabilità che dipende da quanto la sua persona si fida di quel canale. Si possono indicare unità bersaglio.
3. **Giudizio**:
   - in **modalità dimostrativa**: temi pesati per sensibilità, posizioni sulle parole chiave, effetto dello stile modulato da fiducia e scetticismo, credibilità del canale;
   - con il **modello linguistico**: ogni persona riceve la propria scheda e il messaggio, e restituisce punteggio, emozione, frase, obiezione e propensione a parlarne.

## 4. Il passaparola, round per round

A ogni round gli agenti informati ne parlano con i propri contatti, con probabilità crescente con influenza e intensità dell'opinione:

- chi **non sapeva** riceve la notizia deformata dal passaparola, che di solito la peggiora un po';
- chi **sapeva già** si avvicina all'opinione dei contatti, ma solo se non è opposta alla propria; le opinioni negative pesano di più;
- ognuno resta in parte **ancorato alla propria idea**.

Si contano anche le **voci**: notizie passate da agenti molto negativi.

## 5. Più esecuzioni e lettura dei risultati

La simulazione è ripetuta con semi diversi (predefinito: 3 esecuzioni). Il sistema riporta la media e la fascia tra minimo e massimo; la **stabilità** indica quanto i risultati cambiano tra un'esecuzione e l'altra.

| Misura | Lettura |
|---|---|
| Gradimento (0–100) | 50 è neutro; sopra 55 prevale il favore, sotto 45 la contrarietà |
| Raggiunti dal canale | Quota raggiunta direttamente, prima del passaparola |
| Positivi e negativi | Quota di agenti con opinione chiaramente favorevole o contraria |
| Classifica delle personas | Da dove partivano a dove arrivano |
| Obiezioni, voci, consigli | Che cosa correggere prima di diffondere |

## 6. Limiti

- Gli agenti basati su modelli linguistici tendono a **uniformarsi** più delle persone reali: per questo il motore limita l'influenza reciproca e ancora ogni agente alla propria opinione.
- La modalità dimostrativa riconosce i temi con un **vocabolario**: messaggi con lessico insolito possono essere letti in modo impreciso. La radiografia del messaggio mostra cosa è stato riconosciuto.
- I risultati sono **esplorativi**: servono a scegliere tra alternative e a preparare risposte, non a stimare consensi. Vanno confermati con una breve domanda reale (ad esempio il canale QR previsto nella proposta EMI-AAA-2026-02).
- **Taratura**: quando sono disponibili i dati reali, tenere da parte 2–3 domande dell'indagine, porle alle personas e confrontare le risposte simulate con quelle reali prima di usare il sistema per decisioni.

## 7. Usi da evitare

- Profilare **persone identificabili** o attribuire opinioni a individui reali.
- Usare dati raccolti per un fine (ad esempio la soddisfazione dei clienti) per un fine diverso, come la profilazione politica: il GDPR lo vieta senza una nuova base giuridica e le opinioni politiche sono dati particolari (art. 9).
- Generare e inviare **messaggi personalizzati agli elettori**: l'AI Act (Allegato III, punto 8b) classifica ad alto rischio i sistemi destinati a influenzare il voto.
- Diffondere i risultati come **sondaggi**, soprattutto nei 15 giorni prima delle elezioni (legge 28/2000, art. 8).
