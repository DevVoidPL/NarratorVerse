# Raport integracji — 3 listopada 2026

Dokument historyczny: dotyczy źródeł i lokalnego bundle przy `f714094`, przed
przygotowaniem `0.2.0-beta.1`. Aktualny stan publikacji źródeł i test manualny
użytkownika opisują `docs/SOURCE_PUBLICATION.md` i `RELEASE_NOTES.md`.

## Status i granice

**Integracja funkcjonalna i lokalny kandydat beta przygotowane. Nie oznacza
to gotowosci do publicznej publikacji.** Blokady: niezamkniete obowiazki
redystrybucji runtime oraz brak dluzszej sesji w grze i slabszego CPU.
Nie wykonano push, tagu, publikacji ani instalacji do istniejacego Flatpaka.

Katalog roboczy: osobny klon integracyjny.
Galaz: `integration/quickmt-beta-20261103`.
Baza publiczna: `4e7553a4bca022cc09b85c196d3f083651ddb12c`.
Remote main sprawdzony przez ls-remote, fetch wykonany tylko w nowym klonie.
Klon nie korzysta z hardlinkow obiektow ani shared object store.

Oba oryginalne katalogi pozostaly nietkniete. Koncowo sprawdzono hashe
99 importowanych plikow deweloperskich oraz czyste Git status publicznej
kopii. Lista importu i pierwotne hashe: `docs/integration-import.md`.
Trzy publiczne screenshoty pozostaly. Ignore rules obejmuja modele,
runtime, narzedzia, dane prywatne i buildy; `.gitignore` jest sledzony.

## 1. Polaczona deduplikacja

Wspolny `PhraseDeduplicator` zachowuje epizod i jego kanoniczny tekst oraz
warianty. Dodano rezerwacje indeksowane request ID, od przyjecia dialogu
do startu audio albo terminalnego odrzucenia. Historia domyslnie wynosi
4500 ms od audio-start, nie od akceptacji i nie od konca mowy.

Przyjecie innej kwestii i znikniecie napisow nie usuwaja historii mowy.
Powtorka w kolejce jest blokowana takze przed startem audio. Pauza zwalnia
nieodtworzone zadania, zachowujac historie rozpoczetej mowy; nowa sesja
tworzy nowy stan. Stare callbacki sa filtrowane generacja i progiem ID.

Przekazanie kolejce nie jest Latest Wins. Zachowano osiem oczekujacych
kwestii tekstowych i osiem audio oraz dotychczasowe usuwanie najstarszego
oczekujacego przy przepelnieniu. Aktualna kwestia nie jest przerywana przez
nowy napis. Przed-OCR zastepowanie klatek pozostaje oddzielne.

Regresje obejmuja A/A, A/B/A w historii i po jej granicy, A oczekujace/B/A,
A/B/C/duplikat B, overflow, wyjatek/anulowanie translacji i TTS, odmowe
przyjecia przez executor, oczekiwanie audio, pauze i reset sesji. Zachowano
pelny tekst -> uciety -> pelny, liczby, negacje, rozmowcow i OCR m/rn.
Wykryto i naprawiono gate OCR, ktory mogl zatrzaskiwac napis odrzucony przez
historie nawet po jej wygasnieciu.

Najwazniejsze pliki:

- `backend/game_optimization_linux/services/narrator_pipeline.py`
- `backend/game_optimization_linux/services/narrator_audio.py`
- `backend/narratorverse/pipeline.py`, `backend/narratorverse/main.py`
- `tests/test_narrator_unified_dedup.py`
- zachowane i zaktualizowane testy epizodow, dialogow, garbage i m/rn.

## 2. QuickMT i standardowy instalator

Jedyny domyslny lokalny translator EN -> PL: QuickMT, CTranslate2 CPU,
bez pobran przy starcie, bez chmury i bez fallbacku. Cache zachowany, provider
ma identyfikator z rewizja i ustawieniami dekodowania. Stare profile
atomowo migruja identyfikator translatora, pozostawiajac inne wartosci.

