"""Black-box tests for brainstorming-glm/scripts/server.cjs, helper.js and
frame-template.html. Each test spawns the real server.cjs as a subprocess
against a throwaway session directory in the system temp dir (never inside
the repo/worktree) and talks to it over real HTTP/WebSocket sockets.
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
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.parse

TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
SKILLS_DIR = os.path.dirname(os.path.dirname(TESTS_DIR))
SCRIPTS_DIR = os.path.join(SKILLS_DIR, 'brainstorming-glm', 'scripts')
SERVER_JS = os.path.join(SCRIPTS_DIR, 'server.cjs')
HELPER_JS = os.path.join(SCRIPTS_DIR, 'helper.js')

STARTUP_TIMEOUT = 10


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
    """The server only returns real screen content once a cookie was minted:
    GET /?key=<token> returns a small bootstrap stub (sets the cookie, then
    JS-redirects to /). A plain single-shot GET never sees the actual page.
    """
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


class BrainstormServerTestCase(unittest.TestCase):
    def start_server(self, env_extra=None):
        session_dir = os.path.realpath(tempfile.mkdtemp(prefix='bstest-session-'))
        content_dir = os.path.join(session_dir, 'content')
        state_dir = os.path.join(session_dir, 'state')
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

        env = dict(os.environ)
        for var in ('BRAINSTORM_PORT', 'BRAINSTORM_PORT_FILE', 'BRAINSTORM_TOKEN_FILE',
                    'BRAINSTORM_TOKEN', 'BRAINSTORM_OWNER_PID'):
            env.pop(var, None)
        env['BRAINSTORM_DIR'] = session_dir
        env['BRAINSTORM_HOST'] = '127.0.0.1'
        env['BRAINSTORM_URL_HOST'] = 'localhost'
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

    # ---- W9-2: literal content injection (no $&/$$/$'/$` interpretation) ----

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
        # Edge case: the screen itself is a complete HTML document, so the
        # bypass path (no frame wrap) plus the helper-script injection before
        # </body> must also avoid $-pattern interpretation.
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
        # helper script must still have been injected before </body>
        self.assertIn('<script>', text)

    # ---- W9-3: crash/signal safety ----

    def test_request_handler_crash_returns_500_and_server_keeps_serving(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        # Removing the content dir makes fs.readdirSync throw inside the '/'
        # handler (getNewestScreen). The handler must catch it, not crash.
        shutil.rmtree(content_dir)

        status, body = _fetch_real_content(info['port'], token)
        self.assertEqual(status, 500, body[:500])
        self.assertIsNone(proc.poll(), 'server process must still be alive after handler error')

        # server must keep serving further requests
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
            req = _ws_handshake_request('127.0.0.1', port, token)
            sock.sendall(req)
            resp = _recv_until(sock, b'\r\n\r\n', 3)
            self.assertIn(b'101', resp)
            frame = _build_ws_frame(0x01, json.dumps({'type': 'click', 'choice': 'x'}).encode())
            sock.sendall(frame)
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

    # ---- W9-4 / C1: session_dir ----

    def test_session_dir_in_started_json_and_server_info(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        self.assertIn('session_dir', info)
        self.assertEqual(os.path.realpath(info['session_dir']), session_dir)
        self.assertEqual(os.path.dirname(state_dir), session_dir)

        info_file = os.path.join(state_dir, 'server-info')
        with open(info_file, encoding='utf-8') as f:
            written = json.loads(f.read().strip())
        self.assertEqual(os.path.realpath(written['session_dir']), session_dir)

    # ---- W9-7: /files/ url-decoding, traversal, bad percent-encoding ----

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

        # Edge case: invalid percent-encoding must not crash the server.
        status2, _, _ = _http_get(port, '/files/%zz?key=' + token)
        self.assertEqual(status2, 404)
        self.assertIsNone(proc.poll(), 'invalid percent-encoding must not crash the server')

        status3, _, _ = _http_get(port, '/does-not-exist?key=' + token)
        self.assertEqual(status3, 404)

    # ---- W9-8: watcher ignores symlinks / non-regular files ----

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

    # ---- W9-9: bytes in the upgrade `head` are not dropped ----

    def test_websocket_frame_in_same_packet_as_handshake(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])
        port = info['port']

        frame = _build_ws_frame(0x01, json.dumps({'type': 'click', 'choice': 'combo'}).encode())
        req = _ws_handshake_request('127.0.0.1', port, token)

        sock = socket.create_connection(('127.0.0.1', port), timeout=5)
        try:
            # Handshake request and the first WS frame sent as ONE packet/send().
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

    # ---- W9 perf (d): events -> events.prev instead of being deleted ----

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

    # ---- W9-11: no external assets; plain "Brainstorming" brand label ----

    def test_no_external_host_and_plain_brand_label(self):
        proc, info, q, session_dir, content_dir, state_dir = self.start_server()
        token = _token_from_url(info['url'])

        status, body = _fetch_real_content(info['port'], token)
        text = body.decode('utf-8')
        self.assertEqual(status, 200)
        self.assertNotIn('primeradiant.com', text)
        self.assertNotIn('src="http', text)
        self.assertNotIn('github.com', text)
        self.assertNotIn('vunknown', text)
        self.assertIn('<div class="brand"><span class="brand-copy">Brainstorming</span></div>', text)

    # ---- W9-13: helper.js click event text/selected ----

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

            // Non-multiselect: text is whitespace-normalised and capped at 120 chars,
            // and no `selected` key is added.
            const longText = '  Hello   World  ' + 'x'.repeat(200);
            const single = makeEl(longText, 'a', []);
            const singleContainer = { dataset: {}, querySelectorAll: () => [] };
            single.closest = (sel) => (sel === '[data-choice]' ? single : (sel === '.options' || sel === '.cards' ? singleContainer : null));
            dispatchClick(single);

            // Multiselect + selected: `selected` boolean reflects the element's class.
            const multi = makeEl('Pick me', 'b', ['selected']);
            const multiContainer = { dataset: { multiselect: '' }, querySelectorAll: () => [] };
            multi.closest = (sel) => (sel === '[data-choice]' ? multi : (sel === '.options' || sel === '.cards' ? multiContainer : null));
            dispatchClick(multi);

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

        self.assertEqual(len(events), 2)
        single_evt, multi_evt = events

        normalized_full = 'Hello World ' + 'x' * 200  # whitespace collapsed, trimmed, before slicing
        self.assertEqual(single_evt['text'], normalized_full[:120])
        self.assertLessEqual(len(single_evt['text']), 120)
        self.assertNotIn('selected', single_evt)

        self.assertEqual(multi_evt['text'], 'Pick me')
        self.assertIn('selected', multi_evt)
        self.assertTrue(multi_evt['selected'])

    def test_node_check_syntax_server_and_helper(self):
        for script in (SERVER_JS, HELPER_JS):
            with self.subTest(script=script):
                result = subprocess.run(['node', '--check', script], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)


class GlmScriptsTestCase(unittest.TestCase):
    """start-server.sh, stop-server.sh, context.sh and the docs run against real temp dirs."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='glm-bs-scripts-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = os.path.join(self.tmp, 'project')
        self.home = os.path.join(self.tmp, 'home')
        os.makedirs(self.project)
        os.makedirs(self.home)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('BRAINSTORM_')}
        self.env['HOME'] = self.home
        self.env['GIT_CONFIG_GLOBAL'] = os.devnull
        self.env['GIT_CONFIG_NOSYSTEM'] = '1'

    def run_script(self, name, *args, extra_env=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ['bash', os.path.join(SCRIPTS_DIR, name)] + list(args),
            cwd=self.project, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30,
        )

    def start(self, extra_env=None):
        result = self.run_script('start-server.sh', '--project-dir', self.project, extra_env=extra_env)
        lines = result.stdout.strip().splitlines()
        info = json.loads(lines[0]) if lines else {}
        if info.get('type') == 'server-started':
            self.addCleanup(self.run_script, 'stop-server.sh', os.path.dirname(info['state_dir']))
        return result, info

    def pid_of(self, state_dir):
        with open(os.path.join(state_dir, 'server.pid'), encoding='utf-8') as f:
            return int(f.read().strip())

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def wait_dead(self, pid, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline and self.alive(pid):
            time.sleep(0.05)
        return not self.alive(pid)

    def test_start_reports_session_dir_and_stop_stops_the_server(self):
        result, info = self.start()
        self.assertEqual(info.get('type'), 'server-started', result.stdout + result.stderr)
        self.assertIn('session_dir', info)
        state_dir = info['state_dir']
        self.assertEqual(os.path.realpath(info['session_dir']), os.path.realpath(os.path.dirname(state_dir)))
        pid = self.pid_of(state_dir)
        self.assertTrue(self.alive(pid))
        stopped = self.run_script('stop-server.sh', info['session_dir'])
        self.assertEqual(json.loads(stopped.stdout.strip())['status'], 'stopped', stopped.stdout)
        self.assertTrue(self.wait_dead(pid))
        self.assertTrue(os.path.exists(os.path.join(state_dir, 'server-stopped')))

    def test_second_start_stops_the_previous_server_of_the_same_project(self):
        _, first = self.start()
        self.assertEqual(first.get('type'), 'server-started')
        first_pid = self.pid_of(first['state_dir'])
        result, second = self.start()
        self.assertEqual(second.get('type'), 'server-started', result.stdout + result.stderr)
        self.assertNotEqual(first['state_dir'], second['state_dir'])
        self.assertTrue(self.wait_dead(first_pid), 'the previous server must be stopped by the new start')
        self.assertTrue(self.alive(self.pid_of(second['state_dir'])))

    def test_start_fails_fast_when_the_server_dies_on_startup(self):
        started = time.time()
        result, _ = self.start(extra_env={'BRAINSTORM_PORT': 'not-a-port'})
        self.assertIn('exited before starting', result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertLess(time.time() - started, 4.0)

    def git(self, repo, *args):
        subprocess.run(
            ['git', '-c', 'user.name=tester', '-c', 'user.email=tester@example.com'] + list(args),
            cwd=repo, env=self.env, check=True, capture_output=True, text=True, timeout=30,
        )

    def make_repo(self):
        repo = os.path.join(self.tmp, 'repo')
        os.makedirs(os.path.join(repo, 'a'))
        os.makedirs(os.path.join(repo, 'sub', 'x'))
        for rel in (os.path.join('a', 'f.txt'), os.path.join('sub', 'x', 'y.txt')):
            with open(os.path.join(repo, rel), 'w', encoding='utf-8') as f:
                f.write('content\n')
        self.git(repo, 'init', '-q')
        self.git(repo, 'add', 'a', 'sub')
        self.git(repo, 'commit', '-q', '-m', 'seed')
        return repo

    def context_lines(self, cwd):
        result = subprocess.run(
            ['sh', os.path.join(SCRIPTS_DIR, 'context.sh')],
            cwd=cwd, env=self.env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def test_context_hot_dirs_are_scoped_to_the_working_directory(self):
        repo = self.make_repo()
        lines = self.context_lines(os.path.join(repo, 'sub'))
        hot = [line.strip() for line in lines if line.startswith('hot_dirs_30d:')]
        self.assertEqual(hot, ['hot_dirs_30d: x(1)'], lines)

    def test_context_npm_deps_lists_only_dependency_names(self):
        repo = self.make_repo()
        with open(os.path.join(repo, 'package.json'), 'w', encoding='utf-8') as f:
            f.write('{"name":"x","version":"1.0.0","dependencies":{"left-pad":"1.3.0"}}')
        lines = self.context_lines(repo)
        deps = [line.strip() for line in lines if line.startswith('npm_deps:')]
        self.assertEqual(deps, ['npm_deps: left-pad'], lines)

    def test_frame_template_has_no_logo_rules(self):
        with open(os.path.join(SCRIPTS_DIR, 'frame-template.html'), encoding='utf-8') as f:
            template = f.read()
        self.assertNotIn('brand-logo', template)

    def test_visual_companion_describes_the_current_loop(self):
        with open(os.path.join(os.path.dirname(SCRIPTS_DIR), 'visual-companion.md'), encoding='utf-8') as f:
            doc = f.read()
        for needle in ('"session_dir"', 'Save `session_dir`', 'kill -0 <pid>', 'events.prev'):
            self.assertIn(needle, doc)
        self.assertNotIn('primeradiant', doc)


if __name__ == '__main__':
    unittest.main()
