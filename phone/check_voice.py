"""Pocket 한국어 원본·전화 음질 샘플과 합성 시간, STT 결과를 저장한다."""
import audioop
import json
import time
import wave
from pathlib import Path
from audio import Speech
from tts import synthesize_native

folder=Path('/runtime/samples');folder.mkdir(parents=True,exist_ok=True)
records=[]
for name,text in [('welcome','안녕하세요. 인공지능 접수 비서입니다. 어떤 업무로 연락하셨나요?'),('request','어떤 정산서의 금액을 수정하면 될까요? 문서 이름이나 대상 기간을 말씀해 주세요.')]:
    start=time.perf_counter();pcm,rate=synthesize_native(text);elapsed=time.perf_counter()-start
    phone=audioop.ratecv(pcm,2,1,rate,8000,None)[0]
    for suffix,data,hz in [('24k',pcm,rate),('phone-8k',phone,8000)]:
        with wave.open(str(folder/('pocket-'+name+'-'+suffix+'.wav')),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(hz);out.writeframes(data)
    assert len(phone)>16000,'한국어 음성 생성 실패'
    records.append({'text':text,'generation_seconds':round(elapsed,3),'audio_seconds':round(len(pcm)/2/rate,3),'first_load_included':name=='welcome'})
speech=Speech()
for entry,name in zip(records,['welcome','request']):
    with wave.open(str(folder/('pocket-'+name+'-phone-8k.wav')),'rb') as stream: pcm=stream.readframes(stream.getnframes())
    start=time.perf_counter();entry['stt_text']=speech.transcribe(pcm);entry['stt_seconds']=round(time.perf_counter()-start,3)
    assert entry['stt_text'].strip(),'전사 결과가 비어 있습니다.'
Path('/runtime/voice-check.json').write_text(json.dumps({'tts':'Pocket TTS Korean 100M','stt':'faster-whisper small CPU int8','samples':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(records,ensure_ascii=False,indent=2))