Model `quickmt/quickmt-en-pl`, rewizja
`6209580ce1fe525214f29fc39725007b73410109`, CC BY 4.0. Szesc plikow ma
przypiete SHA-256. Trzy male JSON-y pobrano z przypietej rewizji,
policzono SHA-256 i porownano z wczesniejszymi pinami Git blob. Pelny realny
download przez instalator ponownie zweryfikowal wszystkie modelowe SHA-256.
Oryginalny README tez jest przypiety SHA-256 i zachowany z atrybucja.

Wspolna lokalizacja komponentu:
`$XDG_DATA_HOME/narratorverse/narrator/components/translation.quickmt-en-pl`.
Panel Komponenty otrzymuje model, licencje, atrybucje, rozmiar, statusy
i sumaryczny postep. Pobranie obejmuje 403609113 bajtow z README.
Weryfikacja/naprawa/usuwanie/anulowanie wykorzystuja istniejaca architekture.
Atomowy staging chroni poprzednia poprawna instalacje przy bledzie.

Argos provider i BPE usuniete; wspolny worker procesowy i engine CPU
pozostaly. Sacremoses/subword-nmt usuniete z niezaleznej kopii runtime.
RapidOCR, ONNX, Piper i ich wspolne zaleznosci zachowane.

Najwazniejsze pliki:

- `backend/narratorverse/quickmt{,_model,_worker,_download}.py`
- `backend/game_optimization_linux/services/narrator_translation{,_worker}.py`
- `backend/game_optimization_linux/services/narrator_components.py`
- `backend/game_optimization_linux/models/narrator.py`
- `backend/narratorverse/{components,main,profiles,runtime_checks}.py`
- `tests/test_quickmt_integration.py` i zachowane testy downloadera/workera.

## 3. Eksperymenty i pakowanie

Usuniete przelaczniki `NARRATORVERSE_EXPERIMENT_*`, wybor deduplikacji
i translatora, launchery run/build-quickmt oraz quickmt-setup/compare shell.
Zachowany prywatny trace diagnostyczny nie zmienia zachowania pipeline'u.
Narzedzie korpusowe obsluguje teraz tylko QuickMT. Reczne sciezki modelu
pozostaja w jawnych narzedziach deweloperskich jako fixture'y, nie w aplikacji.

Standardowy staging dolacza SentencePiece, ale nie wagi QuickMT ani Argosa.
Manifest Flatpaka znow uzywa allowlisty, nie calego workspace.
Offline probe w stagingu nie generuje bytecode. Wersja aplikacji 0.1.0
pozostaje bez samodzielnego nadawania numeru release.

Najwazniejsze pliki:

- `.gitignore`, `EXPERIMENTS.md`, `README.md`, `RELEASE_NOTES.md`
- `scripts/{stage-flatpak.py,build-flatpak.sh,test.sh,check-source.sh}`
- `scripts/{prepare-quickmt-runtime.sh,reinstall.sh,benchmark-beta.py}`
- `flatpak/io.github.DevVoidPL.NarratorVerse.json`
- `src/i18n.ts`: historia jednoznacznie opisana jako liczona od startu audio.

## 4. Wyniki walidacji

| Kontrola | Wynik |
|---|---|
| Backend w niezaleznym lokalnym runtime, pelny zestaw | **889 passed, 1 xfailed** |
| Xfail | zachowany problem Tesseracta z testowym fontem pikselowym 5x7 |
| Frontend node tests | **8/8** |
| Svelte/TypeScript | **0 errors, 0 warnings** |
| Vite production build | poprawny |
| Cargo release, locked, offline | poprawny |
| `git diff --check`, skladnia shell i Python | poprawne |
| Natywne importy RapidOCR/Piper/QuickMT | wszystkie poprawne |
| Realny download standardowym ComponentManager | poprawny, komplet SHA-256 i manifest |
| Inferencja QuickMT offline w SDK | poprawna |
| Inferencja QuickMT offline we wlasciwym stagingu | poprawna |
| Backend IPC, fresh XDG, bez sieci | ready/status/shutdown poprawne; model prawidlowo not_installed |
| Staging inventory | 7372 wpisy poprawne, 0 extra, 0 bytecode i zakazanych danych |
| Niezalezny import faktycznego bundle do prywatnego OSTree | 7372 wpisy poprawne, 0 extra |
| Instalacja do profilu uzytkownika i test GUI/portalu | **nie wykonano** |

