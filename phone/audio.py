import audioop
import io
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

RATE = 8000
FRAME_BYTES = 320

def packet(kind, payload=b''):
    if len(payload) > 65535:
        raise ValueError('AudioSocket 프레임이 너무 큽니다.')
    return struct.pack('!BH', kind, len(payload)) + payload

async def read_packet(reader):
    header = await reader.readexactly(3)
    kind, length = struct.unpack('!BH', header)
    if length > 3200:
        raise ValueError('지원하지 않는 프레임 길이')
    return kind, await reader.readexactly(length)

class Segmenter:
    # shortcut: 단순 에너지 기준이므로 소음에 민감함, 실제 회선 소음이 크면 학습형 VAD로 교체.
    def __init__(self, threshold=450):
        self.threshold = threshold
        self.frames = bytearray()
        self.speech_bytes = 0
        self.silence_bytes = 0

    def push(self, pcm):
        if len(pcm) % 2:
            raise ValueError('PCM16 바이트 수 오류')
        voiced = audioop.rms(pcm, 2) > self.threshold
        if voiced:
            self.speech_bytes += len(pcm)
            self.silence_bytes = 0
        elif not self.frames:
            return None
        else:
            self.silence_bytes += len(pcm)
        self.frames.extend(pcm)
        if self.silence_bytes >= RATE * 2 * 0.9 or len(self.frames) >= RATE * 2 * 20:
            output = bytes(self.frames) if self.speech_bytes >= RATE * 2 * 0.25 else b''
            self.__init__(self.threshold)
            return output
        return None

def synthesize(text):
    if not text or len(text) > 2500:
        raise ValueError('음성 출력 텍스트 길이 오류')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder, 'reply.wav')
        subprocess.run(['espeak-ng', '-v', 'ko', '-s', '155', '-w', str(path), '--stdin'], input=text.encode('utf-8'), check=True, timeout=30, stdout=subprocess.DEVNULL)
        with wave.open(str(path), 'rb') as stream:
            if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
                raise ValueError('지원하지 않는 TTS 오디오')
            pcm = stream.readframes(stream.getnframes())
            return audioop.ratecv(pcm, 2, 1, stream.getframerate(), RATE, None)[0]

class Speech:
    def __init__(self):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(os.environ.get('WHISPER_MODEL', 'small'), device='cpu', compute_type='int8', download_root='/models/whisper')

    def transcribe(self, pcm):
        # WAV를 메모리에서만 만들고 원음은 파일에 저장하지 않는다.
        target = io.BytesIO()
        with wave.open(target, 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(RATE)
            stream.writeframes(pcm)
        target.seek(0)
        segments, _ = self.model.transcribe(target, language='ko', beam_size=3, condition_on_previous_text=False, vad_filter=True)
        return ' '.join(s.text.strip() for s in segments).strip()
