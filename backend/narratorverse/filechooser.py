"""Native FileChooser portal; grant access to both Piper files, not the whole home."""
import asyncio
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote
from uuid import uuid4
from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from game_optimization_linux.services.narrator_tts import validate_piper_voice_config


def pair_from_uris(uris):
    paths = []
    for uri in uris:
        parsed = urlparse(uri)
        if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
            raise ValueError('Wybierz lokalne pliki głosu')
        paths.append(Path(unquote(parsed.path)))
    models = [p for p in paths if p.suffix.lower() == '.onnx']
    if len(models) != 1 or len(paths) != 2:
        raise ValueError('Zaznacz razem model .onnx i jego konfigurację .onnx.json (Ctrl + kliknięcie).')
    model = models[0]
    configs = [p for p in paths if p.name == model.name + '.json']
    if len(configs) != 1 or not model.is_file() or model.stat().st_size == 0:
        raise ValueError('Model i konfiguracja muszą mieć nazwy głos.onnx oraz głos.onnx.json')
    validate_piper_voice_config(configs[0])
    return model, configs[0]


async def choose_files(cancelled=None):
    bus = await MessageBus().connect()
    token = 'narratorverse_' + uuid4().hex
    handle = '/org/freedesktop/portal/desktop/request/' + bus.unique_name[1:].replace('.', '_') + '/' + token
    response = asyncio.get_running_loop().create_future()
    received = False
    def receive(message):
        if message.message_type == MessageType.SIGNAL and message.path == handle and message.member == 'Response' and not response.done():
            response.set_result(message.body)
    bus.add_message_handler(receive)
    match = "type='signal',interface='org.freedesktop.portal.Request',member='Response'"
    await bus.call(Message(destination='org.freedesktop.DBus', path='/org/freedesktop/DBus', interface='org.freedesktop.DBus', member='AddMatch', signature='s', body=[match]))
    try:
        reply = await bus.call(Message(destination='org.freedesktop.portal.Desktop', path='/org/freedesktop/portal/desktop', interface='org.freedesktop.portal.FileChooser', member='OpenFile', signature='ssa{sv}', body=['', 'Importuj głos — wybierz .onnx i .onnx.json', {'handle_token': Variant('s', token), 'multiple': Variant('b', True), 'filters': Variant('a(sa(us))', [['Głos Piper', [[0, '*.onnx'], [0, '*.onnx.json']]]])}]))
        if reply.message_type == MessageType.ERROR: raise RuntimeError('Nie można otworzyć systemowego wyboru plików: ' + str(reply.body))
        handle = reply.body[0]
        deadline = asyncio.get_running_loop().time() + 300
        while not response.done():
            if cancelled is not None and cancelled.is_set(): return None
            if asyncio.get_running_loop().time() >= deadline: raise RuntimeError('Przekroczono czas wyboru plików')
            await asyncio.wait((response,), timeout=.2)
        code, values = response.result()
        received = True
        if code == 1: return None
        if code: raise RuntimeError('Wybór plików nie powiódł się')
        return values['uris'].value
    finally:
        if not received:
            await bus.call(Message(destination='org.freedesktop.portal.Desktop', path=handle, interface='org.freedesktop.portal.Request', member='Close'))
        bus.remove_message_handler(receive)
        bus.disconnect()


def import_from_chooser(tts, cancelled=None):
    uris = asyncio.run(choose_files(cancelled))
    if uris is None: return None
    model, config = pair_from_uris(uris)
    import onnxruntime
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    try:
        session = onnxruntime.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
        names = {item.name for item in session.get_inputs()}
        if not {'input', 'input_lengths', 'scales'} <= names:
            raise ValueError('Model ONNX nie ma wejść wymaganych przez Piper')
        del session
    except Exception as error:
        raise ValueError('Nie można wczytać modelu głosu Piper: ' + str(error)) from error
    # Document portal grants may live in separate directories. Assemble the pair
    # only in a private temporary directory before the upstream validated import.
    with tempfile.TemporaryDirectory(prefix='narratorverse-voice-') as temp:
        destination = Path(temp) / model.name
        shutil.copyfile(model, destination)
        shutil.copyfile(config, destination.with_name(destination.name + '.json'))
        return tts.import_custom_voice(destination).voice_id