Testy uruchamiano najpierw na czerwono dla nowych zachowan: dedup/history/
rezerwacje, QuickMT default/install/profile, staging oraz odmowy executora.
Nie usunieto testow OCR/FIFO dla uzyskania zielonego wyniku. Testy starego
tokenizera zostaly dostosowane do odpowiednika SentencePiece i zachowano
kontrakty workera, CPU, cache, dekodowania i cancel/close.

Review wykonano lokalnie na diff i testach. Nie byl to niezalezny review
drugiego agenta/osoby; nie bylo dostepnego narzedzia do uruchomienia reviewera.

## 5. Rzeczywisty pomiar CPU, nie test gry

Maszyna: AMD Ryzen 5 3600, 12 logicznych CPU, pelne affinity. Python 3.13.15,
CTranslate2 4.8.1, SentencePiece 0.2.1. Offline, profil balanced, bez cache,
499 par QuickMT + lokalny Piper/Voidek przez 180.14 s. Dane surowe:
lokalny `docs/performance-balanced.json`, wyłączony z publikowanych źródeł.
Pozostawiono tutaj zagregowane wyniki i identyfikację CPU potrzebną do
interpretacji pomiaru, bez surowej telemetrii konkretnego komputera.

| Pomiar | Mediana warm | p95 warm |
|---|---:|---:|
| QuickMT | 60.82 ms | 72.75 ms |
| Piper | 301.95 ms | 363.68 ms |

Mediana tekst -> gotowy PCM: 362.89 ms; p95 427.78 ms. Najwolniejszy pierwszy
cykl 2588.42 ms. Szczyt RSS QuickMT 463527936 bajtow (442.05 MiB), suma
RSS procesow 650977280 (620.82 MiB). Suma RSS podwojnie liczy mapowania
wspoldzielone; nie jest pomiarem unique memory.

Zuzycie CPU calej proby: okolo 154% jednego rdzenia (nie 154% calego CPU).
Mediana RSS QuickMT we wczesnym stabilnym wycinku 315019264 bajtow,
w ostatnich 10% 315146240. Brak znacznego wzrostu w tej krotkiej probie
nie dowodzi braku wycieku w dlugiej sesji.

Nie zmierzono faktycznego startu audio, OCR, portalu ani przyrostu kolejek
w grze. FIFO/overflow sa przetestowane deterministycznie, nie benchmarkiem
rzeczywistej rozgrywki. Nie zmierzono slabszego CPU. Trzy minuty providerow
nie sa dlugim soak testem gry. Tych ograniczen nie oznaczono jako zaliczone.

## 6. Artefakt i blokady publikacji

Plik lokalny:
`flatpak/artifacts/NarratorVerse-0.1.0-beta-integration-x86_64.flatpak`

SHA-256:
`b9a48952e9759609c53a010df74179be5004b7592c7c19276ad1b93b2f37b2c5`

Suma kontrolna:
`flatpak/artifacts/SHA256SUMS`.
Sprawdzona `sha256sum -c`. Bundle pozostaje poza Git, lokalny i niepodpisany.
Kod oraz dolaczone pliki stagingu sa zgodne z inventory; pozniejsze zmiany
w dokumentacji raportowej nie sa czescia payloadu aplikacji.

**Blokada redystrybucji:** faktyczny bundle zawiera m.in. Piper GPL, dodatkowe
moduly Qt Charts/DataVisualization/VirtualKeyboard/WebEngine, 76 sciezek
license/notice, ale nie kompletny zweryfikowany corresponding-source kit
i zestaw obowiazkow wszystkich zaleznosci. Opis w `docs/REDISTRIBUTION.md`.
Weryfikacja hasha nie usuwa tej blokady. Nie publikowac tego bundle jako
zatwierdzonej publicznej bety.

Przed publikacja wymagane: zamkniecie listy redystrybucji (lub odchudzenie
i ponowny test runtime), dluzsza sesja w grze z realnym audio/trace,
test slabszego CPU i niezalezny code review. Dopiero potem ponowny build
i nowa suma pakietu, bez automatycznej publikacji.