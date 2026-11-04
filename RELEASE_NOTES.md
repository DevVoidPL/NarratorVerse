# 0.2.0-beta.1 — w przygotowaniu

## Zmiany

- QuickMT zastępuje Argos jako lokalny translator EN → PL na CPU.
  Pobieranie, naprawa i weryfikacja modelu są dostępne w panelu Komponenty.
- Rewizja modelu `6209580ce1fe525214f29fc39725007b73410109` jest przypięta
  wraz z sumami SHA-256 sześciu plików. Instalator zachowuje README i atrybucję.
- Wspólna ochrona przed powtórzeniami obejmuje widoczne napisy, kolejkę
  i historię od rozpoczęcia audio. Rezerwacje są zwalniane po odrzuceniu,
  błędzie lub anulowaniu zadania.
- Poprawiono obsługę wariantów OCR `m`/`rn`, z zachowaniem rozróżniania
  liczb, negacji i zmian rozmówcy.
- RapidOCR działa na CPU. Dostępne pozostają Tesseract i lokalny Piper.
- Budowanie Flatpaka korzysta z przypiętych zależności i jawnej listy wejść,
  bez kopiowania runtime z wcześniejszej instalacji.

## Ograniczenia

Problem powtarzania kwestii wymaga jeszcze weryfikacji w rzeczywistej sesji
Arch/GTA z przechwytywaniem, OCR, Piperem i PipeWire. Testy automatyczne nie
zastępują tej próby. Nie zweryfikowano dłuższej sesji z tłumaczeniem ani
wydajności na słabszym CPU.

OCR może mylić małe lub cieniowane napisy. Ochrona przed powtórzeniami może
pominąć prawdziwą, identyczną krótką replikę w oknie historii. Kolejki FIFO
mają po osiem oczekujących elementów; przepełnienie usuwa najstarszy
oczekujący dialog, bez przerywania aktualnego odtwarzania.

Ta wersja nie ma jeszcze publicznego pakietu Flatpak.
