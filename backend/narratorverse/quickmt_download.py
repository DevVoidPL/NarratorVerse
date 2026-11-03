"""Developer-only pinned model verifier/downloader; users install from Components.

The GUI catalog and this diagnostic share the same immutable SHA-256 pins.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler

from .quickmt_model import QUICKMT_REVISION, QUICKMT_DOWNLOAD_FILES, QUICKMT_BASE_URL


BASE_URL = QUICKMT_BASE_URL
FILES = QUICKMT_DOWNLOAD_FILES
ATTRIBUTION = (
    'QuickMT EN→PL — quickmt/quickmt-en-pl\n'
    'Autor / wydawca repozytorium: QuickMT\n'
    'Źródło: https://huggingface.co/quickmt/quickmt-en-pl\n'
    f'Rewizja: {QUICKMT_REVISION}\n'
    'Licencja modelu: Creative Commons Attribution 4.0 International (CC BY 4.0)\n'
    'https://creativecommons.org/licenses/by/4.0/\n'
    'Zachowano oryginalny README.md. Pliki modelu bez zmian; bez konwersji ani kwantyzacji.\n'
    'Adapter NarratorVerse i jego ustawienia dekodowania nie są biblioteką QuickMT.\n'
)
METADATA = {'SHA256SUMS.json', 'ATTRIBUTION.txt', '.download.lock'}


def default_model_dir():
    from game_optimization_linux.config import NARRATOR_COMPONENTS_DIR
    from .quickmt_model import QUICKMT_COMPONENT_ID
    return NARRATOR_COMPONENTS_DIR / QUICKMT_COMPONENT_ID


def allowed_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and (host == 'huggingface.co' or host == 'hf.co' or host.endswith('.hf.co')
                 or host.endswith('.huggingface.co')))


class _OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('Odrzucono przekierowanie poza HTTPS infrastruktury Hugging Face')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def _open(url, timeout):
    if not allowed_url(url):
        raise ValueError('Nieoficjalny adres modelu')
    return build_opener(HTTPSHandler(), _OfficialRedirect()).open(url, timeout=timeout)


def _directory(root, *, create=False):
    root = Path(root).expanduser()
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('Katalog modelu musi być absolutną ścieżką bez ..')
    project = Path(__file__).resolve().parents[2]
    if root == project or project in root.parents:
        raise ValueError('Model musi być poza repozytorium i zawartością Flatpaka')
    for path in (root, *root.parents):
        if path.is_symlink():
            raise ValueError(f'Odrzucono symlink katalogu: {path}')
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not root.is_dir() or root.stat().st_uid != os.getuid():
        raise ValueError(f'Katalog modelu nie istnieje lub nie należy do użytkownika: {root}')
    allowed = set(FILES) | METADATA
    for path in root.iterdir():
        if path.name not in allowed and not path.name.startswith('.quickmt-'):
            raise ValueError(f'Nieoczekiwany plik w katalogu modelu: {path.name}')
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Odrzucono symlink lub plik specjalny: {path.name}')
    return root


def _file_hash(path, name):
    size, kind, expected = FILES[name]
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != size:
            raise ValueError(f'{name}: nieprawidłowy typ lub rozmiar, oczekiwano {size} bajtów')
        sha256 = hashlib.sha256()
        pinned = hashlib.sha256() if kind == 'sha256' else hashlib.sha1()
        if kind == 'git':
            pinned.update(f'blob {size}\0'.encode('ascii'))
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            pinned.update(chunk)
            sha256.update(chunk)
    if pinned.hexdigest() != expected:
        raise ValueError(f'{name}: suma nie zgadza się z przypiętą rewizją')
    return sha256.hexdigest()


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _lock(root, *, readonly=False):
    flags = os.O_RDONLY if readonly else os.O_CREAT | os.O_RDWR
    descriptor = os.open(root / '.download.lock', flags | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r' if readonly else 'w') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Inne pobieranie lub sprawdzanie modelu już trwa (lock)') from error
        yield
        # The persistent lock inode must not be unlinked: another process may
        # already have opened it. Closing the descriptor releases flock.


def _atomic_write(root, name, content):
    descriptor, temporary = tempfile.mkstemp(prefix='.quickmt-', dir=root)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / name)
    finally:
        temporary.unlink(missing_ok=True)


def _download(root, name, opener):
    size = FILES[name][0]
    descriptor, temporary = tempfile.mkstemp(prefix='.quickmt-', dir=root)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            with opener(BASE_URL + '/' + name, timeout=60) as response:
                count = 0
                transfer_sha256 = hashlib.sha256()
                while True:
                    chunk = response.read(min(1024 * 1024, size - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > size:
                        raise ValueError(f'{name}: serwer zwrócił za dużo danych')
                    stream.write(chunk)
                    transfer_sha256.update(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        authenticated_sha256 = _file_hash(temporary, name)
        if (transfer_sha256.hexdigest() != authenticated_sha256
                or _sha256(temporary) != authenticated_sha256):
            raise ValueError(f'{name}: weryfikacja SHA-256 zapisanego pliku nie powiodła się')
        os.replace(temporary, root / name)
        return authenticated_sha256
    finally:
        temporary.unlink(missing_ok=True)


def _verify(root):
    if any(root.glob('.quickmt-*')):
        raise ValueError('Pozostał plik częściowy; uruchom ponownie pobieranie')
    receipt = json.loads((root / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    if not isinstance(receipt, dict) or receipt.get('revision') != QUICKMT_REVISION:
        raise ValueError('Nieprawidłowa rewizja w SHA256SUMS.json')
    hashes = receipt.get('files')
    if not isinstance(hashes, dict) or set(hashes) != set(FILES):
        raise ValueError('Niekompletny manifest SHA256SUMS.json')
    for name in FILES:
        # Verify both the upstream identity and the receipt, never trust an
        # attacker-modified receipt as the only integrity check.
        if _file_hash(root / name, name) != hashes[name]:
            raise ValueError(f'{name}: niezgodny SHA-256')
    if (root / 'ATTRIBUTION.txt').read_text(encoding='utf-8') != ATTRIBUTION:
        raise ValueError('Brak poprawnej informacji o autorze i licencji ATTRIBUTION.txt')


def verify_installation(root):
    """Offline completeness, upstream pins and SHA-256 for every required file."""
    root = _directory(root)
    with _lock(root, readonly=True):
        _verify(root)


def install(root, *, opener=None):
    root = _directory(root, create=True)
    with _lock(root):
        os.chmod(root, 0o700)
        # Recover even after SIGKILL/power loss. No verified final file is
        # removed. Temporary files are private and validated by _directory.
        for partial in root.glob('.quickmt-*'):
            partial.unlink()
        hashes = {}
        for name in FILES:
            try:
                hashes[name] = _file_hash(root / name, name)
                print(f'OK: {name} — przypięty plik już istnieje', flush=True)
            except (OSError, ValueError):
                print(f'Pobieranie: {name} ({FILES[name][0]} bajtów)', flush=True)
                hashes[name] = _download(root, name, opener or _open)
        _atomic_write(root, 'ATTRIBUTION.txt', ATTRIBUTION.encode('utf-8'))
        receipt = dict(repository='quickmt/quickmt-en-pl', revision=QUICKMT_REVISION,
                       license='CC-BY-4.0', author='QuickMT', files=hashes)
        _atomic_write(root, 'SHA256SUMS.json',
                      (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        _verify(root)
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description='Jawne pobranie przypiętego QuickMT EN→PL, bez instalacji bibliotek.')
    parser.add_argument('--model-dir', type=Path, default=default_model_dir())
    parser.add_argument('--check-files', action='store_true', help='Tylko kontrola offline, bez pobierania')
    arguments = parser.parse_args(argv)
    try:
        if arguments.check_files:
            verify_installation(arguments.model_dir)
        else:
            install(arguments.model_dir)
    except (OSError, ValueError, HTTPException) as error:
        print(f'QuickMT: {error}\nUruchom ponownie to samo polecenie po usunięciu przyczyny. '
              'Poprawne pliki zostaną zachowane; uszkodzone pobrane ponownie.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('QuickMT: przerwano. Uruchom ponownie to samo polecenie.', file=sys.stderr)
        return 130
    print(f'QuickMT: komplet plików, przypięta rewizja i SHA-256 poprawne: {arguments.model_dir}')
    print('To nie jest jeszcze potwierdzenie ładowania modelu przez CTranslate2.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())