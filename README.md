# NarratorVerse

Lektor napisow do gier na Linuksa. Czyta napisy z wybranego fragmentu okna
lub ekranu i odtwarza je po polsku. Nie wymaga modyfikowania plikow gry.

## Stan zrodel beta

Przygotowywana wersja: **0.2.0-beta.1**. Nie opublikowano jeszcze odpowiadajacego
jej pakietu Flatpak. Program pomaga sledzic dialogi bez ciaglego patrzenia na napisy.

QuickMT jest jedynym domyslnym lokalnym translatorem EN -> PL na CPU, instalowanym
z panelu Komponenty. Nie wymaga eksperymentalnego launchera ani recznej
sciezki modelu. Po instalacji dziala offline. RapidOCR nadal pracuje na CPU
bez CUDA, a mowa jest generowana lokalnie przez Pipera.

**Nie publikowac jeszcze pakietu:** przeglad redystrybucji runtime pozostaje
otwarty. Szczegoly: `docs/REDISTRIBUTION.md`. Stan prac i wyniki:
`docs/SOURCE_PUBLICATION.md`; historyczna integracja: `docs/INTEGRATION_REPORT.md`;
zmiany i historyczny test GTA V: `RELEASE_NOTES.md`.
Instalacja: `docs/INSTALL.md`; diagnostyka: `docs/DIAGNOSTICS.md`.

Swiezy build z przypietych zaleznosci: [FRESH_BUILD](docs/FRESH_BUILD.md).
Stan przygotowania: [RELEASE_PREPARATION](docs/RELEASE_PREPARATION.md).
Lokalny kandydat zostal zbudowany, ale nie jest publicznym wydaniem.
**P0 powtorzen pozostaje OPEN**: wymagany jest rzeczywisty test GTA/capture,
Piper i PipeWire z nowym JSONL. Historyczny test GTA nie zamyka tej bramki.

## Podglad

![Lektor](docs/screenshots/lektor.png)

## Funkcje

- Odczyt polskich napisow i lokalne tlumaczenie angielskich napisow na polski.
- Wybor silnika OCR: Tesseract lub RapidOCR.
- Glos Voidek oraz import wlasnych glosow Piper z plikow `.onnx` i `.onnx.json`.
- Regulacja tempa, glosnosci i lagodne przyspieszanie szybkich dialogow.
- Opcjonalne czytanie imion postaci z podpisow, np. `Anna:`.
- Przyciszanie wybranej gry podczas mowy lektora.
- Osobne profile dla roznych ustawien i obszarow napisow.
- Szybki odczyt wklejonego tekstu, bez gry i udostepniania ekranu.

Interfejs jest po polsku. Obslugiwane tryby napisow to polski bez tlumaczenia
oraz angielski z tlumaczeniem na polski. Import glosu nie dodaje nowych trybow
tlumaczenia. Program nie rozpoznaje postaci po twarzy ani po ich glosie.

## Jak dziala lektor

Przechwycony obszar trafia do Tesseracta lub RapidOCR. Polskie napisy sa
przekazywane do Pipera, a angielskie najpierw tlumaczy lokalny QuickMT EN -> PL.
Piper generuje mowe odtwarzana w kolejnosci FIFO. Ochrona przed powtorkami
obejmuje aktywny epizod, historie od poczatku audio i kwestie oczekujace.
Nie trzeba modyfikowac gry ani korzystac z uslug chmurowych.

## Wymagania systemowe

- Linux x86_64; obecna sciezka pakowania uzywa GNOME Platform 49 i Flatpaka.
- Dzialajacy `xdg-desktop-portal` z backendem pulpitu obslugujacym wybor
  okna/ekranu i przechwytywanie przez PipeWire.
- Wyjscie audio i CPU obslugujacy rownoczesnie gre, OCR oraz synteze.
  Nie ustalono jeszcze minimum RAM ani CPU; nie zweryfikowano slabszej maszyny.
- Do przyciszania: PipeWire z interfejsem PulseAudio, `pactl` i rozpoznawalny
  strumien gry. GPU/CUDA nie jest wymagane przez RapidOCR ani QuickMT.
- Internet do instalacji/naprawy komponentow; po pobraniu przetwarzanie jest lokalne.

## Instalacja i uzywanie

Ta galaz zawiera zrodla, nie gotowy nowy pakiet. Procedura lokalnego budowania
i jej ograniczenia: `docs/INSTALL.md`. Samo sklonowanie repozytorium nie
wystarcza do zbudowania kompletnego Flatpaka.

Po przygotowaniu lokalnej instalacji otworz **Komponenty**. Sprawdz OCR i glos;
dla angielskich napisow pobierz **QuickMT English to Polish (CPU)**, okolo
385 MiB z README. Panel obsluguje weryfikacje, naprawe, anulowanie i usuwanie.

