"""Browser regression for manual screenshot disclosures (Chromium, stdlib only).
Run in the existing aurora-web container with the repository mounted at /src:
  python3 tests/docs-disclosures.py
Checks deferred images, animations, rapid toggles, real keyboard events, mobile
width and reduced motion against the generated Appearance guide.
"""
import base64, json, os, socket, struct, subprocess, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'work/docs-guide-check'
OUTPUT.mkdir(parents=True, exist_ok=True)
TEST = r'''
(async function () {
 var d=document.querySelector('details.screenshots'),s=d.querySelector('summary'),img=d.querySelector('img');
 var wait=ms=>new Promise(r=>setTimeout(r,ms));
 function check(condition,message){if(!condition)throw Error(message);}
 try {
 check(!d.open,'initially closed');
 check(img.naturalWidth===0,'closed image deferred');
 s.click(); await wait(300); check(d.open,'opens');
 check(!d.style.overflow,'opening cleanup');
 check(img.naturalWidth>0,'expanded image loaded');
 s.click(); await wait(300); check(!d.open,'closes');
 s.click(); await wait(30); s.click(); await wait(30); s.click(); await wait(300);
 check(d.open,'rapid toggle settles open');
 check(d.getBoundingClientRect().height>100,'content visible');
 check(!d.style.overflow,'rapid toggle cleanup');
 check(document.documentElement.scrollWidth<=innerWidth,'no mobile overflow');
 return 'PASS: initial collapse, deferred image, open, close, rapid toggles, mobile width; reduced='+matchMedia('(prefers-reduced-motion: reduce)').matches;
 } catch(e){throw e;}
})();
'''

class CDP:
    def __init__(self, url):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=20)
        nonce = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
        header=b''
        while not header.endswith(b'\r\n\r\n'): header+=self.sock.recv(1)
        assert header.startswith(b'HTTP/1.1 101 '), header
        self.seq=0
    def read(self, n):
        data=b''
        while len(data)<n:
            part=self.sock.recv(n-len(data))
            if not part: raise RuntimeError('Browser socket closed')
            data+=part
        return data
    def call(self, method, params=None):
        self.seq+=1
        payload=json.dumps(dict(id=self.seq,method=method,params=params or {})).encode()
        mask=os.urandom(4); n=len(payload)
        header=bytes([0x81,0x80|n]) if n<126 else bytes([0x81,0xfe])+struct.pack('!H',n)
        self.sock.sendall(header+mask+bytes(b^mask[i%4] for i,b in enumerate(payload)))
        while True:
            op,n=self.read(2); n&=127
            if n==126:n=struct.unpack('!H',self.read(2))[0]
            elif n==127:n=struct.unpack('!Q',self.read(8))[0]
            data=self.read(n)
            if op&15==1:
                response=json.loads(data)
                if response.get('id')==self.seq:
                    assert 'error' not in response,response
                    return response['result']
    def evaluate(self, js):
        response=self.call('Runtime.evaluate',dict(expression=js,awaitPromise=True,returnByValue=True))
        assert 'exceptionDetails' not in response,response
        return response['result'].get('value')

for width, reduced in ((390, False), (390, True), (1440, False), (1440, True)):
    with tempfile.TemporaryDirectory() as profile:
        chrome=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--remote-debugging-port=9222','--remote-allow-origins=*','--window-size=390,844','--user-data-dir='+profile]+(['--force-prefers-reduced-motion'] if reduced else [])+['about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    tabs=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json')); break
                except Exception:time.sleep(.1)
            c=CDP(tabs[0]['webSocketDebuggerUrl'])
            c.call('Page.enable')
            c.call('Emulation.setDeviceMetricsOverride', dict(width=width, height=844, deviceScaleFactor=1, mobile=width < 600))
            c.call('Page.navigate',dict(url=(ROOT / 'docs/manual/appearance.html').as_uri()))
            time.sleep(.5)
            c.evaluate("document.querySelector('details.screenshots').scrollIntoView({block: 'center'})")
            result=c.evaluate(TEST)
            assert result.startswith('PASS'), result
            print(f'{result}; width={width}',flush=True)
            c.call('Page.bringToFront')
            c.evaluate("document.querySelector('details.screenshots > summary').focus()")
            for kind in ('keyDown','keyUp'):
                c.call('Input.dispatchKeyEvent',dict(type=kind,key='Enter',code='Enter',windowsVirtualKeyCode=13, text='\r' if kind == 'keyDown' else ''))
            time.sleep(.4)
            assert c.evaluate("document.querySelector('details.screenshots').open") is False,'Keyboard Enter did not close'
            for kind in ('keyDown','keyUp'):
                c.call('Input.dispatchKeyEvent',dict(type=kind,key='Enter',code='Enter',windowsVirtualKeyCode=13, text='\r' if kind == 'keyDown' else ''))
            time.sleep(.4)
            assert c.evaluate("document.querySelector('details.screenshots').open") is True,'Keyboard Enter did not reopen'
            print('PASS: real keyboard Enter closes and opens',flush=True)
            shot=c.call('Page.captureScreenshot')['data']
            (OUTPUT / (('mobile-' if width < 600 else 'desktop-')+('reduced' if reduced else 'animated')+'.png')).write_bytes(base64.b64decode(shot))
            if width == 390 and not reduced:
                c.call('Emulation.setScriptExecutionDisabled', dict(value=True))
                c.call('Page.navigate', dict(url=(ROOT / 'docs/manual/appearance.html').as_uri()))
                time.sleep(.5)
                c.evaluate("document.querySelector('details.screenshots > summary').focus()")
                assert c.evaluate("document.querySelector('details.screenshots').open") is False
                for kind in ('keyDown', 'keyUp'):
                    c.call('Input.dispatchKeyEvent', dict(type=kind, key='Enter', code='Enter', windowsVirtualKeyCode=13, text='\r' if kind == 'keyDown' else ''))
                time.sleep(.4)
                assert c.evaluate("document.querySelector('details.screenshots').open") is True
                print('PASS: native disclosure without JavaScript', flush=True)
        finally:
            chrome.terminate();chrome.wait(10)
