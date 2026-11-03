"""QuickMT tokenization over the existing CPU/JSONL translation boundary.

Preserve the tested beam sizes, decoding defaults and CPU thread policy.
Only the model and its required tokenization differ in the initial A/B.
"""
from pathlib import Path

from game_optimization_linux.services.narrator_translation_worker import (
    _TranslationEngine, main as serve,
)


class QuickMTTokenizer:
    def __init__(self, model_file):
        from sentencepiece import SentencePieceProcessor
        source = Path(model_file)
        self.source = SentencePieceProcessor(model_file=str(source))
        self.target = SentencePieceProcessor(model_file=str(source.with_name('tgt.spm.model')))

    def encode(self, text, *, out_type):
        if out_type is not str:
            raise TypeError('QuickMT requires string tokens')
        # Matches upstream QuickMT Translator.tokenize, including source EOS.
        return self.source.encode(text, out_type=str) + ['</s>']

    def decode(self, tokens):
        return self.target.decode(tokens)


class QuickMTEngine(_TranslationEngine):
    def __init__(self, model_dir, tokenizer_path, target_prefix='', *,
                 translator_factory=None, tokenizer_factory=None):
        super().__init__(model_dir, tokenizer_path, target_prefix,
                         translator_factory=translator_factory,
                         tokenizer_factory=tokenizer_factory or QuickMTTokenizer)


def main(argv=None, *, engine_factory=QuickMTEngine):
    return serve(argv, engine_factory=engine_factory)


if __name__ == '__main__':
    raise SystemExit(main())