1. Wybierz lub utworz profil w Lektorze.
2. Ustaw rodzaj zrodla, silnik OCR, jezyk napisow, glos i tempo.
3. Zapisz zmiany.
4. Kliknij **Wybierz zrodlo** i wskaz okno gry albo ekran w oknie systemowym.
5. Zaznacz same napisy w podgladzie i zatwierdz obszar.
6. Rozpocznij czytanie.

Pauza wstrzymuje czytanie bez zamykania udostepniania. Zatrzymanie zamyka
przechwytywanie i pozwala zmienic ustawienia profilu. Dostep do okna zalezy od
systemowego portalu; zapis profilu nie gwarantuje zachowania zgody po restarcie.

Opcje czytania sa w Lektorze. Klikniecie nazwy glosu otwiera wybor i import
nowego glosu. Przy imporcie zaznacz razem model i pasujacy plik konfiguracji
(Ctrl + klikniecie). Korzystaj z zaufanych modeli i sprawdz licencje glosu;
licencja Pipera nie obejmuje automatycznie modeli.
Diagnostyka jest zwinieta na dole strony.

### Profile

Ustawienia Lektora zapisuja sie przyciskiem **Zapisz zmiany**. Formularz pokazuje
niezapisane zmiany, a przejscie do innego profilu wymaga ich odrzucenia.
Zamkniecie aplikacji bez zapisu nie zachowuje edytowanego formularza.

Profil pamieta m.in. obszar napisow, silnik OCR, jezyk, glos, tempo i aplikacje
audio. Zapis pliku jest atomowy. Interfejs pobiera stan po zapisie, zanim
wyswietli potwierdzenie. Przywrocenie domyslnych ustawien wymaga potwierdzenia
i zapisuje sie od razu; nie usuwa modeli ani wlasnych glosow.

Szybki odczyt ma osobne opcje glosu, tempa i glosnosci, zapisywane automatycznie.
Czyta do 10 000 znakow polskiego tekstu. Nie uruchamia OCR ani tlumaczenia.

### Balans gry

Uruchom gre z dzwiekiem, odswiez liste aplikacji audio i wybierz wlasciwa
aplikacje. Wlacz przyciszanie i zapisz profil. Wybor okna przechwytywania nie
wybiera automatycznie aplikacji audio.

Poziomy przyciszania to -6, -12 i -18 dB. Po mowie lektora wraca poprzednia
glosnosc gry, nie 100%. Program nie zmienia glosnosci glownej, wyciszenia ani
trasowania. Nie oddziela dialogow gry od muzyki. Reczna regulacja w mikserze
oddaje Ci sterowanie do ponownego wlaczenia czytania.

Funkcja wymaga lokalnego PipeWire z interfejsem PulseAudio, narzedzia `pactl`
i metadanych pozwalajacych rozpoznac strumien. Zmiana strumienia moze wstrzymac
balans; sprawdz wtedy poziom gry i wznow czytanie. Osobny proces i dziennik
pomagaja przywrocic glosnosc po utracie polaczenia z silnikiem. Nie gwarantuja
przywrocenia po smierci obu procesow, zmianie tozsamosci strumienia lub zaniku
zasilania. `pactl` nie oferuje atomowego porownania i zapisu.

Wyrownanie poziomu lektora jest ograniczonym przyblizeniem RMS dla PCM s16le,
do 1 MiB danych, ze wzmocnieniem do 2x i zapasem na szczyty. Nie jest pomiarem
LUFS ani analiza glosnosci gry. Nie dotyczy Szybkiego odczytu.

## Ograniczenia

Jakosc OCR zalezy od czcionki, tla, rozdzielczosci i zaznaczenia napisow.
Nie kazda kwestia zostanie odczytana poprawnie. Identyczna kwestia wymaga
konca epizodu oraz wygasniecia historii (4500 ms domyslnie od startu audio).
Rezerwacje chronia tez kwestie nadal oczekujace w FIFO i aktualnie odtwarzane,
az do zdarzenia terminalnego. Historia nie dodaje
opoznienia przed odtwarzaniem. Program nie ma dostepu do skryptu
dialogow gry ani listy nazw postaci.

QuickMT moze blednie tlumaczyc idiomy, imiona i urwane zdania. Bledy OCR
przechodza do tlumaczenia. Wynik nie zastepuje tlumaczenia przygotowanego
przez czlowieka. Identyczna, autentyczna krotka replika moze zostac zablokowana
przez historie deduplikacji.

Tempo bazowe ma zakres 0,5-2x. Adaptacja zmienia tempo nowych wypowiedzi,
maksymalnie do 150% tempa bazowego i nie ponad 2x. Nie zmienia trwajacej mowy.
Przy dlugim, szybkim dialogu kolejka moze pominac czesc oczekujacych kwestii.

## Prywatnosc

Przetwarzanie obrazu, tlumaczenie i mowa sa lokalne. Siec jest potrzebna do
pobierania komponentow, nie do wysylania obrazu gry do uslugi zewnetrznej.
Przed udostepnieniem diagnostyki sprawdz jej tresc: moze zawierac napisy z gry,
nazwy aplikacji, urzadzen oraz lokalne sciezki.

