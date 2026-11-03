# Diagnostyka integracji beta

## Regresje i kolejki

`sh scripts/test.sh` uruchamia backend w SDK, bez zapisu bytecode do zrodel.
`npm run check`, `npm run test:ui` i `npm run build` sprawdzaja frontend.
Test xfail miniaturowego fontu Tesseracta pozostaje znanym ograniczeniem,
nie zostal naprawiony przez poluzowanie asercji ani zastapienie OCR.

Aktywny epizod blokuje powtorke nawet po uplywie historii. Historia domyslnie
obejmuje 4500 ms od rozpoczecia audio i przezywa znikniecie napisow. To filtr,
nie opoznienie mowy. Rezerwacja blokuje duplikat tak dlugo, jak pierwsza
kwestia oczekuje na tlumaczenie, synteze lub audio. Po resecie sesji nie
przechodzi ani historia, ani rezerwacje. Pauza zachowuje historie juz zaczetej
mowy, ale zwalnia zadania odrzucone z kolejek.

Obie kolejki zachowuja dotychczasowe FIFO i osiem oczekujacych elementow.
Przepelnienie usuwa najstarszy oczekujacy, nie aktualnie przetwarzany lub
odtwarzany. Zastepowanie klatek przed OCR jest oddzielna polityka.

## Prywatny trace deweloperski

Opcjonalna zmienna `NARRATORVERSE_DIAGNOSTIC_TRACE` przyjmuje absolutna
sciezke do **nowego** pliku JSONL. Plik zawiera pelne napisy i tlumaczenia:
nie publikuj go bez przegladu prywatnosci. Tryb nie zmienia translatora,
cache ani deduplikacji. Producent nie czeka na zapis dyskowy; brakujace
zdarzenia i bledy writer'a sa raportowane.

Zdarzenia rozrozniaja akceptacje, rezerwacje/FIFO, tlumaczenie, TTS, start
i zakonczenie audio, odrzucenie i bledy. `recognized_to_speech_ms` odnosi sie
do rozpoznania; `accepted_to_speech_ms` do akceptacji, a
`frame_to_speech_ms` do klatki. Nie traktuj `tts_ms` jako zadnego z nich.

## Pomiary providerow

`scripts/benchmark-beta.py` to jawne narzedzie deweloperskie. W SDK z
backendem, SentencePiece i runtime na `PYTHONPATH` przyjmuje `--model-dir`,
`--components`, `--output` i `--seconds`. Reczne sciezki sa tutaj fixture'ami
diagnostycznymi, nie konfiguracja normalnego uzytkownika. Uruchamiaj bez sieci.
Pomiar nie odtwarza dzwieku ani nie przechwytuje gry. Raport zawiera CPU,
powinowactwo, czasy cold/warm, RSS i ograniczenia metody.

`python3 -m narratorverse.translation_compare --corpus ... --output ...`
pozostaje narzedziem pomiaru jedynego QuickMT, nie porownywarka Argos/QuickMT.
`narratorverse.quickmt_runtime` sprawdza natywne importy;
`narratorverse.quickmt_smoke` wykonuje rzeczywista inferencje.

## Wymagane jeszcze sprawdzenia reczne

Zgłoszono manualną sesję GTA V: około 40 minut, RapidOCR, polskie napisy,
tłumaczenie wyłączone, zero zaobserwowanych powtórzeń. Szczegóły i ograniczenia
w `RELEASE_NOTES.md`. Nie jest to test QuickMT ani pomiar wydajności.

- dłuższa sesja z QuickMT: wzrost RAM, kolejki, pauza/wznowienie/stop;
- opoznienie od rozpoznania do rzeczywistego startu audio przy OCR i grze;
- zatloczona sciezka audio, awaria urzadzenia i anulowanie pobrania w GUI;
- slabszy CPU: lokalne wyniki nie sa jego predykcja;
- instalacja gotowego bundle w osobnym koncie/srodowisku i test offline.