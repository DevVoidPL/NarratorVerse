# Diagnostyka

## Kontrole automatyczne

`npm run check`, `npm run test:ui` i `npm run build` sprawdzaja frontend.
`sh scripts/test.sh` uruchamia testy backendu w przygotowanym lokalnym
srodowisku Python/Qt; wymagania opisuje [INSTALL](INSTALL.md).
Testy nie zastępują próby przechwytywania i odtwarzania w aplikacji.

## Slad zdarzen

`NARRATORVERSE_DIAGNOSTIC_TRACE` przyjmuje absolutna sciezke do nowego pliku
JSONL. Pola tekstowe sa hashowane przed zapisem. Zwykle logi i inne slady
moga zawierac pelne napisy; przejrzyj je przed udostepnieniem.

Zdarzenia obejmuja akceptacje napisow, rezerwacje, kolejki, tlumaczenie,
synteze i odtwarzanie. Producent nie czeka na zapis dyskowy; utracone
zdarzenia i bledy zapisu sa liczone.

`recognized_to_speech_ms` mierzy czas od rozpoznania do startu audio,
`accepted_to_speech_ms` od akceptacji, a `frame_to_speech_ms` od klatki.
`tts_ms` opisuje tylko synteze.

## Runtime tlumaczenia

`python3 -m narratorverse.quickmt_runtime` sprawdza natywne zaleznosci.
`narratorverse.quickmt_smoke` wykonuje inferencje na wskazanym modelu.
Oba narzedzia wymagaja przygotowanego runtime. Pomiar samej inferencji
nie obejmuje OCR, przechwytywania ani opoznienia fizycznego wyjscia audio.
