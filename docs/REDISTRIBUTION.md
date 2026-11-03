# Przegląd licencji: źródła a redystrybucja runtime

Data: 2026-11-03. Status: **NIEZAMKNIETY / NIE PUBLIKOWAC BUNDLE**.
To rejestr konkretnych ustalen i brakow, nie opinia prawna ani certyfikat
zgodnosci. Lokalny kandydat sluzy walidacji.

## Publikacja samych źródeł

Źródła aplikacji są objęte MIT z zachowanym autorstwem GameOpti/DevVoidPL.
W publikowanym drzewie nie ma implementacji Pipera, Qt, wheeli ani wag modeli;
są importy, opisy komponentów, locki oraz teksty licencji i testy. Publikacja
takiego drzewa nie jest tym samym co przekazanie odbiorcy kopii binarnego runtime.
Nie stwierdzono tu blokady wymagającej wstrzymania samego przeglądu źródeł
z powodu niekompletnego corresponding-source kit dla niepublikowanego Flatpaka.
Nie jest to ostateczna opinia o kwalifikacji prawnej całego połączonego produktu.
Gotowość Git i prywatności ocenia osobno `docs/SOURCE_PUBLICATION.md`.

## Co rzeczywiscie sprawdzono

- Skopiowany runtime `.runtime/lib/python3.13/site-packages`, biblioteki
  natywne, Qt/PySide6 i metadane dystrybucji; w stagingu zweryfikowano wszystkie 7372 wpisy `snapshot-files.json`,
  bez plikow dodatkowych ani bytecode. Suma gotowego bundle sprawdzona.
- Obecne: Piper 1.7.0 (GPL-3.0-or-later), PySide6/Qt 6.11.1, CTranslate2
  4.8.1, ONNX Runtime 1.28.0, RapidOCR 3.10.0 oraz OpenCV i zaleznosci.
- Qt snapshot zawiera rowniez nieuzywane przez ten frontend biblioteki:
  Charts, DataVisualization, VirtualKeyboard i WebEngine. Nie wolno
  utozsamiac naglowkowego LGPL dla PySide6 z licencjami wszystkich modulow.
- Metadane wheeli nie dostarczaja kompletnej listy natywnych bibliotek ani
  ich obowiazkow. Dla CTranslate2 i wheeli PySide6 nie znaleziono plikow
  license w ich listach RECORD; to wymaga uzupelnienia z dokladnych zrodel.
- Usunieto z kopii runtime sacremoses i subword-nmt, potrzebne tylko Argosowi.
  Zachowano kod procesowy i zaleznosci OCR/Pipera.
- Model QuickMT nie jest w bundle. Katalog komponentow zawiera przypieta
  rewizje, SHA-256, oryginalny README oraz informacje o autorze, licencji
  i braku zmian. Voidek zachowuje osobna licencje i zapisana zgode projektu.

## Obowiazki do zamkniecia przed dystrybucja

1. **Piper i jego natywne zaleznosci**: ustalic kompletny corresponding
   source dla faktycznie dolaczonych binariow, wymagane skrypty budowania,
   notice'y i sposob udostepnienia zgodny z GPL. Sam link do ogolnej strony
   projektu ani sam JSON ze spisem pakietow nie jest dowodem spelnienia.
2. **Qt/PySide6**: ustalic licencje kazdego zachowanego modulu i kodu
   third-party, dolaczyc teksty licencji/notice, zapewnic wymagane zrodla
   i uprawnienia odbiorcy. Alternatywnie przygotowac i przetestowac
   minimalny runtime bez nieuzywanych modulow; nie usuwac bibliotek w ciemno.
3. **GStreamer/Tesseract/Leptonica i biblioteki ELF**: mapowanie wszystkich
   faktycznych plikow na zrodla, wersje, licencje i wymagane notice.
   Runtime GNOME jest osobnym artefaktem, a nie dowodem zgodnosci plikow
   skopiowanych do `/app`.
4. **Pozostale wheele oraz Cargo/npm**: zachowac notice'y kodu dolaczonego
   do bundle (takze statycznie), sprawdzic wyjatki i tresc third-party.
5. Po naprawie: powtorzyc staging, testy natywnych importow/offline,
   zweryfikowac caly nowy inventory i utworzyc nowa sume bundle.

