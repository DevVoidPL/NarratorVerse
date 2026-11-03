# Przygotowanie źródeł do Pull Request — 3 listopada 2026

## Zakres i Git

Repozytorium: `DevVoidPL/NarratorVerse`. Gałąź: `integration/quickmt-beta-20261103`.
Po `git fetch origin` publiczny `main` nadal wskazuje
`4e7553a4bca022cc09b85c196d3f083651ddb12c`; nie pojawiły się nowe commity
względem bazy integracji. Wykryto istniejący zdalny tag `v0.1.0`, nie utworzono go.
`ls-remote --heads` pokazał tylko `main`; integracja nie została wypchnięta.

Pierwotny lokalny commit `f714094ab86f1b8252f6497f3950662c740b91ec` zawierał
ścieżki komputera w raporcie i surową telemetrię benchmarku. Został zachowany
pod lokalną referencją `refs/local-audit/integration-before-source-cleanup`.
Na tej samej gałęzi przygotowano oczyszczony commit z rodzicem równym
publicznemu `main`. Stary commit nie należy do historii przeznaczonej do PR.
Nie zmieniono historii publicznej ani nie wykonano force push. Referencja
audytowa służy wyłącznie lokalnie; nie publikować jej przez `--mirror`.

Funkcjonalny zakres `f714094` zachowano: QuickMT, deduplikacja, rezerwacje FIFO,
obsługa błędów lifecycle, poprawka OCR `m`/`rn`, RapidOCR na CPU i integracja
komponentów. Przygotowanie źródeł nie zmienia algorytmu pipeline'u; zmienia
metadane wersji, przyszłą nazwę artefaktu, dokumentację i dodaje regresje.

Nie wykonano push, nowego tagu, release, instalacji ani budowy Flatpaka.
Nie modyfikowano oryginalnych katalogów deweloperskich i publicznej kopii.

## Wersja i dokumentacja

Przygotowano `0.2.0-beta.1`: kolejny minor po tagu `v0.1.0` ze względu na
zmianę domyślnego translatora i deduplikacji, jawnie oznaczony jako prerelease.
Spójność obejmuje `package.json`, oba wpisy aplikacji w `package-lock.json`,
`Cargo.toml`, wpis NarratorVerse w `Cargo.lock`, `tauri.conf.json`, backend
`APP_VERSION`, najnowszy wpis metainfo oraz przyszłą nazwę bundle.
Historyczne wersje zależności i wpis metainfo `0.1.0` nie zostały zmienione.

README opisuje działanie, oba silniki OCR, jedyny domyślny QuickMT EN → PL,
Pipera, import głosów, profile, balans, wymagania, prywatność i ograniczenia.
Zachowuje istniejącą konwencję polskiego tekstu ASCII wymaganą przez test UI.
Instrukcje budowania nie obiecują odtwarzalności kompletnego runtime.
Brak instrukcji instalacji starego translatora i eksperymentalnych launcherów.
Historyczne wzmianki w changelogu i testach migracji nie są ofertą drugiego silnika.

`RELEASE_NOTES.md` zawiera test manualny zgłoszony przez użytkownika: GTA V,
około 40 minut, RapidOCR, polskie napisy, tłumaczenie wyłączone,
zero zaobserwowanych powtórzeń. Nie podano dokładnej daty sesji ani pomiarów
RAM/FIFO/opóźnienia. Nie jest to test QuickMT, test automatyczny ani gwarancja.
Nie deklarujemy testu QuickMT w Batmanie w tej wersji.

## Kontrola prywatności

Przejrzano nazwy i zawartość całego publikowanego drzewa, nie tylko diff.
Skan obejmował prywatne klucze, znane formaty tokenów, przypisania haseł/sekretów,
dane uwierzytelniające w URL, lokalne ścieżki i adresy e-mail. Obejrzano publiczne
screenshoty oraz grafikę aplikacji; pliki PNG sprawdzono także pod kątem metadanych.
Sprawdzono historię commitów, która ma trafić do PR, oddzielnie od lokalnej
referencji audytowej.

W końcowym drzewie sprawdzono 188 plików (171 tekstowych, 17 PNG), a w historii
przeznaczonej do PR siedem commitów i 244 unikalne bloby. Nie wykryto wzorców
sekretów ani ścieżek konkretnego komputera. Surowa telemetria nie występuje
w żadnym commicie osiągalnym z oczyszczonej gałęzi.

Nie znaleziono aktywnych sekretów ani danych profili/kont w publikowanym drzewie.
Zachowane adresy autorów w publicznej historii Git i upstream NOTICE są atrybucją,
nie nowymi danymi użytkownika. `128x128@2x.png` jest nazwą ikony, nie adresem e-mail.
Publiczne screenshoty przedstawiają formularze aplikacji bez danych kont.
Z bieżących kopii usunięto tekstowe metadane pozycji okna (`logicalX/Y`),
bez zmiany pikseli. W grafice źródłowej zachowano C2PA z informacją o generowaniu
obrazu i publicznymi certyfikatami wystawcy; nie znaleziono tam danych kont.
Starsze screenshoty pozostają w już publicznej historii `main`, której nie
przepisywano. Nie obiecujemy usunięcia publicznych danych z historii upstream.
Małe TSV to opisane, oczyszczone fixture'y regresji OCR, nie pełne logi sesji.

