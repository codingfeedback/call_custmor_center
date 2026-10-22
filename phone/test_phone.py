import asyncio
import math
import struct
import unittest
from audio import Segmenter, packet, read_packet
from config import render
ENV={'SIP_TEST_PASSWORD':'test_only_1234567890'}
class ConfigTests(unittest.TestCase):
    def test_local_only(self):
        config=render(ENV)
        self.assertNotIn('[provider]',config['pjsip.conf'])
        self.assertIn('auth=test-auth',config['pjsip.conf'])
        self.assertNotIn('Dial(',config['extensions.conf'])
        self.assertIn('AudioSocket('+'$'+'{CALL_UUID},127.0.0.1:9092)',config['extensions.conf'])
    def test_provider(self):
        config=render({**ENV,'PROVIDER_CIDRS':'203.0.113.4/32','INBOUND_DID':'07012345678','PUBLIC_IP':'198.51.100.2'})
        self.assertIn('match=203.0.113.4/32',config['pjsip.conf'])
        self.assertIn('exten => 07012345678,1',config['extensions.conf'])
        self.assertNotIn('_X.',config['extensions.conf'])
    def test_bad_config(self):
        for change in [{'SIP_TEST_PASSWORD':'CHANGE_ME_TO_A_RANDOM_PASSWORD'},{'INBOUND_DID':'123\nSystem(evil)'},{'PROVIDER_CIDRS':'0.0.0.0/0'},{'PUBLIC_IP':'not-an-ip'}]:
            with self.assertRaises(ValueError): render({**ENV,**change})
class AudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_split_packet(self):
        reader=asyncio.StreamReader();data=packet(0x10,b'\x01\x00'*160)
        reader.feed_data(data[:1]);reader.feed_data(data[1:4]);reader.feed_data(data[4:])
        self.assertEqual(await read_packet(reader),(0x10,b'\x01\x00'*160))
    async def test_bad_packet(self):
        reader=asyncio.StreamReader();reader.feed_data(struct.pack('!BH',0x10,60000))
        with self.assertRaises(ValueError): await read_packet(reader)
    def test_segment(self):
        segment=Segmenter();self.assertIsNone(segment.push(b'\0'*320))
        voiced=struct.pack('<160h',*[int(2000*math.sin(i/3)) for i in range(160)])
        for _ in range(20): self.assertIsNone(segment.push(voiced))
        for _ in range(45): output=segment.push(b'\0'*320)
        self.assertTrue(output);self.assertFalse(segment.frames)
    def test_noise(self):
        segment=Segmenter();segment.push(struct.pack('<160h',*([2000]*160)))
        for _ in range(45): output=segment.push(b'\0'*320)
        self.assertEqual(output,b'')
if __name__=='__main__': unittest.main()
