"""Pocket TTS Korean 100M. 모델·음성 상태는 프로세스당 한 번 로드한다."""
import audioop
import threading
from functools import lru_cache

CONFIG = 'hf://seastar105/pocket-tts-korean-100m/korean.yaml@d5418f368ed97bc982ab80c5b639fe28f280636b'
VOICE = 'hf://kyutai/tts-voices/alba-mackenna/casual.wav'
_lock = threading.Lock()
_model = None
_state = None

@lru_cache(maxsize=16)
def synthesize_native(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 2500:
        raise ValueError('음성 출력 텍스트 길이 오류')
    global _model, _state
    # Pocket 모델은 thread-safe가 아니므로 로드와 합성을 같은 잠금으로 보호한다.
    with _lock:
        import torch
        if _model is None:
            from pocket_tts import TTSModel
            torch.set_num_threads(4)
            _model = TTSModel.load_model(config=CONFIG)
            _state = _model.get_state_for_audio_prompt(VOICE)
        audio = _model.generate_audio(_state, text).detach().cpu().clamp(-1, 1)
        pcm = (audio.numpy() * 32767).astype('<i2').tobytes()
        if not pcm:
            raise ValueError('빈 TTS 오디오')
        return pcm, _model.sample_rate

def synthesize(text):
    pcm, rate = synthesize_native(text)
    return audioop.ratecv(pcm, 2, 1, rate, 8000, None)[0]
