import json
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4
from game_optimization_linux.config import CONFIG_DIR
from game_optimization_linux.models.narrator import NarratorGameSettings
from game_optimization_linux.services.narrator_persistence import _atomic_json_write
from .audio_balance import validate_target

class Profiles:
    def __init__(self, path=CONFIG_DIR / 'profiles.json'):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text())
            if self.data.get('version') != 1:
                raise ValueError('Unsupported profile schema')
        else:
            self.data = {'version': 1, 'selected': '', 'profiles': []}
            self.create('Domyślny')

    def persist(self):
        _atomic_json_write(self.path, self.data)

    def commit(self, data):
        # A failed write must not make status/events report unsaved data as saved.
        _atomic_json_write(self.path, data)
        self.data = data

    def selected(self):
        return self.get(self.data['selected'])

    def get(self, key):
        return next(p for p in self.data['profiles'] if p['id'] == key)

    def settings(self):
        p = self.selected()
        settings = NarratorGameSettings.from_dict(p['settings'], expected_game_key=p['id'])
        return replace(settings, audio_balance_target=validate_target(settings.audio_balance_target))

    def create(self, name):
        name = self.validate_name(name)
        key = 'local-' + uuid4().hex[:24]
        settings = replace(NarratorGameSettings.default(key), enabled=True)
        data = deepcopy(self.data)
        data['profiles'].append({'id': key, 'name': name, 'settings': settings.to_dict(), 'ocr': {'mode': 'automatic'}})
        data['selected'] = key
        self.commit(data)
        return key

    @staticmethod
    def validate_name(name):
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or any(c in name for c in '\r\n\0'):
            raise ValueError('Podaj nazwę profilu (1–100 znaków)')
        return name.strip()

    def select(self, key):
        self.get(key)
        self.commit({**self.data, 'selected': key})

    def rename(self, name):
        name = self.validate_name(name)
        data = deepcopy(self.data)
        next(p for p in data['profiles'] if p['id'] == data['selected'])['name'] = name
        self.commit(data)

    def delete(self):
        if len(self.data['profiles']) <= 1:
            raise ValueError('Zachowaj przynajmniej jeden profil')
        remaining = [p for p in self.data['profiles'] if p['id'] != self.data['selected']]
        self.commit({**self.data, 'profiles': remaining, 'selected': remaining[0]['id']})

    def update(self, values, *, ocr_mode=None):
        if ocr_mode is not None and ocr_mode not in ('automatic', 'classic'):
            raise ValueError('Unknown OCR mode')
        p = self.selected()
        raw = {**p['settings'], **values, 'game_key': p['id'], 'enabled': True}
        validated = NarratorGameSettings.from_dict(raw, expected_game_key=p['id'])
        validated = replace(validated, audio_balance_target=validate_target(validated.audio_balance_target))
        data = deepcopy(self.data)
        candidate = next(item for item in data['profiles'] if item['id'] == p['id'])
        candidate['settings'] = validated.to_dict()
        if ocr_mode is not None: candidate['ocr'] = {'mode': ocr_mode}
        self.commit(data)

    def reset(self, section):
        defaults = replace(NarratorGameSettings.default(self.selected()['id']), enabled=True).to_dict()
        fields = {'recognition': ('ocr_provider_id','capture_sampling_hz','visual_change_threshold','stabilization_ms','ocr_min_confidence','duplicate_cooldown_ms'), 'voice': ('voice_id','speech_rate','adaptive_speech_rate','volume','noise_scale','noise_w_scale','read_speaker_names','translation_profile_id','subtitle_language_mode'), 'audio': ('audio_balance_enabled','audio_balance_target','audio_balance_db','normalize_narrator'), 'region': ('subtitle_region',)}
        if section == 'profile':
            self.update(defaults, ocr_mode='automatic')
        elif section in fields:
            self.update({k: defaults[k] for k in fields[section]},
                        ocr_mode='automatic' if section == 'recognition' else None)
        else:
            raise ValueError('Unknown reset section')