# 0.2.0-beta.1 — przygotowywana, nieopublikowana

Data przygotowania źródeł: 3 listopada 2026. Nie utworzono nowego tagu, release
ani Flatpaka. Kolejny minor po `v0.1.0` oznacza zmianę translatora i deduplikacji;
`beta.1` określa stan przed wydaniem. Publikację źródeł oceniamy osobno od
redystrybucji runtime, nadal zablokowanej przez `docs/REDISTRIBUTION.md`.

## Zmiany

- QuickMT jest jedynym domyslnym lokalnym translatorem EN -> PL na CPU.
  Zastępuje Argos; tłumaczenie nie korzysta z usług chmurowych.
  Instalacja, naprawa, weryfikacja, usuwanie, rozmiar i sumaryczny postep
  korzystaja ze standardowego panelu Komponenty. Bez fallbacku do chmury.
- Przypieta rewizja modelu
  `6209580ce1fe525214f29fc39725007b73410109`, CC BY 4.0, szesc SHA-256
  oraz zachowany README. Jeden katalog XDG, bez recznego wyboru modelu w GUI.
- Wspolna ochrona epizodu napisow, historii od startu audio (4500 ms
  domyslnie) i rezerwacji oczekujacych. A -> B -> A nie powiela A, gdy
  pierwsza nadal czeka w FIFO. Historia nie dodaje opoznienia odtwarzania.
- Poprawka wariantów OCR `m`/`rn`; zachowane zabezpieczenia liczb, negacji,
  rozmowcow i zmian tresci oraz regresje tych przypadków.
- RapidOCR nadal działa na CPU, bez CUDA. Zachowane Tesseract i lokalny Piper.
- FIFO i limity bez zmian. Odrzucenie oczekujacej kwestii, blad lub
  anulowanie zwalnia rezerwacje. Reset sesji czysci stan; stare callbacki
  pozostaja odciete generacja i progiem request ID.
- Usuniete launchery eksperymentalne i przelaczniki zachowania.
  Diagnostyka prywatna pozostaje opt-in; narzedzia regresyjne zachowane.
- Runtime SentencePiece trafia do standardowego stagingu. Argos i jego
  tokenizery nie sa uzywane ani dolaczane jako komponent tlumaczenia.

## Test manualny użytkownika

Zgłoszony przez użytkownika podczas przygotowania źródeł:

| Ustawienie / obserwacja | Wartość |
|---|---|
| Gra | GTA V |
| Czas | około 40 minut |
| OCR | RapidOCR |
| Język napisów | polski |
| Tłumaczenie | wyłączone |
| Zaobserwowane powtórzone zdania | **0** |

To test manualny, nie wynik automatycznych testów ani gwarancja niezawodności.
Nie podano dokładnej daty sesji ani pomiarów RAM, opóźnienia i długości FIFO.
Ta sesja **nie sprawdza QuickMT**, ponieważ tłumaczenie było wyłączone.
Nie wykonano ani nie deklarujemy testu QuickMT w Batmanie w tej wersji.

## Ograniczenia

OCR moze gubic i mylic znaki, zwlaszcza przy malych/cieniowanych napisach.
Nowy filtr moze celowo zablokowac identyczna autentyczna krotka replike
w oknie historii; rozroznienie bez obrazu/rozmowcy nie zawsze jest mozliwe.
FIFO jest ograniczone: dluga mowa i szybkie napisy nadal moga spowodowac
przepelnienie zgodnie z dotychczasowa polityka.

Aktualne wyniki testów źródeł: `docs/SOURCE_PUBLICATION.md`.
Historyczne testy inferencji i pomiary providerów: `docs/INTEGRATION_REPORT.md`.
Nie zweryfikowano dłuższej sesji z aktywnym tłumaczeniem ani słabszego CPU.
Nie przenosic wynikow lokalnego CPU na slabsze maszyny. Test providerow
bez OCR i bez audio nie jest testem sesji gry.