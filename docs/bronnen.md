# Bronnenlijst met rechtenstatus (beslissing G2)

Status per 27-10-2026. Regel: **alleen bronnen met status "vrij" of "eigen" mogen in de publieke dataset.**
Alles met "beschermd" of "te verifiëren" gaat hooguit in de **lokale RAG** van de gebruiker.
"Te verifiëren" betekent: de licentie is nog niet met de bron zelf gecontroleerd. Niet aannemen dat het vrij is.

| Bron | Soort | Platform | Rechtenstatus | Gebruik |
|---|---|---|---|---|
| c64_basic / c128_basic / c64_kickass skillsets (mfidder2026) | skills, checkers | C64, C128 | eigen (nog geen LICENSE-bestand, zie N3) | dataset + RAG + verificatie |
| Eigen game-repos (§1.1 implement.md) | broncode | C64 | eigen code. Assets van derden-IP strippen | dataset na per-repo review |
| cc65 (compiler, ca65/ld65, voorbeelden) | toolchain + code | 6502-familie | zlib (vrij) | tool + voorbeelden in dataset |
| VICE (emulator, petcat, c1541) | toolchain | alle 8-bit | GPL-2.0 | alleen als tool, niet als data |
| Kick Assembler (Mads Nielsen) | assembler + handleiding | C64 | freeware. Herdistributie en hergebruik van handleidingtekst: te verifiëren | tool. Handleiding alleen RAG |
| ACME, 64tass | assemblers | 6502 | te verifiëren per project (open source) | tool |
| Codebase64 wiki | artikelen + code | C64 | te verifiëren (licentie per pagina/site) | RAG. Dataset pas na check |
| C64-Wiki | artikelen | C64 e.a. | te verifiëren | RAG |
| Commodore 64 Programmer's Reference Guide | handboek | C64 | beschermd | alleen lokale RAG |
| Commodore 128 Programmer's Reference Guide / System Guide | handboek | C128 | beschermd | alleen lokale RAG |
| Plus/4 en C16 gebruikershandleidingen | handboek | Plus/4, C16 | beschermd | alleen lokale RAG |
| PET/CBM gebruikershandleidingen | handboek | PET | beschermd | alleen lokale RAG |
| Mapping the Commodore 64 / 128 (Leemon, COMPUTE! Books) | boek | C64, C128 | beschermd | alleen lokale RAG |
| Amiga ROM Kernel Reference Manuals, Hardware Reference Manual | handboek | Amiga | beschermd | alleen lokale RAG |
| AROS (ROM-vervanger) | OS/ROM | Amiga | AROS Public License, te verifiëren voor CI-gebruik | headless Amiga-verificatie zonder Kickstart |
| vasm / vlink | assembler | Amiga 68k | te verifiëren (eigen licentie, beperkingen voor commercieel gebruik) | tool |
| GitHub-repos met MIT/BSD/Apache-licentie | broncode | alle | vrij, per repo vastleggen | dataset |
| GitHub-repos met GPL | broncode | alle | beleid nog open (vraag L3) | voorlopig niet in de dataset |
| CSDb / disk-magazines / PD-disks | binaries | C64 e.a. | meestal onduidelijk | niet in de dataset (vraag G3) |

## Volgende stappen
1. Per "te verifiëren"-rij de licentietekst bij de bron opzoeken en hier vastleggen, met URL en datum.
2. De opdrachtgever bepaalt N3 (licentie eigen werk) en L3 (GPL-beleid).
3. Handleidingen die de opdrachtgever zelf aanschaft of scant, komen in `rag/` (niet in git).