Usunięto z publikowanego drzewa surowy `docs/performance-balanced.json`, ale
**plik pozostaje na dysku**, ignorowany przez Git. Zagregowane wyniki, CPU
potrzebny do interpretacji benchmarku i ograniczenia zachowano w historycznym
raporcie. Z dokumentacji usunięto ścieżki konkretnego komputera.
Nie kasowano modeli, stagingów, runtime ani plików źródłowych.

`.gitignore` jest śledzony. Reguły wykluczają modele, runtime, narzędzia, cache,
profile, `.private`, referencje, `node_modules`, `dist`, stagingi i artefakty.
Przetestowano także rzeczywistą zawartość archiwum Git.
Nie był dostępny gitleaks ani trufflehog; wykonano własny skan wzorców i przegląd.
To nie gwarantuje wykrycia każdego możliwego sekretu.

## Testy wykonane na przygotowanych źródłach

| Kontrola | Wynik |
|---|---|
| Pełny backend: `sh scripts/test.sh` | **892 passed, 1 xfailed** |
| Wydzielony zestaw komponentów, QuickMT, FIFO/dedup, `m`/`rn`, pakowania | **170 passed**; to podzbiór pełnego zestawu, nie dodatkowe 170 testów |
| Nowe regresje wersji/nazwy artefaktu | Najpierw **2 failed, 3 passed**, po poprawce **5 passed** |
| Kontrole źródeł: `sh scripts/check-source.sh` | Python i shell poprawne, Svelte/TypeScript **0 błędów, 0 ostrzeżeń**, UI **8/8**, Vite build poprawny |
| Cargo metadata, `--locked --offline` | poprawne, aplikacja `0.2.0-beta.1` |
| Git archive z przygotowanego drzewa | test nieobecności lokalnych danych i surowej telemetrii poprawny |
| `git diff --check` | poprawne |

Zachowany xfail: Tesseract błędnie rozpoznaje testowy font pikselowy 5×7.
Nie obniżono asercji ani nie usunięto testów dla uzyskania zielonego wyniku.
Pierwsza kontrola frontendu wykryła znaki spoza ASCII w README; dostosowano
dokument, zachowując test. Testy nie zastępują sesji GUI/portalu.

Nie powtórzono pobierania modelu, inferencji na prawdziwym modelu, testu gry,
instalacji Flatpaka ani pełnego builda Rust. Historyczne wyniki tych kontroli
są wyraźnie oddzielone w `docs/INTEGRATION_REPORT.md`. Nie przebudowywano runtime.
Ponownie odczytano historyczny checkout OSTree: 7372 wpisy zgodne, a stary
bundle zachował SHA-256 `b9a48952e9759609c53a010df74179be5004b7592c7c19276ad1b93b2f37b2c5`.
Ten bundle nie odpowiada już bieżącym metadanym/dokumentacji i nie jest nowym wydaniem.

## Licencje i decyzja o PR

`licenses/NOTICE.md` i `docs/REDISTRIBUTION.md` rozdzielają źródła aplikacji
MIT od kopii bibliotek i modeli. Zachowano autorstwo, upstream NOTICE
SentencePiece, licencję i kartę Voidek oraz atrybucję QuickMT CC BY 4.0.
Przejrzano faktyczny inventory i lokalne licencje, a nie tylko nazwy pakietów.

**Źródła są przygotowane do Pull Request**, bez zgody na publikację binariów.
Wymagany jest zwykły przegląd PR; nie wykonano niezależnego review drugiej osoby
ani agenta (brak narzędzia delegacji). Obecne testy wykonano na przygotowanym
środowisku, nie na czystej maszynie odtwarzającej runtime ze źródeł.

**Flatpak nadal zablokowany**: Piper/espeak-ng GPL, licencje konkretnych modułów
Qt i third-party WebEngine, źródła LGPL/MPL, natywne biblioteki i brakujące notice,
sposób udostępnienia odpowiadających źródeł oraz ocena łączenia kodu z GPL.
Lista i rozróżnienie oferty źródeł od dostępu online są w `docs/REDISTRIBUTION.md`.
Nie wydano prawnej deklaracji zgodności ani nie zmieniono MIT aplikacji.

Decyzje właściciela: akceptacja numeru `0.2.0-beta.1`, osobna zgoda na push
konkretnej gałęzi i utworzenie PR; przed binariami wybór minimalnego runtime lub
uzupełnienia pełnego zestawu licencji/źródeł i potwierdzenie publicznej treści
zezwolenia Voidek. Potrzebne są też sesja z QuickMT i test słabszego CPU.