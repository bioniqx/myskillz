"""Black-box tests for oc-brainstorming/scripts: oc-server.cjs, oc-helper.js,
oc-start-server.sh, oc-stop-server.sh and oc-context.sh.

Each server test spawns the real oc-server.cjs against a throwaway session
directory in the system temp dir (never inside the repo) and talks to it over
real HTTP/WebSocket sockets. The script tests run the shell scripts against
temp project directories.
"""
import http.client
import json
import os
import queue
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.parse

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
OC_ROOT = os.path.dirname(os.path.dirname(TESTS_DIR))
SCRIPTS_DIR = os.path.join(OC_ROOT, 'oc-brainstorming', 'scripts')
SERVER_JS = os.path.join(SCRIPTS_DIR, 'oc-server.cjs')
HELPER_JS = os.path.join(SCRIPTS_DIR, 'oc-helper.js')
START_SH = os.path.join(SCRIPTS_DIR, 'oc-start-server.sh')
STOP_SH = os.path.join(SCRIPTS_DIR, 'oc-stop-server.sh')
CONTEXT_SH = os.path.join(SCRIPTS_DIR, 'oc-context.sh')

STARTUP_TIMEOUT = 10


def _clean_env(**extra):
    env = dict(os.environ)
    for var in list(env):
        if var.startswith('BRAINSTORM_'):
            env.pop(var)
    env.pop('CODEX_CI', None)
    env.pop('OC_MAX_LANES', None)
    env.update(extra)
    return env


def _drain(proc, q):
    try:
        for line in proc.stdout:
            q.put(line.rstrip('\n'))
    except Exception:
        pass


def _wait_for_json(q, predicate, timeout):
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        try:
            line = q.get(timeout=remaining)
        except queue.Empty:
            return None
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if predicate(data):
            return data


