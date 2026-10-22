import json
from pathlib import Path
from audio import Speech, synthesize
pcm=synthesize('안녕하세요. 정산서 금액을 수정해 주세요.')
assert len(pcm)>16000,'한국어 음성 생성 실패'
text=Speech().transcribe(pcm)
assert text.strip(),'전사 결과가 비어 있습니다.'
Path('/runtime').mkdir(exist_ok=True)
Path('/runtime/voice-check.json').write_text(json.dumps({'tts':'espeak-ng/ko','stt':'faster-whisper','text':text,'audio_bytes':len(pcm)},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: local Korean TTS and Whisper inference',text)
