"""Asterisk 수신 전용 설정. 외부 트렁크는 명시한 CIDR과 DID만 허용."""
import ipaddress
import os
import re
from pathlib import Path

def render(env):
    password = env.get('SIP_TEST_PASSWORD', '')
    if len(password) < 16 or not re.fullmatch(r'[A-Za-z0-9_-]+', password) or password.startswith('CHANGE_ME'):
        raise ValueError('16자 이상의 무작위 SIP_TEST_PASSWORD가 필요합니다.')
    did = env.get('INBOUND_DID', '07000000000')
    if not re.fullmatch(r'\+?\d{3,20}', did):
        raise ValueError('잘못된 INBOUND_DID')
    public = env.get('PUBLIC_IP', '')
    if public:
        public = str(ipaddress.IPv4Address(public))
    cidrs = [str(ipaddress.ip_network(x.strip(), strict=False)) for x in env.get('PROVIDER_CIDRS', '').split(',') if x.strip()]
    if any(ipaddress.ip_network(c).prefixlen == 0 for c in cidrs):
        raise ValueError('전체 인터넷 CIDR은 허용하지 않습니다.')
    if env.get('SIP_BIND_IP', '127.0.0.1') != '127.0.0.1' and (not public or not cidrs):
        raise ValueError('외부 SIP 공개에는 PUBLIC_IP와 PROVIDER_CIDRS가 필요합니다.')
    transport = f'external_signaling_address={public}\nexternal_media_address={public}\nlocal_net=172.16.0.0/12\n' if public else ''
    pjsip = f'''[global]
type=global
endpoint_identifier_order=ip,username
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060
{transport}
[1001]
type=endpoint
context=from-test
disallow=all
allow=ulaw,alaw
auth=test-auth
aors=1001
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
[test-auth]
type=auth
auth_type=userpass
username=1001
password={password}
[1001]
type=aor
max_contacts=1
remove_existing=yes
'''
    if cidrs:
        pjsip += '[provider]\ntype=endpoint\ncontext=from-provider\ndisallow=all\nallow=ulaw,alaw\ndirect_media=no\nrtp_symmetric=yes\nforce_rport=yes\n[provider-identify]\ntype=identify\nendpoint=provider\n' + ''.join(f'match={c}\n' for c in cidrs)
    dialplan = f'''[from-test]
exten => 1000,1,Gosub(handle-call,s,1)
 same => n,Hangup()
[from-provider]
exten => {did},1,Gosub(handle-call,s,1)
 same => n,Hangup()
[handle-call]
exten => s,1,AGI(/app/phone/call_id.py)
 same => n,GotoIf($["${{CALL_UUID}}" = ""]?done)
 same => n,Answer()
 same => n,Set(TIMEOUT(absolute)=300)
 same => n,AudioSocket(${{CALL_UUID}},127.0.0.1:9092)
 same => n(done),Hangup()
'''
    return {'pjsip.conf': pjsip, 'extensions.conf': dialplan,
            'rtp.conf': '[general]\nrtpstart=18000\nrtpend=18020\n',
            'modules.conf': '[modules]\nautoload=yes\nnoload=chan_sip.so\nnoload=chan_iax2.so\nnoload=res_pjsip_endpoint_identifier_anonymous.so\n',
            'manager.conf': '[general]\nenabled=no\n', 'http.conf': '[general]\nenabled=no\n'}

if __name__ == '__main__':
    for name, value in render(os.environ).items():
        Path('/etc/asterisk', name).write_text(value, encoding='utf-8')