def _token_from_url(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.parse_qs(parsed.query)['key'][0]


def _http_get(port, path_and_query, timeout=5, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        conn.request('GET', path_and_query, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, body, resp.getheader('Set-Cookie')
    finally:
        conn.close()


def _fetch_real_content(port, token, timeout=5):
    """GET /?key=<token> returns a small bootstrap stub that sets the cookie;
    only a second GET / carrying that cookie returns the real screen."""
    status1, _, set_cookie = _http_get(port, '/?key=' + token, timeout=timeout)
    if status1 != 200 or not set_cookie:
        return status1, b''
    cookie_pair = set_cookie.split(';', 1)[0]
    status2, body2, _ = _http_get(port, '/', timeout=timeout, headers={'Cookie': cookie_pair})
    return status2, body2


def _build_ws_frame(opcode, payload):
    fin_opcode = 0x80 | opcode
    length = len(payload)
    mask_bit = 0x80
    if length < 126:
        header = bytes([fin_opcode, mask_bit | length])
    elif length < 65536:
        header = bytes([fin_opcode, mask_bit | 126]) + struct.pack('>H', length)
    else:
        header = bytes([fin_opcode, mask_bit | 127]) + struct.pack('>Q', length)
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return header + mask + masked


def _ws_handshake_request(host, port, token):
    return (
        'GET /?key={key} HTTP/1.1\r\n'
        'Host: {host}:{port}\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'
        'Sec-WebSocket-Version: 13\r\n'
        '\r\n'
    ).format(key=token, host=host, port=port).encode('utf-8')


def _recv_until(sock, delim, timeout):
    sock.settimeout(timeout)
    data = b''
    while delim not in data:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        data += chunk
    return data


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_dead(pid, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


class OcServerTests(unittest.TestCase):
    def start_server(self, env_extra=None):
        session_dir = os.path.realpath(tempfile.mkdtemp(prefix='ocbs-session-'))
        content_dir = os.path.join(session_dir, 'content')
        state_dir = os.path.join(session_dir, 'state')
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

        env = _clean_env(
            BRAINSTORM_DIR=session_dir,
            BRAINSTORM_HOST='127.0.0.1',
            BRAINSTORM_URL_HOST='localhost',
        )
        if env_extra:
            env.update(env_extra)

        proc = subprocess.Popen(
            ['node', SERVER_JS], cwd=SCRIPTS_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        q = queue.Queue()
        threading.Thread(target=_drain, args=(proc, q), daemon=True).start()

        info = _wait_for_json(q, lambda d: d.get('type') == 'server-started', STARTUP_TIMEOUT)
        if info is None:
            proc.kill()
            stderr = ''
            try:
                stderr = proc.stderr.read()
            except Exception:
                pass
            shutil.rmtree(session_dir, ignore_errors=True)
            self.fail('server did not start: ' + stderr)

        self.addCleanup(self.stop_server, proc, session_dir)
        return proc, info, q, session_dir, content_dir, state_dir

    def stop_server(self, proc, session_dir):
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(session_dir, ignore_errors=True)

    def write_screen(self, content_dir, name, html):
        with open(os.path.join(content_dir, name), 'w', encoding='utf-8') as f:
            f.write(html)

    def test_content_injection_literal_dollar_fragment(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        fragment = "<p>Price $&5 and $$3 and $'x and $`y</p>"
        self.write_screen(content_dir, 'screen.html', fragment)

        status, body = _fetch_real_content(info['port'], token)
        text = body.decode('utf-8')
        self.assertEqual(status, 200)
        self.assertIn("$&5", text, text[:2000])
        self.assertIn("$$3", text, text[:2000])
        self.assertIn("$'x", text, text[:2000])
        self.assertIn("$`y", text, text[:2000])

    def test_content_injection_literal_dollar_full_document(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        full_doc = (
            "<!DOCTYPE html><html><head></head><body>"
            "<p>Cost $&9 $$1 $'a $`b</p>"
            "</body></html>"
        )
        self.write_screen(content_dir, 'full.html', full_doc)

        status, body = _fetch_real_content(info['port'], token)
        text = body.decode('utf-8')
        self.assertEqual(status, 200)
        self.assertIn("$&9", text)
        self.assertIn("$$1", text)
        self.assertIn("$'a", text)
        self.assertIn("$`b", text)
        self.assertIn('<script>', text)

    def test_request_handler_crash_returns_500_and_server_keeps_serving(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        # Removing the content dir makes fs.readdirSync throw inside the '/'
        # handler (getNewestScreen). The handler must catch it, not crash.
        shutil.rmtree(content_dir)

        status, body = _fetch_real_content(info['port'], token)
        self.assertEqual(status, 500, body[:500])
        self.assertIsNone(proc.poll(), 'server process must still be alive after handler error')

        status2, body2, _ = _http_get(info['port'], '/does-not-exist?key=' + token)
        self.assertEqual(status2, 404)

    def test_message_handler_crash_does_not_kill_server(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        port = info['port']
        # Removing state_dir makes fs.appendFileSync throw inside handleMessage
        # when an event carries `choice`. The handler must catch it.
        shutil.rmtree(state_dir)

        sock = socket.create_connection(('127.0.0.1', port), timeout=5)
        try:
            sock.sendall(_ws_handshake_request('127.0.0.1', port, token))
            resp = _recv_until(sock, b'\r\n\r\n', 3)
            self.assertIn(b'101', resp)
            sock.sendall(_build_ws_frame(0x01, json.dumps({'type': 'click', 'choice': 'x'}).encode()))
            time.sleep(0.3)
        finally:
            sock.close()

        self.assertIsNone(proc.poll(), 'server process must survive a message-handler error')
        status, _, _ = _http_get(port, '/does-not-exist?key=' + token)
        self.assertEqual(status, 404)

    def test_signals_write_server_stopped_and_remove_server_info(self):
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=sig):
                proc, info, q, session_dir, content_dir, state_dir = self.start_server()
                info_file = os.path.join(state_dir, 'server-info')
                stopped_file = os.path.join(state_dir, 'server-stopped')
                self.assertTrue(os.path.exists(info_file))

                proc.send_signal(sig)
                deadline = time.time() + 5
                while time.time() < deadline and not os.path.exists(stopped_file):
                    time.sleep(0.05)

                self.assertTrue(os.path.exists(stopped_file), 'server-stopped was not written for signal %s' % sig)
                self.assertFalse(os.path.exists(info_file), 'server-info was not removed for signal %s' % sig)
                proc.wait(timeout=5)

    def test_session_dir_in_started_json_and_server_info(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        self.assertIn('session_dir', info)
        self.assertEqual(os.path.realpath(info['session_dir']), session_dir)

        info_file = os.path.join(state_dir, 'server-info')
        with open(info_file, encoding='utf-8') as f:
            written = json.loads(f.read().strip())
        self.assertEqual(os.path.realpath(written['session_dir']), session_dir)

    def test_files_route_url_decodes_and_serves(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        with open(os.path.join(content_dir, 'my image.png'), 'wb') as f:
            f.write(b'PNGDATA')

        status, body, _ = _http_get(info['port'], '/files/my%20image.png?key=' + token)
        self.assertEqual(status, 200)
        self.assertEqual(body, b'PNGDATA')

    def test_files_route_traversal_and_invalid_encoding_still_404(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        port = info['port']

        status, _, _ = _http_get(port, '/files/..%2f..%2fetc%2fpasswd?key=' + token)
        self.assertEqual(status, 404)

        status2, _, _ = _http_get(port, '/files/%zz?key=' + token)
        self.assertEqual(status2, 404)
        self.assertIsNone(proc.poll(), 'invalid percent-encoding must not crash the server')

        status3, _, _ = _http_get(port, '/does-not-exist?key=' + token)
        self.assertEqual(status3, 404)

    def test_watcher_ignores_symlink_and_fifo(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()

        target = os.path.join(session_dir, 'target.html')
        with open(target, 'w', encoding='utf-8') as f:
            f.write('<p>real content elsewhere</p>')
        os.symlink(target, os.path.join(content_dir, 'sym.html'))

        got = _wait_for_json(
            q, lambda d: d.get('type') == 'screen-added' and 'sym.html' in d.get('file', ''), 1.2
        )
        self.assertIsNone(got, 'a symlinked .html file must never trigger screen-added')

        if hasattr(os, 'mkfifo'):
            os.mkfifo(os.path.join(content_dir, 'pipe.html'))
            got_fifo = _wait_for_json(
                q, lambda d: d.get('type') == 'screen-added' and 'pipe.html' in d.get('file', ''), 1.2
            )
            self.assertIsNone(got_fifo, 'a non-regular (fifo) .html file must never trigger screen-added')

        self.write_screen(content_dir, 'real.html', '<p>a real screen</p>')
        got_real = _wait_for_json(
            q, lambda d: d.get('type') == 'screen-added' and 'real.html' in d.get('file', ''), 3
        )
        self.assertIsNotNone(got_real, 'a genuine regular .html file must trigger screen-added')

    def test_websocket_frame_in_same_packet_as_handshake(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        port = info['port']

        frame = _build_ws_frame(0x01, json.dumps({'type': 'click', 'choice': 'combo'}).encode())
        req = _ws_handshake_request('127.0.0.1', port, token)

        sock = socket.create_connection(('127.0.0.1', port), timeout=5)
        try:
            sock.sendall(req + frame)
            resp = _recv_until(sock, b'\r\n\r\n', 3)
            self.assertIn(b'101', resp)

            events_file = os.path.join(state_dir, 'events')
            deadline = time.time() + 3
            content = ''
            while time.time() < deadline:
                if os.path.exists(events_file):
                    with open(events_file, encoding='utf-8') as f:
                        content = f.read()
                    if content:
                        break
                time.sleep(0.05)
            self.assertIn('"choice":"combo"', content)
        finally:
            sock.close()

    def test_new_screen_renames_events_to_events_prev(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        port = info['port']

        self.write_screen(content_dir, 'a.html', '<p>first screen</p>')
        got = _wait_for_json(q, lambda d: d.get('type') == 'screen-added' and 'a.html' in d.get('file', ''), 3)
        self.assertIsNotNone(got)

        sock = socket.create_connection(('127.0.0.1', port), timeout=5)
        try:
            sock.sendall(_ws_handshake_request('127.0.0.1', port, token))
            self.assertIn(b'101', _recv_until(sock, b'\r\n\r\n', 3))
            sock.sendall(_build_ws_frame(0x01, json.dumps({'type': 'click', 'choice': 'keep-me'}).encode()))
            time.sleep(0.3)
        finally:
            sock.close()

        events_file = os.path.join(state_dir, 'events')
        events_prev_file = os.path.join(state_dir, 'events.prev')
        deadline = time.time() + 3
        while time.time() < deadline and not os.path.exists(events_file):
            time.sleep(0.05)
        with open(events_file, encoding='utf-8') as f:
            first_events = f.read()
        self.assertIn('keep-me', first_events)

        self.write_screen(content_dir, 'b.html', '<p>second screen</p>')
        got2 = _wait_for_json(q, lambda d: d.get('type') == 'screen-added' and 'b.html' in d.get('file', ''), 3)
        self.assertIsNotNone(got2)
        time.sleep(0.2)

        self.assertFalse(os.path.exists(events_file), 'events must be renamed away, not left in place')
        self.assertTrue(os.path.exists(events_prev_file), 'previous events must survive as events.prev')
        with open(events_prev_file, encoding='utf-8') as f:
            prev_events = f.read()
        self.assertIn('keep-me', prev_events)

    def test_no_external_assets_and_no_unknown_version(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])

        status, body = _fetch_real_content(info['port'], token)
        text = body.decode('utf-8')
        self.assertEqual(status, 200)
        self.assertNotIn('primeradiant.com', text)
        self.assertNotIn('src="http', text)
        self.assertNotIn('vunknown', text)

    def test_helper_js_click_text_normalized_and_multiselect_selected(self):
        harness = textwrap.dedent(r"""
            const fs = require('fs');
            const helperPath = process.argv[2];
            const src = fs.readFileSync(helperPath, 'utf8');

            function makeClassList(initial) {
              const set = new Set(initial);
              return {
                contains: (c) => set.has(c),
                add: (c) => set.add(c),
                remove: (c) => set.delete(c),
              };
            }
            function makeEl(text, choice, classes) {
              return {
                id: '',
                textContent: text,
                dataset: { choice },
                classList: makeClassList(classes),
                closest() { return null; },
              };
            }

            class FakeWS {
              constructor(url) {
                this.url = url;
                this.readyState = FakeWS.OPEN;
                FakeWS.sent.push(this);
              }
              send(data) { FakeWS.sent.messages.push(data); }
              close() {}
            }
            FakeWS.OPEN = 1;
            FakeWS.sent = [];
            FakeWS.sent.messages = [];

            const listeners = {};
            global.window = {
              sessionStorage: { getItem: () => null },
              location: { host: 'x', replace() {}, reload() {} },
            };
            global.WebSocket = FakeWS;
            global.document = {
              addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
              querySelector() { return null; },
              body: null,
              createElement() { return { style: {}, appendChild() {} }; },
            };

            eval(src);

            function dispatchClick(target) {
              (listeners['click'] || []).forEach((fn) => fn({ target }));
            }

            const longText = '  Hello   World  ' + 'x'.repeat(200);
            const single = makeEl(longText, 'a', []);
            const singleContainer = { dataset: {}, querySelectorAll: () => [] };
            single.closest = (sel) => (sel === '[data-choice]' ? single : (sel === '.options' || sel === '.cards' ? singleContainer : null));
            dispatchClick(single);

            const multi = makeEl('Pick me', 'b', ['selected']);
            const multiContainer = { dataset: { multiselect: '' }, querySelectorAll: () => [] };
            multi.closest = (sel) => (sel === '[data-choice]' ? multi : (sel === '.options' || sel === '.cards' ? multiContainer : null));
            dispatchClick(multi);

            window.brainstorm.choice('z', { note: 1 });

            console.log(JSON.stringify(FakeWS.sent.messages.map((m) => JSON.parse(m))));
        """)
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(harness)
            harness_path = f.name
        try:
            result = subprocess.run(
                ['node', harness_path, HELPER_JS], capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            events = json.loads(result.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(harness_path)

        self.assertEqual(len(events), 3)
        single_evt, multi_evt, choice_evt = events

        normalized_full = 'Hello World ' + 'x' * 200
        self.assertEqual(single_evt['text'], normalized_full[:120])
        self.assertLessEqual(len(single_evt['text']), 120)
        self.assertNotIn('selected', single_evt)

        self.assertEqual(multi_evt['text'], 'Pick me')
        self.assertIn('selected', multi_evt)
        self.assertTrue(multi_evt['selected'])

        # The server records only events that carry a `choice` key.
        self.assertEqual(choice_evt['choice'], 'z')
        self.assertEqual(choice_evt['value'], 'z')
        self.assertEqual(choice_evt['note'], 1)

    def test_node_check_syntax_server_and_helper(self):
        for script in (SERVER_JS, HELPER_JS):
            with self.subTest(script=script):
                result = subprocess.run(['node', '--check', script], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)


class StartStopScriptTests(unittest.TestCase):
    def setUp(self):
        self.project = os.path.realpath(tempfile.mkdtemp(prefix='ocbs-proj-'))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.addCleanup(self.kill_all)
        self.env = _clean_env()

    def pids(self):
        found = []
        root = os.path.join(self.project, '.oc-brainstorm')
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                pid_file = os.path.join(root, name, 'state', 'server.pid')
                if os.path.isfile(pid_file):
                    with open(pid_file, encoding='utf-8') as f:
                        found.append(int(f.read().strip()))
        return found

    def kill_all(self):
        for pid in self.pids():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def run_start(self, env=None):
        return subprocess.run(
            ['bash', START_SH, '--project-dir', self.project],
            capture_output=True, text=True, timeout=30,
            env=env or self.env, stdin=subprocess.DEVNULL,
        )

    def run_stop(self, session_dir):
        return subprocess.run(
            ['bash', STOP_SH, session_dir],
            capture_output=True, text=True, timeout=15,
            env=self.env, stdin=subprocess.DEVNULL,
        )

    def started_info(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_start_reports_session_dir_and_stop_keeps_project_session(self):
        info = self.started_info(self.run_start())
        self.assertEqual(info['type'], 'server-started')
        session_dir = os.path.realpath(info['session_dir'])
        self.assertEqual(
            os.path.dirname(session_dir),
            os.path.join(self.project, '.oc-brainstorm'),
        )
        self.assertTrue(os.path.isfile(os.path.join(session_dir, 'state', 'owner-pid')))

        stop = self.run_stop(info['session_dir'])
        self.assertEqual(json.loads(stop.stdout)['status'], 'stopped', stop.stdout + stop.stderr)
        self.assertTrue(os.path.isdir(session_dir), 'project-dir sessions keep their files')

    def test_restart_stops_prior_session_server(self):
        self.started_info(self.run_start())
        first_pids = self.pids()
        self.assertEqual(len(first_pids), 1)
        self.assertTrue(_alive(first_pids[0]))

        self.started_info(self.run_start())
        self.assertTrue(_wait_dead(first_pids[0]), 'prior session server is still running after a restart')

    def test_start_fails_fast_when_server_process_dies(self):
        fake_bin = os.path.realpath(tempfile.mkdtemp(prefix='ocbs-fakenode-'))
        self.addCleanup(shutil.rmtree, fake_bin, ignore_errors=True)
        fake_node = os.path.join(fake_bin, 'node')
        with open(fake_node, 'w', encoding='utf-8') as f:
            f.write('#!/bin/sh\necho boom >&2\nexit 1\n')
        os.chmod(fake_node, 0o755)
        env = dict(self.env)
        env['PATH'] = fake_bin + os.pathsep + env.get('PATH', '')

        started = time.time()
        result = self.run_start(env=env)
        elapsed = time.time() - started

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('exited before starting', result.stdout)
        self.assertIn('boom', result.stdout)
        self.assertLess(elapsed, 4, 'a dead server must fail fast, not wait out the 5 second window')

    def test_stop_reports_already_exited_for_dead_server(self):
        info = self.started_info(self.run_start())
        pid = self.pids()[0]
        os.kill(pid, signal.SIGKILL)
        self.assertTrue(_wait_dead(pid))
        time.sleep(0.3)

        stop = self.run_stop(info['session_dir'])
        self.assertEqual(json.loads(stop.stdout)['status'], 'already_exited', stop.stdout + stop.stderr)

    def test_stop_refuses_to_signal_unrelated_process(self):
        session_dir = os.path.realpath(tempfile.mkdtemp(prefix='ocbs-stale-'))
        self.addCleanup(shutil.rmtree, session_dir, ignore_errors=True)
        state_dir = os.path.join(session_dir, 'state')
        os.makedirs(state_dir)
        victim = subprocess.Popen(['sleep', '30'])
        self.addCleanup(victim.kill)
        with open(os.path.join(state_dir, 'server.pid'), 'w', encoding='utf-8') as f:
            f.write(str(victim.pid) + '\n')
        with open(os.path.join(state_dir, 'server-instance-id'), 'w', encoding='utf-8') as f:
            f.write('a' * 32 + '\n')

        stop = self.run_stop(session_dir)
        self.assertEqual(json.loads(stop.stdout)['status'], 'stale_pid', stop.stdout + stop.stderr)
        self.assertIsNone(victim.poll(), 'an unrelated process must never be signalled')


class ContextScriptTests(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix='ocbs-ctx-'))
        self.home = os.path.realpath(tempfile.mkdtemp(prefix='ocbs-home-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.env = _clean_env(HOME=self.home)

    def run_context(self, cwd):
        result = subprocess.run(
            ['sh', CONTEXT_SH], cwd=cwd, env=self.env,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def line(self, out, prefix):
        matches = [l for l in out.splitlines() if l.startswith(prefix)]
        self.assertEqual(len(matches), 1, out)
        return matches[0]

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    def test_hot_dirs_are_scoped_to_the_working_directory(self):
        self.write('pkg/a/x.txt', 'x\n')
        self.write('other/y.txt', 'y\n')
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        subprocess.run(['git', 'add', '-A'], cwd=self.root, check=True)
        subprocess.run(
            ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com',
             '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'init'],
            cwd=self.root, check=True,
        )

        out = self.run_context(os.path.join(self.root, 'pkg'))
        hot = self.line(out, 'hot_dirs_30d:')
        self.assertIn('a(1)', hot)
        self.assertNotIn('other', hot)
        self.assertNotIn('pkg', hot)

    def test_npm_deps_parse_a_one_line_package_json(self):
        self.write(
            'package.json',
            '{"name":"t","dependencies":{"left-pad":"1.0.0","chalk":"^5"},'
            '"devDependencies":{"mocha":"1"}}',
        )
        out = self.run_context(self.root)
        deps = self.line(out, 'npm_deps:')
        self.assertEqual(deps.split()[1:], ['left-pad', 'chalk', 'mocha'])


if __name__ == '__main__':
    unittest.main()
