# 0.2.0-beta.1 — przygotowywana, nieopublikowana

Data przygotowania źródeł: 3 listopada 2026. Nie utworzono nowego tagu, release
ani publicznego Flatpaka. Kolejny minor po `v0.1.0` oznacza zmianę translatora i deduplikacji;
`beta.1` określa stan przed wydaniem. Publikację źródeł oceniamy osobno od
redystrybucji runtime, nadal zablokowanej przez `docs/REDISTRIBUTION.md`.

4 listopada 2026 rozpoczęto przygotowanie gałęzi `release/0.2.0-beta.1`
z aktualnego `origin/main` po scaleniu PR #1. Plan nowego buildu i bramki
dotyczące przyszłego pakietu: `docs/RELEASE_PREPARATION.md`.
Zbudowano lokalne kandydaty świeżego buildu; nie opublikowano nowego Flatpaka.
Procedura: [FRESH_BUILD](docs/FRESH_BUILD.md).

## P0 powtórzeń — OPEN

Publikacja źródeł nie zamyka P0 i nie jest zgodą na wydanie binarne.
Zmiany źródeł obejmują ochronę przez czas odtwarzania, obsługę zdarzeń terminalnych
i idempotencję callbacków. Testy na atrapach nie dowodzą usunięcia zgłoszonego
problemu Arch/GTA. Wymagana jest rzeczywista sesja capture → OCR → Piper →
PipeWire z nowym JSONL: [P0_ARCH_ACCEPTANCE](docs/P0_ARCH_ACCEPTANCE.md).
Przypadek `1508 → 1515` („Rzecz jasna...”) pozostaje nierozstrzygnięty;
nie dodano spekulacyjnego filtra. ESC/interface OCR jest oczekiwany.
ASR pozostaje odłożone, bez implementacji ani dokumentu koncepcyjnego.

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

## Historyczny test manualny użytkownika — nie zamyka P0

Zgłoszony przez użytkownika podczas przygotowania źródeł:

| Ustawienie / obserwacja | Wartość |
|---|---|
| Gra | GTA V |
| Czas | około 40 minut |
| OCR | RapidOCR |
| Język napisów | polski |
| Tłumaczenie | wyłączone |
| Zaobserwowane powtórzone zdania | **0** |

To historyczna obserwacja, **nie dowód zamknięcia P0**, nie wynik bieżących
testów automatycznych ani gwarancja niezawodności.
Nie podano dokładnej daty sesji ani pomiarów RAM, opóźnienia i długości FIFO.
Ta sesja **nie sprawdza QuickMT**, ponieważ tłumaczenie było wyłączone.
Nie wykonano ani nie deklarujemy testu QuickMT w Batmanie w tej wersji.

## Ograniczenia

OCR moze gubic i mylic znaki, zwlaszcza przy malych/cieniowanych napisach.
Nowy filtr moze celowo zablokowac identyczna autentyczna krotka replike
w oknie historii; rozroznienie bez obrazu/rozmowcy nie zawsze jest mozliwe.
FIFO jest ograniczone: dluga mowa i szybkie napisy nadal moga spowodowac
przepelnienie zgodnie z dotychczasowa polityka.

Stan przygotowania tej gałęzi: `docs/RELEASE_PREPARATION.md`.
Historyczne wyniki testów integracji: `docs/SOURCE_PUBLICATION.md`.
Historyczne testy inferencji i pomiary providerów: `docs/INTEGRATION_REPORT.md`.
Nie zweryfikowano dłuższej sesji z aktywnym tłumaczeniem ani słabszego CPU.
Nie przenosic wynikow lokalnego CPU na slabsze maszyny. Test providerow
bez OCR i bez audio nie jest testem sesji gry.