## Ponowny przegląd rzeczywistego snapshotu

Sprawdzono lokalny inventory i pliki stagingu, bez przebudowy runtime.
To dowód zawartości historycznego `0.1.0-beta-integration`, nie nowego pakietu
`0.2.0-beta.1`. Liczba 76 plików z nazwą license/notice/copying nie dowodzi,
że wszystkie obowiązki zostały spełnione.

| Składnik snapshotu | Zachowane informacje | Nadal do wykonania |
|---|---|---|
| Piper 1.7.0 / espeak-ng | Piper COPYING, GPL-3.0-or-later w metadanych, natywne `espeakbridge` i `libespeak-ng` | Powiązać binaria z dokładnymi źródłami, zmianami i skryptami budowania; ocenić relację importowanego Pipera do aplikacji i właściwe warunki dystrybucji całości |
| PySide6/Essentials/Addons/shiboken6 6.11.1 i Qt | Metadane wariantów LGPL/GPL, inventory bibliotek i pluginów | Uzupełnić licencje/notice konkretnych modułów, źródła, możliwość podmiany biblioteki i wymagane uprawnienia odbiorcy; sam import tylko QtCore nie wyłącza obowiązków za dołączone inne moduły |
| Dodatkowe Qt | Charts, DataVisualization, VirtualKeyboard, WebEngine, także Graphs, Quick3D i HttpServer | Sprawdzić pliki licencyjne dokładnie 6.11.1; część modułów jest GPL-only w ofercie open-source. WebEngine wymaga osobnego przeglądu Chromium/third-party, nie etykiety GPL dla całego katalogu |
| CTranslate2 4.8.1, ONNX Runtime 1.28.0, OpenCV 5.0.0.93 | MIT/Apache w metadanych; ONNX `LICENSE`/`ThirdPartyNotices.txt`, OpenCV `LICENSE.txt`/`LICENSE-3RD-PARTY.txt` | Uzupełnić brakujące teksty CTranslate2 i przejrzeć biblioteki w wheelach, m.in. OpenMP/BLAS i kodeki |
| RapidOCR 3.10.0, Tesseract, Leptonica | RapidOCR `LICENSE` i `MODEL_LICENSES.md` w runtime/komponencie, identyfikatory licencji modeli w katalogu | Zweryfikować wszystkie faktyczne wagi, binaria Tesseract/Leptonica i ich notice; nie utożsamiać licencji engine z modelem |
| SentencePiece 0.2.1 | Apache-2.0 i upstream NOTICE w repo oraz stagingu | Zachować je w przyszłym pakiecie; same teksty nie zastępują przeglądu całego runtime |
| inflate64 1.0.4, multivolumefile 0.2.3, py7zr 1.1.3, pybcj 1.0.8, pyppmd 1.3.1 | Metadane LGPL-2.1/2.1-or-later i pliki LICENSE | Ustalić źródła i sposób spełnienia LGPL dla dystrybuowanych wersji; usunięcie zbędnych pakietów dopiero po analizie użycia i testach |
| Shapely 2.2.0 / GEOS | `LICENSE.txt` i `LICENSE_GEOS` | Ustalić dokładną wersję natywnego GEOS i obowiązki LGPL, nie tylko licencję wrappera |
| certifi 2026.10.23, tqdm 4.70.0 | Metadane MPL-2.0 oraz MPL/MIT | Zmapować pliki objęte MPL i udostępnienie ich Source Code Form zgodnie z §3.2; nie zakładać obowiązku otwarcia całej aplikacji |
| GStreamer i pozostałe ELF, Cargo/npm | Inventory ścieżek, zachowane locki | Pełna mapa plik → wersja → źródła → licencja; obejmuje pluginy, zależności statyczne frontendu i kod third-party |

## Źródła, oferta źródeł i forma dystrybucji

- GPLv3 §6 przewiduje różne sposoby udostępnienia Corresponding Source.
  Przy pobieraniu online §6(d) pozwala zapewnić równoważny dostęp do źródeł
  z tego samego miejsca, bez dodatkowej opłaty. To wymaga faktycznie kompletnego
  zestawu źródeł danego binarium, nie tylko linku do ruchomego `main` upstream.
