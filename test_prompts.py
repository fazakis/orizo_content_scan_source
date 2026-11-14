import unittest
import importlib.util
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
import time

from prompts import (
    ALL_PROMPTS,
    SAFE_PROMPTS,
    UNSAFE_PROMPTS,
    merge_second_opinion,
    unsafe_confidence,
)


def probabilities(safe_mass, unsafe_mass):
    return (
        [safe_mass / len(SAFE_PROMPTS)] * len(SAFE_PROMPTS)
        + [unsafe_mass / len(UNSAFE_PROMPTS)] * len(UNSAFE_PROMPTS)
    )


class PromptPolicyTests(unittest.TestCase):
    def test_prompt_order_matches_the_confidence_slice(self):
        self.assertEqual(ALL_PROMPTS[:len(SAFE_PROMPTS)], SAFE_PROMPTS)
        self.assertEqual(ALL_PROMPTS[len(SAFE_PROMPTS):], UNSAFE_PROMPTS)

    def test_confidence_uses_probability_mass(self):
        self.assertLess(unsafe_confidence(probabilities(0.95, 0.05)), 0.1)
        self.assertGreater(unsafe_confidence(probabilities(0.05, 0.95)), 0.9)

    def test_second_opinion_moves_both_directions(self):
        self.assertEqual(merge_second_opinion(0.70, 0.08, raise_cap=0.75), 0.08)
        self.assertEqual(merge_second_opinion(0.41, 0.91, raise_cap=0.75), 0.75)

    def test_second_opinion_cannot_raise_into_automatic_removal(self):
        self.assertLess(merge_second_opinion(0.41, 0.99, raise_cap=0.75), 0.90)


@unittest.skipUnless(importlib.util.find_spec('uvicorn'), 'requires lightweight uvicorn transport fixture')
class AdmissionTests(unittest.TestCase):
    def test_actual_image_command_rejects_overload_then_recovers(self):
        # Exercise the image's real server flags, without downloading ML models.
        line = next(line for line in Path(__file__).with_name('Dockerfile').read_text().splitlines()
                    if line.startswith('CMD '))
        command = json.loads(line[4:])[2]
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'fixture.py').write_text('''async def app(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': []})
    await send({'type': 'http.response.body', 'body': b'ok'})
''')
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
            args = shlex.split(command.replace('app:app', 'fixture:app')
                               .replace('8099', str(port)).replace('${CONTENT_SCAN_WORKERS}', '1'))
            proc = subprocess.Popen([sys.executable, '-m', *args], cwd=tmp,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clients = []
            try:
                for _ in range(100):
                    try:
                        c = socket.create_connection(('127.0.0.1', port), timeout=1)
                        clients.append(c); break
                    except OSError:
                        time.sleep(.05)
                else:
                    self.fail('Server did not start')
                # Three incomplete request headers occupy available slots.
                for _ in range(2):
                    clients.append(socket.create_connection(('127.0.0.1', port), timeout=1))
                time.sleep(.1)
                def request():
                    with socket.create_connection(('127.0.0.1', port), timeout=2) as c:
                        c.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
                        return c.recv(4096).split(b'\r\n', 1)[0]
                self.assertIn(b'503', request())
                for c in clients: c.close()
                clients.clear()
                time.sleep(.2)
                self.assertIn(b'200', request())
            finally:
                for c in clients: c.close()
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()


if __name__ == '__main__':
    unittest.main()