Pobieranie komponentow ujawnia ich serwerom zwykle dane polaczenia.
Uprawnienie sieciowe Flatpaka nie jest gwarancja odlaczenia od sieci.
Profile, glosy, cache tlumaczen i zgody portalu sa lokalnymi danymi XDG,
nie czescia repozytorium. Diagnostyczny JSONL
`NARRATORVERSE_DIAGNOSTIC_TRACE` hashuje pola tekstowe; zwykle logi i inne
trace moga zawierac pelne napisy. Przejrzyj kazdy plik przed udostepnieniem.

## Kod i budowa

Interfejs korzysta z Svelte i TypeScript, aplikacja okienkowa z Tauri 2,
a osobny proces Python/Qt zajmuje sie przechwytywaniem i przetwarzaniem napisow.
Wersje zaleznosci interfejsu i Rust sa zapisane w plikach blokad.

Repozytorium zrodlowe nie zawiera modeli ani lokalnego runtime.
Aktualna procedura: [FRESH_BUILD](docs/FRESH_BUILD.md), wymagania i ograniczenia:
[INSTALL](docs/INSTALL.md). Budowa nie wymaga starego snapshotu `.runtime`.
Wymaga przypietych SDK/Platform, narzedzi hosta i oryginalow glosu wlasciciela.

Z katalogu projektu, podajac wlasne absolutne sciezki:

```sh
sh scripts/build-fresh.sh /absolute/new/work-directory /absolute/owner-input
```

Katalog roboczy nie moze istniec. Skrypt nie eksportuje, nie instaluje i nie
publikuje pakietu. Skrypty build.sh/build-flatpak.sh/prepare-quickmt-runtime.sh
przyjmuja te same argumenty i deleguja do build-fresh.sh. Automatyczna
reinstalacja jest zablokowana na czas walidacji. Archiwum legacy-snapshot
nie jest aktualna instrukcja.

Kontrole frontendu (nie test instalacji ani audio):

```sh
npm ci --no-audit --no-fund
npm run check
npm run test:ui
npm run build
```

`sh scripts/test.sh` korzysta z wczesniej przygotowanego lokalnego srodowiska
Python/Qt/pytest w GNOME SDK. To pomocnik testowy, nie sposob przygotowania
runtime swiezego buildu. Szczegoly w `docs/INSTALL.md`.

## Testy

Historyczne wyniki integracji sa w `docs/SOURCE_PUBLICATION.md`;
stan tej galezi w `docs/RELEASE_PREPARATION.md`, polecenia w `docs/INSTALL.md`,
a zasady prywatnosci logow, pomiary CPU
i ograniczenia walidacji w `docs/DIAGNOSTICS.md`.

Testy obejmuja przetwarzanie napisow, kolejke mowy, zapis i izolacje profili,
obsluge bledow zapisu oraz balans na atrapach miksera. Testy interfejsu sprawdzaja
stan formularza i kompilacje komponentow; nie zastepuja proby w oknie aplikacji.
Znany oczekiwany blad dotyczy Tesseract i testowej czcionki pikselowej 5x7.

## Licencje

Kod aplikacji jest na licencji MIT. Zaleznosci i modele maja wlasne warunki.
Glos Voidek nie jest objety MIT; niezmieniony model moze byc dolaczany do
pakietow NarratorVerse na podstawie zgody wlasciciela. Tresc licencji i zakres
zezwolenia sa zachowane w dokumentacji licencyjnej.

Informacje o pochodzeniu kodu, zaleznosciach i ograniczeniach redystrybucji
sa w katalogu licencji. Swiezy kandydat korzysta z przypietych wejsc,
ale audyt licencji i obowiazkow dotyczacych zrodel zaleznosci nie jest zakonczony.
Wlasne glosy, profile i dane uzytkownika nie sa czescia publikowanych zrodel.
## Translator i model

QuickMT: `quickmt/quickmt-en-pl`, rewizja
`6209580ce1fe525214f29fc39725007b73410109`, licencja CC BY 4.0.
Model ma szesc plikow z przypietymi SHA-256; instalator zachowuje tez
oryginalny README i atrybucje. CTranslate2 oraz SentencePiece pracuja lokalnie
na CPU. Brak modelu nie wlacza chmury ani zastepczego silnika. Profile fast/balanced
zachowuja dotychczasowe ustawienia dekodowania. Cache jest zachowany.

Kolejki dialogow oraz audio pozostaja FIFO z osmioelementowym oczekiwaniem;
przepelnienie usuwa najstarszy oczekujacy, nigdy obecnie odtwarzany dialog.
Pauza zwalnia nieodtworzone zadania. Nowa sesja czysci historie i rezerwacje.

Publikacja zrodel nie oznacza zamkniecia obowiazkow dotyczacych binarnego runtime.
`EXPERIMENTS.md` kieruje do zachowanych narzedzi diagnostycznych.