- Pisemna oferta z §6(b) jest inną, określoną warunkami ścieżką (m.in. okres
  co najmniej trzech lat, odpowiedni nośnik/sposób przekazania); nie jest
  uniwersalnym zamiennikiem brakujących źródeł. Nie złożono takiej oferty.
  Nie wybieramy jej automatycznie dla przyszłego pobierania Flatpaka.
- LGPLv3 §4 wymaga m.in. notice, licencji i właściwej możliwości ponownego
  połączenia/podmiany biblioteki; sposób spełnienia zależy od dystrybucji.
  Dla składników LGPL-2.1 należy oddzielnie sprawdzić §4/§6 tej wersji.
- MPL-2.0 §3.2 wymaga dostępności Source Code Form objętych nią plików
  i wskazania odbiorcy sposobu uzyskania źródeł. Nie oznacza automatycznie
  objęcia MPL całego programu.
- MIT/BSD/Apache zwykle wymagają zachowania odpowiednich tekstów i atrybucji;
  Apache obejmuje też istotne NOTICE. Nie uznajemy nazw licencji w JSON za notice.

Nie rozstrzygnięto, czy sposób łączenia backendu z Piperem i poszczególnymi
modułami GPL tworzy utwór połączony wymagający objęcia całości właściwymi
warunkami. Oddzielny proces frontend/backend sam tego nie przesądza.
Do zamknięcia: analiza licencyjna architektury albo zmiana zestawu zależności
i ponowna walidacja. Nie zmieniano licencji aplikacji bez decyzji właściciela.

## Modele i głosy

QuickMT jest pobierany osobno: QuickMT, CC BY 4.0, przypięta rewizja
`6209580ce1fe525214f29fc39725007b73410109`. Katalog zachowuje autora,
oryginalny README i informację o niezmienionych plikach. CC BY §3 wymaga
odpowiedniej atrybucji, informacji o licencji i oznaczenia zmian przy udostępnianiu;
nie wymaga corresponding-source kit dla runtime. Nie dołączono wag do Git.

Voidek ma odrębne, ograniczone zezwolenie projektowe opisane w
`licenses/VOIDEK-LICENSE.md`, nie MIT ani ogólną zgodę na samodzielną
redystrybucję modelu. Przed publicznym pakietem właściciel powinien potwierdzić,
że zachowany zapis zgody jest wystarczającym publicznym dokumentem uprawnienia.
Każdy importowany lub dodatkowo pobierany głos podlega własnej karcie modelu;
licencja Pipera nie rozszerza uprawnień do głosu.

Nie oznaczono zadnego z tych punktow jako zakonczonego tylko na podstawie
nazwy pakietu, klasyfikatora PyPI czy testow jednostkowych.

## Zrodla normatywne przejrzane przy integracji

Adresy referencyjne (nie zastapienie zrodel konkretnych wersji):

```text
https://doc.qt.io/qt-6.11/licensing.html
https://doc.qt.io/qt-6.11/lgpl.html
https://doc.qt.io/qt-6.11/gpl.html
https://www.qt.io/development/download-open-source
https://www.gnu.org/licenses/gpl-faq.en.html
https://www.gnu.org/licenses/gpl-3.0.html
https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html
https://www.mozilla.org/en-US/MPL/2.0/
https://github.com/OHF-Voice/piper1-gpl/blob/main/COPYING
https://creativecommons.org/licenses/by/4.0/deed.en
https://creativecommons.org/licenses/by/4.0/legalcode.en
https://huggingface.co/quickmt/quickmt-en-pl/tree/6209580ce1fe525214f29fc39725007b73410109
```

Przy tym przeglądzie odczytano dokumentację Qt 6.11, teksty LGPL i GPL
w dokumentacji Qt, COPYING Pipera, MPL i CC BY. Bezpośrednie pobranie strony
GPL z GNU zakończyło się timeoutem; GPL sprawdzono także w zachowanej lokalnej
kopii Piper COPYING. Strona karty QuickMT w narzędziu WWW nie była dostępna;
przypięte metadane i atrybucję sprawdzono w kodzie komponentu, bez nowego pobierania modelu.
Link do ruchomego upstream jest referencją prawną, nie dowodem pochodzenia
zainstalowanego binarium. Wersje i hashe muszą pochodzić z przyszłego source kit.