"""Immutable public metadata, shared by the component catalog and provider.

SHA-256 of the three small JSON files and upstream README was independently
computed from the pinned revision on 2026-11-03 and cross-checked against the
previously pinned Git blob identities. No model is downloaded on import.
"""
QUICKMT_REVISION = '6209580ce1fe525214f29fc39725007b73410109'
QUICKMT_COMPONENT_ID = 'translation.quickmt-en-pl'
QUICKMT_PROVIDER_ID = 'quickmt-ctranslate2-en-pl-' + QUICKMT_REVISION + '-shared-decoding-v1'
QUICKMT_BASE_URL = 'https://huggingface.co/quickmt/quickmt-en-pl/resolve/' + QUICKMT_REVISION
QUICKMT_FILES = {
    'model.bin': (401699775, 'sha256', '7f02e09d52f04f77cb6b2da251235149053387812e3cfb73afb99882483cee72'),
    'config.json': (223, 'sha256', '66edc5d58ceb812a41b4b784497001f815c35400884f40984b19de29e1bc3d69'),
    'source_vocabulary.json': (332684, 'sha256', '360491222a324bb7ecfce3789b7c30d400e861daf1b766ac03263e7740edf2d3'),
    'target_vocabulary.json': (381704, 'sha256', '9c0e7f04ee081a22910848dfa23d7d39b356f6887a2cd966e2b4fa6a67f6f4f5'),
    'src.spm.model': (585058, 'sha256', '83fa4a21ff8359b8827f033977c0e563fd0786ba84bbc93d4a1e22a0dd81ee7f'),
    'tgt.spm.model': (605240, 'sha256', 'b6ad874c44613df56fb48be31fb64b6b5fc96a14a7888e802b0f91dbf98a8836'),
}
QUICKMT_DOWNLOAD_FILES = dict(QUICKMT_FILES, **{
    'README.md': (4429, 'sha256', 'a4e7fb74b9c60ea837a2ae412690391b2e9c0ae6597f17ebcdbed2247a2765d3'),
})
QUICKMT_ATTRIBUTION = (
    'QuickMT EN→PL — quickmt/quickmt-en-pl. Autor / wydawca: QuickMT. '
    'https://huggingface.co/quickmt/quickmt-en-pl; rewizja ' + QUICKMT_REVISION + '. '
    'CC BY 4.0: https://creativecommons.org/licenses/by/4.0/. '
    'Oryginalne pliki bez zmian, bez konwersji ani kwantyzacji; README zachowany. '
    'Adapter NarratorVerse nie jest biblioteką QuickMT.'
)