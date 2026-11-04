# Przygotowanie zrodel 0.2.0-beta.1

Stan na **4 listopada 2026**: przygotowanie publikacji zrodel, bez zgody na
wydanie binarne. Lokalny swiezy build zostal wykonany; nie jest publicznym
wydaniem i nie zamyka akceptacji P0 ani obowiazkow redystrybucji.

## Baza Git i zakres

Galaz `release/0.2.0-beta.1` ma baze
`b99bf5e3a630fef32e9a945afcf3051c17ce213c` (merge PR #1).
Zmiany przygotowawcze pozostaja w working tree; sam HEAD ich nie identyfikuje.
W tym etapie nie wykonujemy stagingu, commita, push, tagu ani GitHub Release.
Wersja zrodel pozostaje `0.2.0-beta.1`; data przygotowania nie jest data wydania.

## Wykonany swiezy build

Procedura: [FRESH_BUILD](FRESH_BUILD.md), skrot: [INSTALL](INSTALL.md).
Domyslne skrypty deleguja do `scripts/build-fresh.sh`. Manifest korzysta
z flatpak-builder, nie ze starego `.runtime`/`target/release` ani komponentow
skopiowanych z instalacji. Dawne skrypty sa nieaktywnym archiwum tekstowym
w `scripts/legacy-snapshot/`; `stage-flatpak.py` pozostaje kodem historycznym/testowym.

Przygotowano locki SDK/Platform/Rust, Node, Python oraz komponentow. Skrypt
sprawdza commity z `flatpak/sdk-lock.json`, pobiera zahashowane wejscia, tworzy
nowy snapshot zrodel i cache, vendoruje Cargo.lock i rozdziela pobieranie od
kompilacji offline. Tesseract/Leptonica sa budowane ze zrodel; czesc zaleznosci
natywnych pochodzi z Platform lub wheeli. To nie jest build wszystkich zaleznosci
ze zrodel ani dowod bitowej odtwarzalnosci.

Voidek wymaga osobno dostarczonych oryginalow o zgodnych hashach. QuickMT jest
pobierany osobno przez aplikacje i nie trafia do bundla. Wlasne glosy, profile
i cache nie sa wejsciami.

Historyczny kompletny przebieg `full-attempt-2` zakonczyl budowe, offline smoke
w Platform i inventory. Oddzielny kandydat `p0-attempt-1` zawiera pozniejsze
zmiany P0. Ich wynikow nie wolno utozsamiac. Logi, snapshoty, modele i pakiety
pozostaja prywatne, poza publikacja zrodel. Nie zmieniamy zachowanych dowodow.
Raport historyczny: [FINAL_VALIDATION](FINAL_VALIDATION.md), przeglad P0:
[P0_TERMINAL_REVIEW](P0_TERMINAL_REVIEW.md). Liczby w tych raportach opisuja
konkretne wczesniejsze przebiegi, nie biezaca walidacje publikacji.

## Bramki

| Obszar | Stan |
| --- | --- |
| Swiezy build | Zaimplementowany, lokalny pelny przebieg udokumentowany; bez automatycznej instalacji/eksportu |
| Przypiete wejscia | Locki i kontrola hashy/commitow; host builder/narzedzia i niezalezny rebuild nadal wymagaja dokumentacji/weryfikacji |
| Publikacja zrodel | Osobny przeglad zawartosci, prywatnosci, dokumentacji i testow; nie oznacza wydania binarnego |
| P0 powtorzen | **OPEN** — brak pelnej rzeczywistej akceptacji Arch/GTA capture -> OCR -> Piper -> PipeWire z JSONL |
| Licencje/source obligations | **OPEN** — pelna mapa payload -> notices/licencja/zrodla i wymagane materialy dla dystrybucji binarnej |
| GUI i instalacja | **OPEN** — czysta instalacja, portal, oba OCR, audio/ducking/restoration, aktualizacja i izolacja danych |
| QuickMT | Historycznie sprawdzono instalacje przez backend i inferencje offline z Piper/WAV; nie jest to test GUI, capture ani fizycznego audio |
| Artefakt wydania | **OPEN** — czysty release commit, identyfikacja payloadu, resolved manifest, logi, hashe i osobna decyzja o publikacji |

Historyczny test GTA z „0 powtorzen” nie zamyka P0. Przypadek `1508 -> 1515`
(„Rzecz jasna...”) pozostaje nierozstrzygniety: zaakceptowane teksty nie sa
identyczne, a obecna obsluga fragmentow wymaga co najmniej czterech slow.
Nie dodajemy spekulacyjnego filtra. OCR interfejsu ESC jest oczekiwany.
ASR pozostaje odlozone — bez implementacji ani dokumentu koncepcyjnego.

Akceptacja: [P0_ARCH_ACCEPTANCE](P0_ARCH_ACCEPTANCE.md).
Redystrybucja: [REDISTRIBUTION](REDISTRIBUTION.md).
Smoke test, wheel hash ani dynamiczne linkowanie nie zamykaja samodzielnie
obowiazkow dotyczacych zrodel i licencji. Otwarte bramki nie moga byc oznaczone
jako zamkniete przez sama publikacje kodu.
