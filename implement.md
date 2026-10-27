# Commodore3.8 27B — Developer Brief

> **Opdrachtgever:** Michel Fidder (mfidder2026)
> **Datum:** 27 oktober 2026
> **Status:** specificatie, blokkerende vragen beantwoord (zie §0.1), nog geen code
> **Doel van dit document:** alles wat een AI-developer nodig heeft om een eigen, op Qwen3.8-27B gebaseerd codeermodel voor Commodore-computers te trainen, te verpakken en te distribueren, inclusief een eigen meegeleverde AI-engine. Hoofdstuk 12 bevat open vragen die vóór de start beantwoord moeten worden.

---

## 0. Samenvatting in één alinea

We nemen **Qwen/Qwen3.8-27B** (Apache-2.0, dense 27B, hybride GatedDeltaNet/full-attention, vision-language) als basis, en fine-tunen dit met **(Q)LoRA** op een zelf samengestelde, **machinaal geverifieerde** dataset van Commodore-code (C64, C128, Plus/4, PET, Amiga; BASIC, assembler, machinetaal). Het resultaat wordt samengevoegd tot volledige gewichten en daarna gekwantiseerd naar **GGUF Q4_K_M** (LM Studio, Ollama, llama.cpp), **MLX 4-bit** (LM Studio op Mac, mlx-lm) en een **MTPLX-pack via Forge** (snelle Mac-inference met MTP-heads). Daarnaast leveren we een eigen engine/app die het model draait **én** de bestaande skillsets (syntax-checkers, bas2prg, Kick Assembler, VICE) als tools aanbiedt, zodat het model zijn eigen code kan controleren. Belangrijkste les vooraf: **feiten uit handleidingen horen in RAG, stijl en dialect horen in fine-tuning, en correctheid komt uit tools.**

---

## 0.1 Genomen beslissingen (27 oktober 2026)

Deze beslissingen gaan vóór de voorstellen elders in dit document. Waar een hoofdstuk iets anders zegt, geldt deze tabel.

| # | Beslissing | Gevolg |
|---|---|---|
| D1 | **Publiek en gratis** model voor de community | Open licentie. Alleen data met vrije of eigen rechten in de gepubliceerde dataset. Nette model card |
| D2 | PETSCII-stuurcodes in BASIC altijd als **`chr$(…)`** (bijv. `print chr$(147)`) | Sluit aan op bestaande bas2prg en checkers. Geen `{clr}`-notatie in trainingsdata. Bronnen met petcat-notatie omzetten |
| P1 | "Commodore 4" = **Plus/4 + C16/C116** (TED, BASIC 3.5) | Verificatie via VICE `xplus4` (ook C16-model) |
| P2 | **Alle platformen in v1:** C64, C128, Plus/4/C16, PET, Amiga | Grote scope. Zie de fasering in §11, die binnen v1 de volgorde aanhoudt C64/C128 → Plus/4 → PET → Amiga |
| P5 | **Machinecode vervalt.** Alleen BASIC en assembler | Geen hex-, monitor- of DATA/POKE-loaders als apart doel |
| G1 | **Alle eigen Commodore-repos** mogen in de trainingsdata (lijst in §1.1) | Wel per repo assets (graphics/muziek/leveldata van bestaande IP) strippen. Zie §1.1 |
| G2 | **Handleidingen zijn er nog niet** | Developer stelt een bronnenlijst op met rechtenstatus. Standaard: alleen lokale RAG, niet in de publieke dataset |
| M1 | **Alleen Qwen3.8-27B** | Geen 4B/9B-variant. Minimale eindgebruikershardware ≈ 24 GB GPU of 32 GB Mac (Q4) |
| H1 | Hardware: **Mac Apple Silicon met ≥ 128 GB** unified memory | Trainingspad wordt **MLX** (mlx-lm), niet Unsloth/CUDA. Zie §6.0 |
| H2 | **Geen cloud: alles lokaal** | Geen H100-runs. Trainingstijd is de bottleneck: proefrun meet doorlooptijd |
| E1 | Engine **optie D**: llama.cpp-app (Win/Linux) + MTPLX (Mac) + gedeelde tool/MCP-laag | Zie §10 |
| N1 | Naam blijft **Commodore3.8**. Merkrisico bewust geaccepteerd door opdrachtgever | Wel een disclaimer "not affiliated with or endorsed by the Commodore/Amiga trademark holders" in model card, README en app |

---

## 1. Wat er al bestaat (input van de opdrachtgever)

