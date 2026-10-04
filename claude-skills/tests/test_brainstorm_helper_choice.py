"""Black-box test for claude-brainstorming-6.3/scripts/helper.js `brainstorm.choice()` (T02).

server.cjs appends an event to `state/events` only when it carries a `choice` key, so
`window.brainstorm.choice(value)` must send `choice: value` along with `type` and `value`.
helper.js runs under node with a minimal fake browser (window, document, WebSocket); the
queued event is flushed through the fake socket's `onopen` and read back as JSON.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
HELPER = os.path.join(BASE_DIR, "claude-brainstorming-6.3", "scripts", "helper.js")

HARNESS = r"""
const sent = [];
let socket = null;
global.window = { location: { host: 'localhost:1', reload() {} }, sessionStorage: null };
global.document = { addEventListener() {}, querySelector() { return null; }, body: null };
global.WebSocket = class {
  constructor() { socket = this; this.readyState = 0; }
  send(text) { sent.push(JSON.parse(text)); }
  close() {}
};
global.WebSocket.OPEN = 1;
require(process.argv[2]);
if (process.argv[4] === 'meta') window.brainstorm.choice(process.argv[3], { note: 'n1' });
else window.brainstorm.choice(process.argv[3]);
socket.readyState = 1;
socket.onopen();
console.log(JSON.stringify(sent));
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class HelperChoiceTests(unittest.TestCase):
    def run_helper(self, value, mode):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        script = os.path.join(os.path.realpath(tmp), "harness.js")
        with open(script, "w") as f:
            f.write(HARNESS)
        p = subprocess.run(["node", script, HELPER, value, mode], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def test_choice_event_carries_the_choice_key_the_server_records(self):
        events = self.run_helper("b", "meta")
        self.assertEqual(len(events), 1, events)
        event = events[0]
        self.assertEqual(event.get("choice"), "b")
        self.assertEqual(event["type"], "choice")
        self.assertEqual(event["value"], "b")
        self.assertEqual(event["note"], "n1")

    def test_choice_without_metadata_still_sends_choice(self):
        events = self.run_helper("c", "plain")
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0].get("choice"), "c")
        self.assertEqual(events[0]["type"], "choice")
        self.assertEqual(events[0]["value"], "c")
        self.assertNotIn("note", events[0])


if __name__ == "__main__":
    unittest.main()
