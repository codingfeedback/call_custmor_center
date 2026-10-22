"""로컬 SIP 인증/수신/실제 RTP 안내 음성을 검증한다. 유료 전화망은 사용하지 않는다."""
import hashlib
import os
import re
import socket
import uuid


def run():
    sip=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sip.bind(('127.0.0.1',0));sip.settimeout(15)
    rtp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);rtp.bind(('127.0.0.1',0));rtp.settimeout(20)
    port=sip.getsockname()[1];callid=uuid.uuid4().hex;tag=uuid.uuid4().hex[:12];uri='sip:1000@127.0.0.1'
    body='v=0\r\no=test 1 1 IN IP4 127.0.0.1\r\ns=test\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio %d RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\na=sendrecv\r\n'%rtp.getsockname()[1]
    def send(method,cseq,auth='',to='',payload=''):
        request=(f'{method} {uri} SIP/2.0\r\nVia: SIP/2.0/UDP 127.0.0.1:{port};branch=z9hG4bK{uuid.uuid4().hex};rport\r\n'
                 f'Max-Forwards: 70\r\nFrom: <sip:1001@127.0.0.1>;tag={tag}\r\nTo: {to or "<sip:1000@127.0.0.1>"}\r\n'
                 f'Call-ID: {callid}\r\nCSeq: {cseq} {method}\r\nContact: <sip:1001@127.0.0.1:{port}>\r\n'
                 f'{auth}Content-Type: application/sdp\r\nContent-Length: {len(payload.encode())}\r\n\r\n{payload}')
        sip.sendto(request.encode(),('127.0.0.1',5060))
    def response():
        while True:
            result=sip.recv(65535).decode()
            if not result.startswith('SIP/2.0 100'): return result
    try:
        send('INVITE',1,payload=body);challenge=response();assert challenge.startswith('SIP/2.0 401'),challenge[:80]
        to=re.search(r'^To:\s*(.+)',challenge,re.M|re.I).group(1).strip();send('ACK',1,to=to)
        fields=dict(re.findall(r'(\w+)="([^"]*)"',challenge))
        md5=lambda value:hashlib.md5(value.encode()).hexdigest()
        digest=md5(md5('1001:'+fields['realm']+':'+os.environ['SIP_TEST_PASSWORD'])+':'+fields['nonce']+':'+md5('INVITE:'+uri))
        auth=f'Authorization: Digest username="1001", realm="{fields["realm"]}", nonce="{fields["nonce"]}", uri="{uri}", response="{digest}", algorithm=MD5\r\n'
        send('INVITE',2,auth=auth,payload=body)
        while True:
            result=response()
            if result.startswith('SIP/2.0 180'): continue
            assert result.startswith('SIP/2.0 200'),result[:80]
            break
        to=re.search(r'^To:\s*(.+)',result,re.M|re.I).group(1).strip();send('ACK',2,to=to)
        data,_=rtp.recvfrom(4096);assert len(data)>12 and data[0]>>6==2,'RTP 음성 없음'
        send('BYE',3,to=to)
        print('PASS: SIP 401 authentication -> authenticated INVITE -> 200/ACK -> RTP greeting -> BYE')
    finally:
        sip.close();rtp.close()

if __name__=='__main__':run()