| Repo | Inhoud | Bruikbaar als |
|---|---|---|
| [c64_kickass_ai_skillset](https://github.com/mfidder2026/c64_kickass_ai_skillset) | `C64_KICKASS_SKILL.md` (~3.700 regels: syntax, scripttaal, macro's, segments, 21 recepten, 28 praktijklessen uit eigen games), `c64_ka_syntax_checker.py` (~1.600 regels, CLI + Python-API), `build.bat` (check → KickAss → VICE) | Trainingsdata (regels → Q&A), RAG-bron, **verificatietool** in de datapijplijn en in de engine |
| [c128_basic_ai_skillset](https://github.com/mfidder2026/c128_basic_ai_skillset) | `c128_basic_skill.md` (BASIC 7.0, 40/80-koloms, BANK, sprites, SID), `c128_syntax_checker.py` met `--json` en exitcodes 0/1/2, `bas2prg.py` (tokenizer, load `$1C01`, `-i` case-inversie), `pong.bas`, toolchain-tests, Roo-skill | Idem; de `--json`-output is direct bruikbaar in een geautomatiseerde loop |
| [c64_basic_ai_skillset](https://github.com/mfidder2026/c64_basic_ai_skillset) | `c64_basic_skill.md` (EN + NL), `c64_syntax_checker.py` (EN + NL), `bas2prg.py` | Idem; checker heeft nog **geen** `--json`-modus → toevoegen |
| Eigen projecten (lokaal) | o.a. `dune64` (C64-game, cc65 + eigen fastloader, SID), `GeosU64` (GEOS voor C64 Ultimate) | Waardevolle, **echte** projectcode met bekende licentie (eigen werk) |

**Opmerkingen bij de repos**
- Geen van de drie repos heeft een `LICENSE`-bestand. Voor gebruik als trainingsdata door de eigenaar zelf is dat geen probleem, maar als de dataset of de skills worden meegepubliceerd moet er een licentie op (voorstel: MIT of Apache-2.0 voor code, CC-BY-4.0 voor de skill-documenten).
- De skills zijn deels Nederlandstalig (KickAss-skill, NL-varianten). Bepaal de trainingstaal (zie vraag T3).
- De checkers zijn de belangrijkste asset: ze maken **automatische verificatie** van gegenereerde trainingsdata mogelijk. Zorg dat alle drie dezelfde machineleesbare interface krijgen (`--json`, exitcode 0/1/2).

### 1.1 Eigen Commodore-repos voor de dataset (beslissing G1)

Alle repos van `github.com/mfidder2026` (stand 27-10-2026) plus het lokale project GeosU64:

| Repo | Inhoud | Aandachtspunt |
|---|---|---|
| c64_kickass_ai_skillset, c128_basic_ai_skillset, c64_basic_ai_skillset | Skills, checkers, bas2prg | Kern van de regels en de verificatie |
| dune64 | C64-game naar Dune (PC), cc65 + fastloader + SID | Gebaseerd op bestaande IP: **code** wel, afgeleide graphics/teksten/muziek strippen |
| GeosU64 (lokaal) | GEOS voor C64 Ultimate | GEOS-code van derden onderscheiden van eigen code |
| calda | Zelda-achtige C64-game | Eigen werk |
| commodore_keen | Port van Commander Keen | Bestaande IP: alleen eigen code, geen originele assets |
| c64red | Port van Pokémon Red vanuit assembler | Waarschijnlijk afgeleid van een disassembly van commerciële software → **juridisch het meest gevoelig.** Alleen eigen engine-/portcode, geen geport origineel |
| c64city | uCity-port (Game Boy) | uCity is open source (GPL?): licentie checken, eigen portcode is bruikbaar |
| C64GB | Game Boy-emulator voor de C64 Ultimate | Eigen werk, zeer waardevol (complex assembler) |
| commodore_desk | GUI voor de C64 | Eigen werk |
| sidplayer | SID-player | Eigen code ja, meegeleverde SID-tunes nee |
| C64U-H2H | Head-to-head netwerktest C64 Ultimate | Eigen werk, Ultimate-netwerk-API |
| Cowboy-Castaway | Screensaver (cc65, gemaakt met LM Studio) | Eigen werk |
| Commodore64_Gameserver | Windows-gameserver (Wizard of Wor LAN) | Grotendeels pc-code: alleen het C64-deel gebruiken |

Bijna al deze projecten zijn C64-gericht. Voor **C128 (assembler), Plus/4, PET en Amiga is er nog nauwelijks eigen code** → daar is synthetische en open-source data nodig.

Gerelateerde eigen projecten die mogelijk bruikbaar zijn voor de engine: **AetherDrift** ("Run monster AI Models on Apple Silicon Devices") en **DocWizard** (praat al met LM Studio, Ollama en MTPLX). Developer: beoordelen of die als basis voor de engine-app kunnen dienen.

---

## 2. Onderzochte software

### 2.1 Kev (jaredpalmer/kev) — **niet geschikt**
Kev is een familie *beslismodellen* (ja/nee, multiple choice, score met gekalibreerde kans) op Qwen3.5/3.8-basis. Het genereert geen tekst of code. Het is daarom ongeschikt als basis voor een codeermodel. Hooguit is het later bruikbaar als goedkope "rechter", maar onze checkers en VICE zijn betrouwbaarder. **Advies: niet gebruiken.**

### 2.2 Basismodel: Qwen/Qwen3.8-27B
| Eigenschap | Waarde | Gevolg voor ons |
|---|---|---|
| Licentie | Apache-2.0 | Fine-tunen, hernoemen en commercieel verspreiden toegestaan, mits LICENSE + NOTICE meegeleverd en wijzigingen vermeld |
| Architectuur | `Qwen3_5ForConditionalGeneration`, `model_type: qwen3_5`; dense 27B, 64 lagen (48 GatedDeltaNet-lineaire attention + 16 full attention) | Vereist recente tooling. Oudere llama.cpp-builds laden het niet |
| Type | image-text-to-text (vision-taal) | Vision-encoder bevriezen tijdens training; beslissen of we vision meeleveren (GGUF `mmproj`) |
| Context | ~262K native | Lange assemblerlistings passen; trainen doen we op kortere sequenties |
| MTP-heads | Ja (gebruikt door MTPLX en recente llama.cpp) | Na fine-tunen passen de originele MTP-heads niet meer exact. Opnieuw trainen via MTPLX Forge (§2.4) |
| Thinking-modus | Ja (reasoning-effort tot `xhigh`) | Bepalen of trainingsdata redeneerstappen bevat (vraag M4) |
| Kwantisaties | Unsloth en bartowski publiceren GGUF's; Q4 ≈ 17–19 GB | Q4_K_M als standaard-release is realistisch voor 24 GB GPU's en Macs vanaf 32 GB |

> ⚠️ **"Q4 trainen" bestaat niet echt.** Je traint LoRA-adapters (in bf16) bovenop een in 4-bit geladen basismodel (**QLoRA**), voegt de adapter samen met de **bf16**-gewichten, en kwantiseert **daarna** opnieuw naar Q4. Samenvoegen met een al-gekwantiseerd model geeft merkbaar kwaliteitsverlies. "Commodore3.8 27B Q4" is dus de naam van één *release-variant*, niet van het trainingsproces.

### 2.3 Trainingstooling
| Tool | Platform | Geschikt voor | Opmerkingen |
|---|---|---|---|
| **Unsloth** (≥ v0.1.800, aug 2026) | Linux/WSL2 + NVIDIA | QLoRA/LoRA van Qwen3.8-27B, export naar GGUF | Officiële uploads `unsloth/Qwen3.8-27B(-GGUF)`. Volgens secundaire bronnen nog geen officieel 27B-notebook. **Eerst kleine proefrun.** |
| LLaMA-Factory / Axolotl | Linux + NVIDIA | Alternatief, meer configuratie | Controleer of `qwen3_5` ondersteund wordt in de gekozen versie |
| **mlx-lm** (`mlx_lm.lora`, `mlx_lm.fuse`) | Apple Silicon | (Q)LoRA op Mac | `fuse --dequantize` → bf16 → opnieuw kwantiseren. 64 GB Mac is ongeveer het minimum voor 27B, 128 GB is comfortabel (schatting, testen) |
| Cloud (RunPod, Lambda, Modal, Vast) | H100/H200 80 GB | Volledige bf16-LoRA, lange context | Ruwe orde: €2–4 per GPU-uur. Een complete run van enkele uren kost tientallen tot enkele honderden euro's (schatting) |

**Geheugen-indicatie (schattingen, verifiëren met proefrun):**
- QLoRA 27B, sequenties 2–4K, gradient checkpointing: **24 GB VRAM krap, 48 GB comfortabel**
- QLoRA met sequenties 8–16K: **80 GB**
- bf16-LoRA: **≥ 80 GB**
- Samenvoegen naar bf16: ~**64 GB systeem-RAM** (bf16-gewichten ≈ 54–56 GB)

### 2.4 MTPLX (github.com/youssofal/MTPLX)
- **Wat:** native Mac-app + CLI (Apache-2.0), gebouwd op MLX. Draait modellen met hun eigen **MTP-heads** als speculatieve decoder, met exacte rejection sampling. Volgens de README levert dat ongeveer 1,6–2,2× snellere generatie. Qwen 3.8 27B is het aanbevolen codeermodel; gemeten 52–88 tok/s op een M5 Max.
- **API:** OpenAI-compatibel (`/v1/chat/completions`, `/v1/responses`, …) en Anthropic-compatibel (`/v1/messages`) op `127.0.0.1:8000`, met tool calls. Werkt met Claude Code, Cline, Continue, Open WebUI. Kan ook embedding- en rerank-modellen serveren, dus RAG zonder tweede server.
- **Cruciaal voor ons — Forge:** `mtplx forge` zet een Hugging Face-repo om naar MLX, **traint de MTP-adapter opnieuw** tegen precies die gewichten, meet of het sneller is en publiceert naar de Hub. MTPLX weigert expliciet een losse MTP-head op een andere trunk te plakken. **Ons gefinetunede model moet dus via Forge**, vanaf het samengevoegde bf16-checkpoint.
- **Beperking:** alleen Apple Silicon (M1+, macOS 14+). Geen Windows of Linux. De opdrachtgever werkt op Windows → MTPLX kan de Mac-distributie zijn, niet de enige engine.
- **Modelmappen:** `~/.mtplx/config.toml` (`model_dir`, `model_dirs`) en `--model-search-dir`; lokale paden worden ondersteund.

### 2.5 Runtimes voor eindgebruikers
| Runtime | Formaat | Status voor Qwen3.8-27B (`qwen35`-arch) | Actie |
|---|---|---|---|
| **llama.cpp** | GGUF | Ondersteund in builds vanaf ongeveer mei 2026, inclusief MTP | Minimale buildversie vastleggen in de README |
| **LM Studio** | GGUF (Win/Linux/Mac) + MLX (Mac) | Volgens secundaire bronnen ja. **Niet officieel bevestigd** | Zelf testen met onze eigen GGUF |
| **Ollama** | GGUF + Modelfile | Volgens één blog ja. **Niet officieel bevestigd** | Zelf testen. Modelfile met juiste chat-template/stop-tokens maken. Publiceren op ollama.com |
| **MTPLX** | MLX-pack via Forge | Ja (Qwen 3.8 27B is first-class) | Forge-pack bouwen en op HF publiceren |

Een community-bron meldt dat mainline llama.cpp bij deze hybride architectuur stil naar CPU terugvalt voor KV-caches die niet q4 zijn. Dat is niet geverifieerd: meenemen in de testmatrix.

---

## 3. Doelarchitectuur

```text
            ┌───────────────────────── DATA ─────────────────────────┐
 bronnen ─▶ │ verzamelen ─▶ licentiecheck ─▶ normaliseren ─▶ dedup   │
 (eigen     │      ─▶ instructieparen maken ─▶ VERIFIËREN (checker,  │
  code,     │         assembler, VICE/emulator) ─▶ train/val/test     │
  docs,     └────────────────────────────┬───────────────────────────┘
  skills)                                │
                                         ▼
            ┌──────────────────────── TRAINING ──────────────────────┐
            │ QLoRA op Qwen3.8-27B ─▶ eval vs. baseline ─▶ iteratie   │
            │ ─▶ merge naar bf16 "Commodore3.8-27B"                  │
            └───────┬───────────────┬────────────────┬───────────────┘
                    ▼               ▼                ▼
             GGUF Q4_K_M/      MLX 4/8-bit      MTPLX Forge-pack
             Q5/Q6/Q8 (+mmproj?)  (LM Studio Mac)   (MTP-heads hertraind)
                    │               │                │
        LM Studio · Ollama · llama.cpp      LM Studio   MTPLX
                    │
                    ▼
            ┌──────────────── EIGEN ENGINE / APP ────────────────────┐
            │ model-runtime + RAG over handleidingen + TOOLS:         │
            │ syntax-checkers · bas2prg · KickAss/ca65/ACME · VICE    │
            │ (x64sc/x128/xplus4/xpet) · Amiga-emulator · d64-tools   │
            └────────────────────────────────────────────────────────┘
```

**Kernprincipes**
1. **Elk trainingsvoorbeeld met code is machinaal geverifieerd.** Minimaal: checker 0 errors en assembler/tokenizer slaagt. Waar mogelijk ook: draait in de emulator zonder crash en geeft het verwachte schermresultaat of geheugenresultaat.
2. **Fine-tuning ≠ kennisopslag.** Adressen, registertabellen en kernal-vectoren onthoudt een model via fine-tuning slecht en hallucineert het graag. Die gaan via **RAG** (handleidingen, memory maps) en via de skill-documenten in de prompt.
3. **De baseline moet verslagen worden.** Eerst meten hoe goed *ongetrainde* Qwen3.8-27B is, met de skill-documenten als systeemprompt en de checker-loop. De fine-tune heeft alleen zin als die daar aantoonbaar overheen gaat.

---

## 4. Platformen & talen (scope-matrix)

Te bevestigen door de opdrachtgever (vragen P1–P6). Voorstel voor prioriteit:

| Platform | CPU | BASIC | Assembler(s) | Emulator voor verificatie | Prioriteit |
|---|---|---|---|---|---|
| C64 | 6510 | V2 | Kick Assembler 5.x, ca65 (cc65), ACME, 64tass? | VICE `x64sc` | **1** |
| C128 | 8502 (+Z80) | 7.0 | idem + C128-specifiek (MMU, VDC) | VICE `x128` | **1** |
| Plus/4 / C16 ("Commodore 4"?) | 7501/8501 | 3.5 | idem (TED i.p.v. VIC/SID) | VICE `xplus4` | 2 |
| PET/CBM | 6502 | 1.0/2.0/4.0 | idem | VICE `xpet` | 2 |
| VIC-20? | 6502 | V2 | idem | VICE `xvic` | ? |
| Amiga | 68000+ | AmigaBASIC / ACE / Blitz? | vasm, Devpac, ASM-One? (+ C?) | vAmiga / FS-UAE / WinUAE | **3**: compleet andere wereld (68k, AmigaOS, custom chips, Kickstart-ROMs met licentiebeperking) |

**Machinecode vervalt (beslissing P5).** Het model richt zich op BASIC en assembler. VIC-20 valt buiten de scope, tenzij later anders besloten.

---

## 5. Dataset

### 5.1 Bronnen (met licentiestatus — verplicht per bron vastleggen)
| Categorie | Voorbeelden | Licentie-aandachtspunt |
|---|---|---|
| Eigen werk | 3 skillset-repos, dune64, GeosU64, overige eigen projecten | ✅ eigen. Wel een licentie kiezen bij publicatie |
| Open-source repos | GitHub-projecten met MIT/BSD/Apache/GPL-licentie (demos, games, libs), cc65-voorbeelden, KickAss-voorbeelden | GPL-code in trainingsdata is juridisch grijs → beleid vaststellen (vraag L3) |
| Kennisbanken | Codebase64-wiki, C64-Wiki, oude disk-magazines | Licentie per bron controleren |
| Handleidingen & boeken | C64 Programmer's Reference Guide, C128 System Guide, Mapping the C64/C128, Amiga ROM Kernel Manuals, Hardware Reference Manual | **Auteursrechtelijk beschermd**, ook als ze op archive.org staan. Voorstel: wel in lokale RAG (eigen gebruik), **niet** letterlijk in een publiek verspreide dataset. Juridisch advies bij twijfel |
| Synthetische data | Opgaven + oplossingen gegenereerd door een sterk model, gefilterd met onze verificatie | Controleer de gebruiksvoorwaarden van het genererende model/API (sommige verbieden het trainen van concurrerende modellen) |
| Disk-images (.d64/.prg) | CSDb, oude PD-collecties | Gedetokeniseerde BASIC/disassembly. Rechten vaak onduidelijk; disassembly van commerciële software uitsluiten |

### 5.2 Normalisatie
- **Encoding van PETSCII/stuurcodes:** één conventie kiezen en overal toepassen (vraag D2). Opties: de bestaande "lowercase-bron + `invert_case`"-conventie van bas2prg, `petcat`-stijl `{clr}{home}{red}`, of `chr$(147)`. **Moet consistent zijn met bas2prg en de checkers.**
- Tokenized `.prg` → tekst met `petcat` (VICE) of eigen detokenizer. Machinetaal → disassembly met labels (bijv. via `da65` met infofile) alleen als bron toegestaan is.
- Elke assembler-bron krijgt metadata: platform, assembler + versie, load-adres, of hij zelfstandig assembleert, en afhankelijkheden.
- Deduplicatie (exact + near-dup via MinHash), en strippen van grote binaire `.byte`-blokken (sprites, muziek) of vervangen door een placeholder: die leren het model niets en vreten tokens.

### 5.3 Formaten
1. **SFT/chat** (hoofdmoot): `system` (platform + dialect + regels kort) → `user` (opdracht) → `assistant` (uitleg + code-blok met juiste taal-tag). Optioneel met tool-call-traces: model roept checker aan → krijgt fout → verbetert. Dat leert het model de **verificatielus** te gebruiken.
2. **Continued pretraining** (optioneel, klein aandeel): ruwe broncode en eigen documentatie. Alleen als SFT-alleen onvoldoende blijkt.
3. **Regels → Q&A:** de "harde regels" en "praktijklessen" uit de skills omzetten in vraag/antwoord- en "vind de fout"-voorbeelden (bijv. `;`-commentaar in KickAss, `score` bevat `or`, BASIC V2 kent geen `else`).
4. **Negatieve voorbeelden:** foutieve code + checker-output + gecorrigeerde code.

### 5.4 Verificatiepijplijn (automatisch, per voorbeeld)
```text
code ─▶ juiste checker (--json) ─▶ 0 ERRORs?
     ─▶ bas2prg / KickAss / ca65+ld65 / ACME ─▶ exit 0?
     ─▶ VICE headless: x64sc -warp -limitcycles N -autostart prg
        (+ -exitscreenshot of remote monitor op poort 6510:
         geheugen/registers/schermgeheugen uitlezen)
     ─▶ verwacht resultaat? (scherm-RAM bevat tekst X, geen BRK/JAM, enz.)
     ─▶ ✅ in dataset   /   ❌ weg of naar "negatieve voorbeelden"
```
- Draai dit parallel (meerdere VICE-instanties) in Linux-containers. VICE heeft een headless build.
- Amiga: vAmiga/FS-UAE headless met een Kickstart-ROM. **Kickstart is niet vrij te verspreiden** → AROS-ROM als alternatief onderzoeken voor CI.

### 5.5 Omvang (indicatie)
Begin met **2.000–5.000 hoogwaardige, geverifieerde** SFT-voorbeelden per prioriteit-1-platform/taal. Kwaliteit telt meer dan kwantiteit. Splits vooraf een **vaste testset** af die nooit in training komt.

---

## 6. Training

### 6.0 Trainingspad: lokaal op Mac met MLX (beslissingen H1 + H2)
Er is geen NVIDIA-GPU en geen cloud. Training gebeurt dus op de Mac (≥ 128 GB) met **mlx-lm**:

```text
1. Qwen/Qwen3.8-27B (bf16, HF)  ──mlx_lm.convert -q──▶  4-bit MLX-trainingsbasis
2. mlx_lm.lora --model <4-bit> --train --data <jsonl> (QLoRA, grad-checkpoint)
3. mlx_lm.fuse --model <bf16 MLX> --adapter-path <adapter> --de-quantize?
       ▶ adapter samenvoegen met de bf16-basis (NIET met de 4-bit)
4. bf16 → HF-safetensors ─▶ llama.cpp convert_hf_to_gguf ─▶ llama-quantize Q4_K_M …
                         ─▶ mlx_lm.convert -q (4/8-bit MLX)
                         ─▶ mtplx forge (MTPLX-pack)
```

**Aandachtspunten voor de developer:**
- **Vision:** mlx-lm laadt de taal-trunk. Vision-ondersteuning zit in mlx-vlm. Gevolg: v1 wordt waarschijnlijk **tekst-only** (vraag M2 vervalt daarmee in de praktijk), tenzij de developer aantoont dat de vision-tower ongewijzigd mee kan in de GGUF (`mmproj` van het basismodel hergebruiken).
- **GatedDeltaNet-lagen:** controleren dat de mlx-lm-versie `qwen3_5` volledig ondersteunt voor training (forward én backward) en welke modules als LoRA-doel beschikbaar zijn.
- **Stap 3 → 4:** controleren dat de gefuseerde gewichten exact de HF-namen en -layout hebben die `convert_hf_to_gguf.py` verwacht. Zo niet, een kleine conversiestap schrijven en testen met een logits-vergelijking (bf16 MLX vs GGUF Q8_0 op dezelfde prompt).
- **Doorlooptijd:** 27B-training op een Mac is traag. De proefrun moet **tokens/seconde** meten en daaruit de duur van een volledige run berekenen (bijv. 5–20 M trainingstokens). Plan nachtelijke runs, zet energiebeheer en slaapstand uit, en sla regelmatig checkpoints op (`--save-every`).
- **Geheugen:** 4-bit trunk ≈ 15–17 GB plus activaties. Met 128 GB kunnen sequenties van 8K haalbaar zijn. Meten met `--max-seq-length` 2K/4K/8K.
- **Fallback** als de Mac-training te traag of onstabiel blijkt: de opdrachtgever opnieuw laten beslissen over beperkte cloud-inzet. Dit is geen eigen keuze van de developer.

1. **Proefrun** (dag 1): mlx-lm op ~200 voorbeelden, 2K context. Controleren: laadt de `qwen3_5`-arch, werkt het chat-template, gaat de loss omlaag, en blijft vision bevroren.
2. **Hyperparameters (startpunt):** LoRA rank 16–64, alpha = rank of 2×rank, op alle lineaire lagen van de taal-trunk (attention + MLP + GatedDeltaNet-projecties: controleren welke modules Unsloth ondersteunt), LR 1e-4 – 2e-4, 1–3 epochs, cosine schedule, max seq 4–8K. Loss alleen op de assistant-turns.
3. **Behoud van algemene kennis:** meng 10–20% algemene code- en chatdata erdoor om *catastrophic forgetting* te beperken. Anders kan het model bijvoorbeeld slechter Nederlands of Python gaan schrijven.
4. **Thinking-modus:** zie vraag M4. Als we geen redeneersporen hebben, trainen met thinking uit, of korte zelfgeschreven redeneringen toevoegen.
5. **Merge:** adapter + **bf16**-basis → `Commodore3.8-27B` (safetensors). Daarna kwantiseren.
6. **Kwantisatie:** llama.cpp `convert_hf_to_gguf.py` + `llama-quantize` (Q4_K_M, Q5_K_M, Q6_K, Q8_0), eventueel met een **imatrix** op Commodore-code. Dat verbetert juist Q4 voor ons domein. MLX: `mlx_lm.convert -q --q-bits 4` en 8. MTPLX: `mtplx forge` vanaf het bf16-checkpoint.

---

## 7. Evaluatie ("Commodore-Eval")

- **Benchmark-set:** ±50–100 opgaven per platform/taal, met automatische test (zie §5.4). Bijvoorbeeld: "toon border-kleurcyclus", "IRQ-raster-split op regel 100", "sprite met joystick in poort 2", "BASIC 7.0 `SOUND`-melodie", "PET: tekst in 80 kolommen".
- **Metrieken:** % checker-schoon, % assembleert/tokenized, % draait correct in emulator (pass@1, pass@5), aantal gehallucineerde instructies of keywords, en latency (tok/s per runtime).
- **Vergelijk altijd vier varianten:**
  1. Qwen3.8-27B kaal
  2. Qwen3.8-27B + skill-prompt + RAG + checker-loop
  3. Commodore3.8 kaal
  4. Commodore3.8 + tools
- **Regressietests:** algemene vaardigheden (een kleine set gewone code- en Nederlandstalige vragen).
- **Q4 vs bf16:** meten hoeveel kwaliteit de kwantisatie kost op onze eigen benchmark.

---

## 8. Naamgeving, licentie en merkrecht

- **Apache-2.0 verplichtingen:** LICENSE meeleveren, de NOTICE van Qwen behouden, duidelijk vermelden dat het een afgeleide is ("Commodore3.8-27B is a fine-tune of Qwen/Qwen3.8-27B") en welke wijzigingen er zijn gedaan. Hernoemen is toegestaan.
- **⚠️ "Commodore" is een geregistreerd en actief gebruikt handelsmerk**, net als "Amiga" (andere eigenaar). Een publiek model en product onder de naam "Commodore3.8" kan een merkinbreuk zijn of de indruk van een officieel product wekken. **Advies:** juridisch laten toetsen of toestemming vragen aan de merkhouder. Houd anders een neutrale naam achter de hand (zie vraag N1), bijvoorbeeld "PETSCII-27B", "Breadbin-27B" of "Retro6502-27B", met beschrijvend "for Commodore 8-bit and Amiga development".
- **Model card** (HF) bevat: basismodel, datasetbeschrijving en licenties, trainingsrecept, evaluatie, bekende beperkingen, en een disclaimer "not affiliated with Commodore".
- **Dataset:** apart publiceren (of niet), met licentie per bron.

---

## 9. Distributie

| Artefact | Waar | Voor wie |
|---|---|---|
| `Commodore3.8-27B` (bf16 safetensors, ~54 GB) | Hugging Face | Wie zelf wil kwantiseren of verder trainen |
| `Commodore3.8-27B-GGUF` (Q4_K_M, Q5_K_M, Q6_K, Q8_0 [+ mmproj]) | Hugging Face | LM Studio, llama.cpp, Ollama |
| `Commodore3.8-27B-MLX-4bit/8bit` | Hugging Face | LM Studio (Mac), mlx-lm |
| `Commodore3.8-27B-MTPLX` (Forge-pack) | Hugging Face | MTPLX op Mac |
| Ollama-model + `Modelfile` (template, stop tokens, `num_ctx`, systeemprompt, parameters) | ollama.com/<user>/… | `ollama run …` |
| LoRA-adapter apart (~0,2–1 GB) | Hugging Face | Wie de basis al heeft |
| Engine-app (zie §10) | GitHub Releases | Eindgebruikers |

Elke release krijgt een versie (`v1.0`), SHA-256-checksums, een changelog en evaluatiecijfers.

---

## 10. Eigen AI-engine ("meeleveren")

### 10.1 Opties
| Optie | Beschrijving | Voor | Tegen |
|---|---|---|---|
| **A. Wrapper rond llama.cpp (`llama-server`)** | Eigen app (bijv. Tauri/Electron of Python + web-UI) die een meegeleverde llama-server start met onze GGUF | Cross-platform (Win/Linux/Mac), CUDA/Vulkan/Metal, MIT-licentie | Zelf UI en updates bouwen |
| **B. MTPLX als Mac-backend** | Op Mac MTPLX gebruiken (Apache-2.0, API-compatibel) | Snelste Mac-inference | Alleen Mac |
| **C. Geen eigen runtime, wel eigen "agent-laag"** | Alleen een **tool/MCP-server** leveren (checkers, assemblers, VICE, RAG); de gebruiker draait het model in LM Studio, Ollama of MTPLX | Minste werk, sluit aan op bestaande runtimes (LM Studio en veel clients ondersteunen MCP) | Minder "all-in-one" |
| **D. Combinatie (advies)** | **A** op Windows/Linux, **B** op Mac, en **C** als gedeelde tool-laag die ook los werkt | Beste van alles | Meeste werk |

### 10.2 Functionele eisen (voorstel, te bevestigen)
- Model kiezen, downloaden en starten (detecteert hardware → Q4/Q5/Q8 of MLX/MTPLX).
- Chat- en editor-UI met projectmap. Codeblokken direct als `.bas`/`.asm`/`.s` opslaan.
- **Tool-loop:** het model roept zelf `check`, `build`, `run_in_vice`, `screenshot` en `read_memory` aan. Fouten gaan terug naar het model tot alles groen is (max. N iteraties).
- RAG over handleidingen die de gebruiker zelf toevoegt (PDF/TXT), met lokale embeddings.
- Toolchain-beheer: paden naar Java/KickAss, cc65, ACME, VICE en Amiga-emulator (zoals de `[1] CONFIG` in `build.bat`), of meegeleverde portable versies (licenties checken: VICE is GPL, KickAss is freeware maar niet vrij te herdistribueren?, cc65 is zlib).
- Export naar `.prg`, `.d64`/`.d71`/`.d81` (c1541), en Amiga `.adf`/hunk-executable.
- OpenAI-compatibele API, zodat ook Cline, Continue en Claude Code-achtige clients het model kunnen gebruiken.
- Volledig offline te gebruiken na de download.

---

## 11. Fasering (voorstel)

| Fase | Inhoud | Opleverbaar |
|---|---|---|
| 0 | Vragen beantwoorden, hardware en budget vastleggen, licentie- en merkcheck | Ingevulde §12 |
| 1 | Baseline-eval: Qwen3.8-27B + skills + checkers op een eerste testset (C64 BASIC, C128 BASIC, C64 KickAss) | Benchmark + cijfers |
| 2 | Datapijplijn + verificatie (VICE headless); checkers uniformeren (`--json`) | Dataset v0.1 |
| 3 | Proef-fine-tune op de Mac (MLX, C64/C128), doorlooptijd meten, eval vs baseline | Adapter v0.1 + rapport (incl. tok/s en geschatte duur volledige run) |
| 4 | Release-pijplijn: merge → GGUF/MLX/Forge, test in LM Studio/Ollama/llama.cpp/MTPLX | Release v0.1 (privé) |
| 5 | Tool/MCP-laag + eenvoudige engine-app | Engine v0.1 |
| 6 | Data + verificatie voor Plus/4/C16 en PET (VICE `xplus4`, `xpet`) | Dataset v0.2 |
| 7 | Data + verificatie voor Amiga (68k, emulator headless op Mac) | Dataset v0.3 |
| 8 | Eén gecombineerde trainingsrun over alle platformen, eval per platform | Release-candidate v1.0 |
| 9 | Publicatie: model cards, dataset (eigen en vrije delen), website/docs | Publieke v1.0 |

Omdat alle platformen in v1 moeten (beslissing P2) maar de training lokaal en traag is, worden de tussenruns (fase 3) klein gehouden. Pas in fase 8 komt één grote run. Als Amiga de release te lang ophoudt, legt de developer dat als keuze terug bij de opdrachtgever.

---

## 12. Open vragen voor de opdrachtgever

> Vul de antwoorden in onder elke vraag. Vragen met ⭐ zijn blokkerend voor de start.

### Doel & scope
- ⭐ **D1.** Wat is het belangrijkste doel: (a) je eigen productiviteit, (b) een publiek model voor de community, (c) een commercieel product? Bepaalt licentie, naam en databeleid.
  - ✅ **Antwoord (27-10-2026):** Publiek en gratis model voor de retro-community.
- ⭐ **D2.** Welke PETSCII/stuurcode-notatie in BASIC-bron is de standaard: de bestaande lowercase + `invert_case`-conventie, `petcat`-stijl `{clr}`, of `chr$(…)`?
  - ✅ **Antwoord (27-10-2026):** `chr$(…)`, bijv. `print chr$(147)`.
- **D3.** Moet het model ook **uitleggen** (tutorials, commentaar in het Nederlands) of vooral **code schrijven**?
- **D4.** Moet het model bestaande code kunnen **debuggen, refactoren en disassembleren**, of alleen nieuwe code schrijven?
- **D5.** Is ondersteuning van **C (cc65, vbcc voor Amiga)** gewenst, of strikt BASIC + assembler + machinetaal?

### Platformen
- ⭐ **P1.** "Commodore 4": bedoel je de **Plus/4** (en daarmee ook C16/C116)? Of iets anders?
  - ✅ **Antwoord (27-10-2026):** Plus/4 + C16/C116 (TED, BASIC 3.5).
- ⭐ **P2.** Volgorde van prioriteit van de platformen? Voorstel: C64 = C128 > Plus/4 > PET > Amiga.
  - ✅ **Antwoord (27-10-2026):** Alle platformen in v1: C64, C128, Plus/4/C16, PET én Amiga. Interne volgorde zie §11.
- **P3.** Ook **VIC-20**, **C65/MEGA65**, **CBM-II (B-serie)** en **C64 Ultimate / Ultimate 64**-specifieke features (REU, Ultimate Command Interface)?
- **P4.** Welke PET-modellen en BASIC-versies (1.0/2.0/4.0; 40 of 80 kolommen)?
- ⭐ **P5.** Wat bedoel je precies met "machinecode": hex-invoer via een monitor, BASIC-`DATA`/`POKE`-loaders, of ruwe `.prg`-bytes?
  - ✅ **Antwoord (27-10-2026):** Machinecode vervalt; alleen BASIC en assembler.
- **P6.** Amiga: welke talen (68k-assembler, AmigaBASIC, Blitz Basic, ACE, C), welke assembler (vasm, Devpac, ASM-One/AsmPro), welke OS-versie (1.3 / 3.x), system-friendly of hardware-banging (copper, blitter)?
- **P7.** Welke assemblers voor 6502 moeten ondersteund worden: Kick Assembler, ca65, ACME, 64tass, DASM, Turbo Assembler (op de C64 zelf)?
- **P8.** Ook **C128 Z80-modus / CP/M** en 80-koloms VDC-assembler?
- **P9.** Ook muziek en graphics: SID-players (GoatTracker/SID-Wizard-formaat), sprite- en charset-editors, of alleen code?

### Data
- ⭐ **G1.** Welke eigen broncode mag erin? Alleen de 3 skillset-repos, of ook dune64, GeosU64 en andere (privé)projecten?
  - ✅ **Antwoord (27-10-2026):** Alle eigen Commodore-repos + dune64 + GeosU64 + de 3 skillsets (zie §1.1).
- ⭐ **G2.** Welke handleidingen/boeken heb je, in welk formaat (PDF-scan, OCR'd tekst), en weet je de rechtenstatus?
  - ✅ **Antwoord (27-10-2026):** Nog geen handleidingen in bezit; developer stelt een bronnenlijst met rechtenstatus op.
- **G3.** Heb je toegang tot grote collecties (CSDb-releases, disk-magazines, PD-disks)? Mogen die gedisassembleerd worden?
- **G4.** Mag synthetische data gegenereerd worden met een commercieel model (kosten + gebruiksvoorwaarden), of alleen met lokale modellen?
- **G5.** Wil je de **dataset** zelf ook publiceren?
- **G6.** Wie controleert steekproefsgewijs de kwaliteit? Hoeveel uur per week kun je zelf reviewen?
- **G7.** Moeten de bestaande skill-documenten leidend blijven, waarbij het model niets mag doen wat de skill verbiedt? Of mag het model van de skills afwijken als iets aantoonbaar werkt?

### Model
- ⭐ **M1.** Vast aan **Qwen3.8-27B**, of open voor een kleinere variant ernaast (bijv. Qwen3.5-4B/9B) voor gebruikers met minder hardware? Een 4B/9B-variant is goedkoper te trainen en draait op veel meer machines.
  - ✅ **Antwoord (27-10-2026):** Alleen Qwen3.8-27B, geen kleinere variant.
- **M2.** Vision behouden (bijv. een screenshot van een C64-scherm laten analyseren of een sprite uit een plaatje halen)? Of tekst-only uitbrengen (kleiner, eenvoudiger)?
- **M3.** Welke quants wil je naast Q4_K_M uitbrengen (Q5/Q6/Q8, MLX 4/8-bit)?
- **M4.** Thinking/reasoning-modus: aan laten (trager, mogelijk beter in assembler) of standaard uit?
- **M5.** Contextlengte die je eindgebruikers wilt garanderen (8K / 32K / 128K)?
- **M6.** Taal van het model: Engels, Nederlands of beide (trainingsdata in beide talen)?

### Hardware & budget
- ⭐ **H1.** Welke hardware heb je zelf? GPU-type + VRAM, systeem-RAM, en welke Mac (chip + unified memory) als je die hebt?
  - ✅ **Antwoord (27-10-2026):** Mac Apple Silicon met ≥ 128 GB unified memory (geen NVIDIA-GPU).
- ⭐ **H2.** Budget voor cloud-GPU's (eenmalig en per iteratie)? Is het goed als we op H100/H200 bij RunPod, Lambda of Modal trainen?
  - ✅ **Antwoord (27-10-2026):** Geen cloud; alles lokaal op de Mac.
- **H3.** Wat is de minimale hardware die een *eindgebruiker* moet hebben (bijv. "24 GB GPU of 32 GB Mac")?

### Engine/app
- ⭐ **E1.** Welke van de opties A/B/C/D uit §10.1 heeft je voorkeur?
  - ✅ **Antwoord (27-10-2026):** Optie D (combinatie).
- **E2.** Doelplatformen voor de app: Windows, macOS, Linux?
- **E3.** Moet de app de toolchains (VICE, KickAss, cc65, ACME, Amiga-emulator) **meeleveren** of moet de gebruiker die zelf installeren? Let op: herdistributielicenties.
- **E4.** Gewenste UI: eigen IDE-achtige editor, chat-venster, VS Code-extensie, of alleen een API/MCP-server?
- **E5.** Moet de engine ook naar **echte hardware** kunnen sturen (bijv. Ultimate 64/C64 Ultimate via het netwerk-REST-API, 1541Ultimate, Kung Fu Flash, SD2IEC)?
- **E6.** Naam van de engine? Open-source (welke licentie) of gesloten?
- **E7.** Updates: automatische modelupdates via Hugging Face, of handmatig?

### Naam & juridisch
- ⭐ **N1.** Ben je je bewust van het merkrecht op "Commodore" en "Amiga"? Wil je toestemming vragen of juridisch advies inwinnen? Of kiezen we een neutrale naam (met "for Commodore" als beschrijving)?
  - ✅ **Antwoord (27-10-2026):** Naam Commodore3.8 blijft; merkrisico bewust geaccepteerd. Disclaimer verplicht.
- **N2.** Onder welke naam/organisatie publiceer je (persoonlijk HF-account `mfidder2026`, een organisatie, fremen.app)?
- **N3.** Licentie voor eigen werk (skills, checkers, engine, dataset)?

### Planning & samenwerking
- **S1.** Gewenste deadline voor een eerste bruikbare versie?
- **S2.** Hoe werkt de developer: via GitHub-issues/PR's op een nieuw repo (bijv. `mfidder2026/commodore38`)? Wie heeft schrijfrechten?
- **S3.** Moet alles reproduceerbaar zijn (vaste seeds, gepinde versies, scripts in repo)? Advies: ja.

---

## 13. Risico's

| Risico | Kans | Impact | Mitigatie |
|---|---|---|---|
| Fine-tune verslaat de baseline (base + skills + tools) niet | Middel | Hoog | Baseline eerst meten (fase 1). Desnoods alleen de engine + RAG uitbrengen |
| Te weinig geverifieerde data voor PET/Plus/4/Amiga | Hoog | Middel | Synthetisch genereren + verificatie. Gefaseerd uitbreiden |
| Runtime-incompatibiliteit (`qwen35`-arch in Ollama/LM Studio) | Middel | Hoog | Vroeg testen in fase 4. Minimale versies documenteren |
| Merkrecht "Commodore"/"Amiga" | Middel | Hoog | Juridische toets. Alternatieve naam klaar hebben |
| Auteursrecht op handleidingen/boeken in dataset | Middel | Hoog | Alleen in lokale RAG. Niet in de gepubliceerde dataset |
| Catastrophic forgetting (algemene vaardigheden achteruit) | Middel | Middel | Algemene data bijmengen. Regressie-eval |
| Q4-kwantisatie kost veel domeinkwaliteit | Laag-middel | Middel | imatrix op Commodore-code. Q5/Q6 aanbieden |
| MTP-snelheid valt weg na fine-tune | Hoog (zonder Forge) | Laag-middel | MTPLX Forge gebruiken. Forge meet zelf of het helpt |
| Lokale Mac-training te traag voor de volle scope (geen cloud) | Hoog | Hoog | Doorlooptijd meten in fase 3. Data compact houden (kwaliteit > kwantiteit). Desnoods terug naar de opdrachtgever voor een besluit over cloud |
| mlx-lm-training van `qwen3_5` (GatedDeltaNet) onvolledig of buggy | Middel | Hoog | Proefrun op dag 1. mlx-lm-versie pinnen. Logits-vergelijking na fuse/convert |
| Weinig eigen code voor C128-asm, Plus/4, PET en Amiga | Hoog | Middel | Synthetisch genereren + streng verifiëren. Open-source bronnen met vrije licentie |
| Eigen ports van bestaande IP (c64red, commodore_keen, dune64) in publieke data | Middel | Middel | Alleen eigen code. Assets en geporte originele logica eruit. Per repo beoordelen |

---

## 14. Definition of Done voor v1.0

- [ ] Commodore-Eval toont statistisch duidelijke winst t.o.v. baseline op prioriteit-1-platforms
- [ ] GGUF Q4_K_M draait aantoonbaar in LM Studio, Ollama en llama.cpp (versies gedocumenteerd)
- [ ] MLX- en MTPLX-pack draaien op Mac; Forge-rapport gepubliceerd
- [ ] Model card met herkomst, licenties, eval en beperkingen
- [ ] Engine v1: model starten, tool-loop met checker + assembler + VICE, RAG
- [ ] Alle trainings- en build-scripts reproduceerbaar in de repo
- [ ] Naam- en licentiekwesties afgehandeld

---

## Bronnen
- Qwen3.8-27B modelkaart en metadata: https://huggingface.co/Qwen/Qwen3.8-27B
- MTPLX: https://github.com/youssofal/MTPLX · https://mtplx.com
- Unsloth Qwen3.8-docs: https://unsloth.ai/docs/models/qwen3.8
- GGUF-quants: https://huggingface.co/bartowski/Qwen3.8-27B-GGUF
- Secundair (niet officieel, verifiëren): https://www.yottalabs.ai/post/how-to-run-qwen-3-8-27b-locally-ollama-gguf-single-gpu-2026 · https://www.yottalabs.ai/post/how-to-fine-tune-qwen-3-8-27b-with-unsloth-2026 · https://acecloud.ai/blog/qwen3-8-27b-guide/ · https://gist.github.com/ryan4yin/19db9fa44972c5735c1d181e8888d4fe
- Kev (onderzocht, niet geschikt): https://github.com/jaredpalmer/kev
- Eigen repos: https://github.com/mfidder2026/c64_kickass_ai_skillset · https://github.com/mfidder2026/c128_basic_ai_skillset · https://github.com/mfidder2026/c64_basic_ai_skillset
