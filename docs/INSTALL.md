# Instalacja i budowanie źródeł beta

Wersja źródeł: **0.2.0-beta.1**, bez tagu i wydania. Nie ma publicznego Flatpaka
odpowiadającego tym źródłom. Obowiązki przed dystrybucją binarną opisuje
`docs/REDISTRIBUTION.md`. Test manualny GTA V z wyłączonym tłumaczeniem
opisano w `RELEASE_NOTES.md`; nie zastępuje testu sesji z QuickMT.

## Lokalny pakiet

Tylko po świadomym przygotowaniu własnego lokalnego builda, w katalogu projektu:

```sh
sh -eu -c 'cd flatpak/artifacts; sha256sum -c SHA256SUMS'
flatpak install --user --bundle flatpak/artifacts/NarratorVerse-0.2.0-beta.1-x86_64.flatpak
flatpak run io.github.DevVoidPL.NarratorVerse
```

Powyższy nowy pakiet nie został zbudowany podczas przygotowania źródeł. Stary
lokalny `0.1.0-beta-integration` nie odpowiada bieżącej wersji źródeł.
Nie usuwaj katalogu danych przy aktualizacji. Instalacja/reinstalacja nie jest
wykonywana automatycznie przez agenta integracyjnego.

## Pierwsze uruchomienie

1. Otworz **Komponenty** i zainstaluj **QuickMT English to Polish (CPU)**.
   Pobranie to okolo 384.9 MiB. Siec potrzebna jest do instalacji/naprawy,
   nie do kolejnych tlumaczen. Postep jest sumaryczny dla calego komponentu.
2. Sprawdz dostepnosc OCR i glosu Voidek. Opcje weryfikacji, naprawy,
   anulowania pobrania i usuniecia modelu sa w tym samym panelu.
3. Wybierz zrodlo przez portal i potwierdz obszar napisow. Napisy musza byc
   widoczne na ekranie. Ustaw je mozliwie duze i kontrastowe.
4. Wybierz polskie napisy albo tlumaczenie angielskich na polski, nastepnie
   uruchom czytanie. Pauza zachowuje portal, ale odrzuca nieodtworzone zadania;
   wznowienie nie przywraca ich ze starej kolejki.

Brak QuickMT nie uruchamia zastępczego translatora ani chmury. Polskie napisy i Szybki odczyt
nie wymagaja translatora. Model QuickMT nie jest dolaczany do Flatpaka.

## Sciezki i aktualizacja profili

Komponent znajduje sie w
`$XDG_DATA_HOME/narratorverse/narrator/components/translation.quickmt-en-pl`.
Bez absolutnego `XDG_DATA_HOME` uzywany jest `~/.local/share`.
Flatpak ustawia te zmienne we wlasnym katalogu aplikacji. Nie wskazuj recznie
modelu; pobierz komponent w GUI.

Profile poprzedniej wersji sa atomowo aktualizowane do jedynego translatora
QuickMT. Identyfikatory cache sa rozdzielone, wiec wpisy starego translatora nie sa
traktowane jako tlumaczenia QuickMT. Dane dawnych eksperymentow nie sa
automatycznie przenoszone ani kasowane.

## Budowanie

Frontend można sprawdzić bez pełnego runtime:

```sh
npm ci --no-audit --no-fund
npm run check
npm run test:ui
npm run build
```

Do backendu i obecnego pakowania wymagane: Linux x86_64, Node/npm,
GNOME SDK/Platform 49, rozszerzenie Rust 25.08, pytest w `.tools/test-python` i
przygotowany lokalny snapshot `.runtime` oraz cztery komponenty z listy
w `scripts/stage-flatpak.py`. To nadal nie jest odtwarzalny build wszystkich
zaleznosci ze zrodel. Repozytorium nie dostarcza kompletnego sposobu odtworzenia
tego snapshotu; nie kopiuj go z nieznanych pakietów. `.tools`, runtime, modele
i artefakty nie trafiaja do Git. Poprzednia walidacja używała Node 22.22.0
i Pythona 3.13.

Kontrole istniejącego środowiska, bez budowy runtime i instalacji:

```sh
sh scripts/test.sh
sh scripts/check-source.sh
```

Dopiero przy świadomym lokalnym budowaniu aplikacji i pakietu:

```sh
sh scripts/prepare-quickmt-runtime.sh
sh scripts/build.sh
sh scripts/build-flatpak.sh
```

`prepare-quickmt-runtime.sh` instaluje tylko przypiety wheel SentencePiece do
izolowanego katalogu narzedzi budowania. Standardowy staging dolacza go do
runtime; nie ma juz osobnego wariantu `--quickmt`. Skrypt pakowania odmawia
nadpisania istniejacego stagingu; zachowaj poprzedni kandydat osobno.
Nazwa przyszłego artefaktu jest wyprowadzana z wersji `0.2.0-beta.1` zapisanej
w `package.json`. `scripts/reinstall.sh` zmienia lokalną instalację i nie jest
częścią kontroli źródeł.