# Instalacja i budowanie zrodel beta

Wersja zrodel: **0.2.0-beta.1**. Zbudowano lokalne kandydaty, ale nie
opublikowano odpowiadajacego im Flatpaka. Publikacja zrodel nie oznacza
wydania binarnego. **P0 powtorzen pozostaje OPEN**, podobnie jak przeglad
redystrybucji: [REDISTRIBUTION](REDISTRIBUTION.md).

## Swiezy build lokalnego kandydata

Pelna procedura: [FRESH_BUILD](FRESH_BUILD.md).
Stan i bramki: [RELEASE_PREPARATION](RELEASE_PREPARATION.md).

Wymagane: Linux x86_64, Python 3.13, git, tar/xz, Flatpak, flatpak-builder,
AppStream z Compose, elfutils i debugedit. Instalacja **uzytkownika** Flatpak musi
zawierac GNOME SDK/Platform 49 i rozszerzenie Rust stable 25.08 z dokladnymi
commitami zapisanymi w `flatpak/sdk-lock.json`. Sama nazwa galezi nie wystarcza.
Potrzebne sa oryginalne pliki wlasciciela glosu Voidek w zewnetrznym katalogu:
`voidek-pl-e991.onnx` i `voidek-pl-e991.onnx.json`; hashe sa sprawdzane.
Nie kopiuj komponentow ani runtime z istniejacej instalacji.

Z katalogu repozytorium, podajac wlasne absolutne sciezki:

```sh
sh scripts/build-fresh.sh /absolute/new/work-directory /absolute/owner-input
```

Katalog roboczy nie moze istniec. Skrypt pobiera przypiete wejscia, przygotowuje
nowe cache npm/Cargo, buduje przez flatpak-builder, wykonuje offline smoke test
w Platform i zapisuje `payload-inventory.json`. Zawiera rowniez niezacommitowane
zmiany zrodel; sam HEAD nie identyfikuje brudnego kandydata. Zachowaj snapshot.
Pobieranie wymaga sieci; kompilacja uzywa przygotowanych wejsc offline.

`scripts/build.sh`, `scripts/build-flatpak.sh` i
`scripts/prepare-quickmt-runtime.sh` deleguja do tej samej procedury i przyjmuja
te same argumenty. Stary `.runtime`, `target/release` i `.tools/quickmt-python`
nie sa wejsciami swiezego buildu. Archiwum `scripts/legacy-snapshot/` nie jest
procedura instalacji. `scripts/reinstall.sh` jest celowo zablokowany na tym etapie.

## Instalacja

Nie ma obecnie publicznego pakietu do instalacji. Swiezy build tworzy lokalny
katalog `build`, nie eksportuje bundla i niczego nie instaluje.
Nie uruchamiaj historycznych komend instalacji starego pakietu jako biezacego wydania.
Prywatny test na osobnym koncie opisuje [P0_ARCH_ACCEPTANCE](P0_ARCH_ACCEPTANCE.md);
wymaga osobno dostarczonego, zidentyfikowanego pakietu. Nie kasuj danych uzytkownika.

## Pierwsze uruchomienie po przygotowaniu instalacji testowej

1. Otworz **Komponenty**. Dla EN -> PL zainstaluj **QuickMT English to Polish (CPU)**,
   okolo 385 MiB. Model nie jest dolaczany do Flatpaka. Siec jest potrzebna do
   pobrania/naprawy, nie do pozniejszej inferencji.
2. Sprawdz OCR i glos Voidek. Panel umozliwia weryfikacje, naprawe, anulowanie
   pobierania i usuwanie komponentow.
3. Wybierz zrodlo przez portal i zaznacz obszar widocznych, kontrastowych napisow.
4. Wybierz polskie napisy lub tlumaczenie angielskich na polski i uruchom czytanie.
   Pauza odrzuca nieodtworzone zadania; wznowienie nie przywraca starej kolejki.

Brak QuickMT nie uruchamia chmury ani zastepczego translatora. Polskie napisy
i Szybki odczyt nie wymagaja translatora.

Komponent QuickMT uzywa
`$XDG_DATA_HOME/narratorverse/narrator/components/translation.quickmt-en-pl`;
bez absolutnego `XDG_DATA_HOME` baza jest `~/.local/share`. Flatpak ustawia wlasne
katalogi aplikacji. Nie wskazuj recznie modelu; korzystaj z panelu Komponenty.
Migracja profili nie usuwa danych dawnych eksperymentow; ich cache nie jest
traktowany jako tlumaczenia QuickMT.

## Kontrole zrodel

```sh
npm ci --no-audit --no-fund
npm run check
npm run test:ui
npm run build
```

`sh scripts/test.sh` jest pomocnikiem dla wczesniej przygotowanego lokalnego
srodowiska testowego Python/Qt w GNOME SDK, z pytest w `.tools/test-python` i
bibliotekami w `.runtime`. Nie przygotowuje tego srodowiska i nie jest wymogiem
ani etapem swiezego buildu. `sh scripts/check-source.sh` sprawdza zrodla/frontend,
ale nie testuje instalacji, portalu ani rzeczywistego audio.
