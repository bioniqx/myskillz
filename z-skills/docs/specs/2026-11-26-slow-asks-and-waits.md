# SLOW asks and waits: nothing is assumed, no 15-minute pick, the turn ends at a question

Date: 2026-11-26. Status: approved in SLOW mode (pick A, margin 5); the user replied
"duyệt"; at the spec review gate the user switched the run to FAST
mode. Scope: the seven skills that have a SLOW branch (z-brainstorming, z-dev-team,
z-writing-plans, z-requirements-code-audit, z-systematic-debugging, z-doc-generator,
z-git-diff-summary), _shared/handoff.py, their tests and two changelogs. Work happens
on main. Nothing is committed or installed by this run. FAST, fast.md, the engine caps
(falsifier, claim, mutant), z-idea-to-spec, z-find-skills, the two video skills, the
vendored gamedev bundle and the sibling repos are not touched.

The request, verbatim (its spans are the frozen atoms of this run):

- SLOW mode.
- Chỉnh sửa các skill trong thư mục này
- ở chế độ SLOW mode
- cái gì không rõ ràng là phải hỏi user
- không tự quyết định
- Bỏ luôn vụ quá 15 phút tự chọn
- Luôn chờ user trả lời thì mới làm tiếp
- Chỉ chỉnh sửa chế độ SLOW mode
- bỏ qua các skill liên quan video

## Architecture

Goal: under SLOW the seven skills ask the user instead of deciding. Three decisions the
user made in this run bind the design:

1. Nothing is assumed. A point is settled when a tool result in this session or the
   user's own words decides it; anything else is a question, with no cap of four.
2. The scope is the user gate only: the main thread asks before designing, before a
   hand-off, and when a lane result leaves something open. The engine caps stay as they
   are (falsifier, claim and mutant each try twice, then name the leftover).
3. One test that reads the real repo's mode stamp is fixed in this run.

The SLOW contract is one sentence, defined once (SLOW_ASK, worded below). Three layers
carry it:

1. Clause layer. _shared/handoff.py holds SLOW_ASK and appends it to every SLOW NEXT
   line it prints. Each of the seven SKILL.md files keeps one pointer sentence, extended
   with the same clause.
2. Engine layer. Three gates learn the stamp: ask.py wait has no deadline under SLOW;
   check.py approve refuses an AUTO block under SLOW; check.py send has no four-question
   cap under SLOW.
3. Prose layer. The SLOW-only rules that turn questions into assumptions are rewritten
   in place.

Why the engine layer is needed: an independent breaker found this run that check.py send
fails a draft with more than four question marks and orders the rest into assumptions,
so a text-only change would leave the old rule inside the gate.

## Components

Changes, clause layer:
- _shared/handoff.py gains the constant SLOW_ASK and one helper that appends it. The
  helper wraps every SLOW NEXT string: the fitted-width builder (direct and short,
  brainstorming and dev-team), the full-pace brainstorming line, the five diff-summary
  lines, the writing-plans, dev-team, debugging (two), audit and doc-generator lines.
  FAST branch strings stay byte for byte. sh _shared/sync.sh re-vendors the eight copies.
- Seven SKILL.md files: each keeps its pointer sentence and appends the same sentence
  (worded below).

Changes, engine layer:
- z-brainstorming/scripts/ask.py, wait: it reads the brainstorming stamp (mode.json,
  else the repo stamp, the order the mode subcommand uses). Under a slow stamp there is
  no deadline: the loop returns REPLY or CANCEL only, --timeout is ignored, and no chain
  is written. Under no stamp or a fast stamp today's behavior is unchanged. The module
  docstring drops the sentence "The 15-minute wait is unchanged".
- z-brainstorming/scripts/check.py: approve and send read the same stamp. approve refuses
  an AUTO block under a slow stamp with "RESULT approve no - SLOW does not pick for the
  user; wait for the reply" and exit 1. send runs its four-question check and its "merge
  the rest into assumptions" order only when the stamp is not slow.
- A shared stamp read: _shared/handoff.py gains a public brainstorm_mode() that
  returns "fast", "slow" or "" (mode.json, else the repo stamp). ask.py wait and
  check.py call it. The mode subcommand of ask.py does not change.
- z-brainstorming/scripts/ask.py, chain: it records a SLOW run as mode slow. It used to
  call mode_of with an empty text, which returns fast, so a human approval in a SLOW
  session wrote "mode": "fast". Fixed in this run at the user's request.

Changes, prose layer:
- z-brainstorming/SKILL.md: eight sentences are replaced (worded below) and one
  sentence is deleted (R13). It is 504 lines today and stays at 504 or fewer.
- z-brainstorming/architectural.md: the Split case and the Assumptions item (worded
  below).
- z-brainstorming/fanout-playbook.md lines 106, 124 and 133, research-playbook.md lines
  118 and 133, spec-document-reviewer-prompt.md line 33: the open point is asked, not
  assumed.
- z-dev-team/SKILL.md: Pipeline step 4 gains one sentence (worded below). The engine is
  not changed: the conductor does not call next until the user answers.
- CHANGELOG.md of z-brainstorming and z-writing-plans: one dated entry each.

## Exact wording to review

- SLOW_ASK, appended to every SLOW NEXT line:
  "SLOW asks: anything a tool result in this session or the user's own words has not
  settled is a question for the user, never an assumption, and there is no cap of four.
  Ask, then end the turn and wait for the reply: no timer, no default, no pick."
- Sentence appended to the pointer of all seven SKILL.md files:
  "Under SLOW nothing is assumed: ask, then end the turn and wait for the reply."
- z-dev-team/SKILL.md, end of Pipeline step 4:
  "Under SLOW this step is a stop: ask every blocking question and every assumption the
  plan lists in one message, start no lane before the reply, and stop the run the same
  way when a lane reports a blocking question."
- z-brainstorming/SKILL.md, sentence by sentence:
  - Hard rule 1, third line: "stdin is the human reply, or the AUTO block of the FAST
    pick inside `open`."
  - Hard rule 6: "Under SLOW ask every unsettled point: there is no cap and nothing is
    an assumption (R6)."
  - R6 title: "R6 - Ask, then wait (SLOW)". Body below. The wait command keeps its
    --ledger and --options arguments and loses --timeout 900.
  - R8: "Unasked questions are asked, not assumed (R6)."
  - R11 merge rule: "Every UNKNOWN or UNVERIFIED becomes a question for the user (R6),
    never a new exploration round unless the design cannot be drafted without it."
  - Red flag "I'll ask to be safe" becomes: "I'll assume to be safe" - under SLOW the
    assumption is the cost; ask (R6).
  - Conductor step 4: "`ask` asks that one fork and ends the turn (R6)."
  - Before you send, item 3: "A design message contains `Approve this design?`, an
    Assumptions section (none under SLOW), and Out of scope."
  - R13: the sentence "An automatic pick already wrote" and the path after it are deleted.
- R6 body:
  "Nothing is assumed. A point is settled when a tool result in this session or the
  user's own words decides it; anything else is a question, with no cap of four. More
  than four questions: one numbered plain-text message. Whether a reply is approval is
  decided by `check.py approve`, not by how agreeable it sounds. With AskUserQuestion
  make item 1 Approve this design (Approve / Approve with my answers below / Revise) so
  one reply both answers and approves; otherwise ask in plain text. Name the
  recommended option id in that message. In the same message start the wait command
  with run_in_background: true, then end the turn. A chat reply before it finishes:
  first call `ask.py cancel`, then `approve` on that reply. The wait never picks: it
  returns REPLY or CANCEL only. `DECISION stop` or `ask=unattacked` is not a pick."
- architectural.md, Split paragraph: "Send the questions right away and end the turn;
  under SLOW no lane runs while the user thinks." Item 7: "Assumptions - none under
  SLOW; every open point is a question in the message."

## Verified locations (this session)

Read or run this session; F-numbers are this session's ledger facts.
- `_shared/handoff.py:810` "def _slow_fit_next(width, scripts, self_name):" - fitted-width SLOW NEXT builder (F-20).
- `_shared/handoff.py:838` "NEXT: PACE: slow. fast.md stays unread. Round 1: one message," - full-pace brainstorming SLOW NEXT (F-99).
- `_shared/handoff.py:1125` "NEXT: PACE: slow. One engine call using that D= path." - dev-team SLOW NEXT (F-100).
- `_shared/sync.sh:19` "z-brainstorming z-dev-team z-doc-generator z-git-diff-summary z-idea-to-spec" - handoff vendor list (F-117).
- `z-brainstorming/scripts/ask.py:20` "DEFAULT_TIMEOUT = 900" - the wait deadline (F-2).
- `z-brainstorming/scripts/ask.py:171` "if now < deadline:" - the wait stops at the deadline (F-4).
- `z-brainstorming/scripts/check.py:560` "if questions > 4:" - send caps a draft at four questions (F-120).
- `z-brainstorming/scripts/check.py:561` "FAIL questions - {questions} question marks (max 4); merge" - and orders the rest into assumptions (F-119).
- `z-brainstorming/scripts/check.py:622` "(?m)^auto$" - approve accepts an AUTO block (F-5).
- `z-brainstorming/SKILL.md:51` "do not take the FAST branch" - the SLOW pointer (F-6).
- `z-brainstorming/SKILL.md:75` "Ask at most 4 forking questions" - hard rule 6 (F-7).
- `z-brainstorming/SKILL.md:207` "Assume, do not ask" - the R6 title (F-8).
- `z-brainstorming/SKILL.md:220` "--timeout 900" - R6 arms the timed wait (F-10).
- `z-brainstorming/SKILL.md:223` "is the reply when 15 minutes pass with none" - the AUTO reply (F-11).
- `z-brainstorming/SKILL.md:241` "Unasked questions become assumptions" - R8 (F-12).
- `z-brainstorming/SKILL.md:352` "becomes an assumption or one of the" - the R11 merge rule (F-13).
- `z-brainstorming/SKILL.md:377` "An automatic pick already wrote" - R13 (F-14).
- `z-brainstorming/SKILL.md:447` "a vetoable assumption costs zero turns" - the red flag (F-15).
- `z-brainstorming/SKILL.md:501` "an assumption, and Out of scope" - Before you send (F-16).
- `z-brainstorming/architectural.md:24` "Send questions + assumptions right away while lanes" - lanes keep running (F-17).
- `z-brainstorming/architectural.md:79` "likely answer you did not ask about" - the Assumptions rule (F-18).
- `z-brainstorming/fanout-playbook.md:124` "3. UNKNOWN or UNVERIFIED" - UNKNOWN becomes an assumption (F-107).
- `z-brainstorming/research-playbook.md:118` "make it an assumption or ask the" - the privacy fallback (F-109).
- `z-brainstorming/spec-document-reviewer-prompt.md:33` "unverified items are labeled as assumptions." - review lens 5 (F-111).
- `z-dev-team/SKILL.md:156` "while the lanes already run" - questions sent while lanes run (F-24).
- `z-dev-team/SKILL.md:158` "anything else is an assumption" - everything else is an assumption (F-25).
- `z-dev-team/agents/z-programmer-lite.md:161` "the exact blocking question" - a lane reports a blocking question (F-27).
- `z-dev-team/agents/z-team-leader.md:105` "what breaks if wrong" - the plan's High-risk assumption list (F-115).
- `z-writing-plans/SKILL.md:209` "never takes this inline path" - its SLOW pointer (F-28).
- `z-systematic-debugging/SKILL.md:59` "the slow branch replaces this lane routing" - its SLOW pointer (F-29).
- `z-requirements-code-audit/SKILL.md:40` "the short path is off and the four calls stay" - its SLOW pointer (F-30).
- `z-doc-generator/SKILL.md:41` "When the prelude prints" - its SLOW pointer (F-31).
- `z-git-diff-summary/SKILL.md:24` "When the prelude prints" - its SLOW pointer (F-32).
- `_shared/tests/test_brainstorm_ask.py:144` "self.assertEqual(json.load(open(dest))" - the assertion that read the real stamp (F-35).
- `_shared/tests/test_handoff.py:459` "class SlowModeTests(unittest.TestCase):" - one SLOW-branch test per skill (F-37).
- `_shared/tests/test_debug_slow.py:133` "NEXT: add ONE falsify command for h1" - the falsifier cap, out of scope (F-83).

## Data flow

handoff.py open classifies the mode and writes the stamp, as today. Under SLOW every
NEXT line it prints ends with SLOW_ASK. The main thread asks the user in one message and
ends the turn; no lane and no engine step runs before the reply. On z-brainstorming at
full pace the background ask.py wait only waits: a chat reply makes the model call
ask.py cancel and pass the reply to check.py approve, which refuses an AUTO block under
SLOW. On "approve yes" the model runs ask.py chain and writes the spec. The six other
skills ask through their SKILL.md pointer; their scripts are unchanged.

## Error handling

- No reply: the session stays idle. The brainstorming wait keeps running until a reply
  file or a cancel file appears; nothing is picked.
- An AUTO block under SLOW: approve prints "approve no" with the reason and exits 1.
- A stale FAST chain.json in the repo is ignored while the stamp is slow: the plan tool
  checks the stamp first. `z-writing-plans/scripts/plan_tool.py:1852` "mode stamp is slow: the inline path is not taken" (F-49).
  So does the engine. `z-dev-team/scripts/devteam.py:1641` "slow = mode_stamp(root)" (F-66).
- A vendored copy that drifts from _shared/handoff.py: test_vendored.py fails; sh
  _shared/sync.sh restores it.
- An unreadable ledger or options file: wait no longer loads them under SLOW (they were
  only needed to pick); approve and send report their own errors as today.

## Testing

Everything below is a command this repo can run.

Tests that move with the requirement (each edited assertion and its reason):
- _shared/tests/test_brainstorm_ask.py, ModeTests.test_cmd_mode_never_asks: its
  assertion read the real repo's stamp and failed in every SLOW session (baseline this
  session: 847 tests, 1 failure). It now patches read_mode_stamp, the stamp reader the
  mode subcommand falls back to, so it reads no stamp. Approved by the user in this run.
- _shared/tests/test_brainstorm_ask.py, ApproveAutoTests.test_the_auto_block_approves:
  it states an empty stamp once approve reads one. No assertion is weakened; the FAST
  behavior it pins is unchanged.
- No other existing assertion changes. WaitTests (the FAST timeout pick) and
  FastPickTests keep today's behavior.

New tests, written first. They patch brainstorm_mode in the module under test and never
read the real repo's stamp. The patch seam is the one the suite already uses: `_shared/tests/test_decide.py:147` "mock.patch.object(decide.urllib.request," (F-123).
- test_handoff.py, SlowModeTests.assert_slow: the binding NEXT of every SLOW branch
  contains SLOW_ASK; no FAST branch string does.
- test_brainstorm_ask.py: under a slow stamp wait has no deadline and writes no chain;
  under no stamp the 900-second deadline and the AUTO pick are unchanged.
- test_brainstorm_ask.py or test_z_brainstorm_check.py: under a slow stamp approve
  refuses an AUTO block and send accepts six question marks; under no stamp both keep
  today's result.
- One test of brainstorm_mode itself in a temporary git repo: mode.json wins, else the
  repo stamp, else an empty string.
- test_brainstorm_ask.py: ask.py chain writes mode slow when mode.json or the repo
  stamp says slow.

Acceptance:
- The new tests above are written first and fail for the right reason before the change.
- Full suite green. Baseline this session: 847 tests, 1 failure (the stamp leak fixed
  here). After the change: 0 failures in a SLOW session and in a session with no stamp.
- bash z-dev-team/scripts/selftest.sh green.
- sh _shared/sync.sh leaves no diff and test_vendored.py is green.
- Hygiene suite green (test_all_skills.py): every description at or under 1024
  characters.
- z-brainstorming/SKILL.md is 504 lines or fewer.
- Grep proof: no FAST branch string in _shared/handoff.py contains SLOW_ASK; every SLOW
  branch string does.
- Not run by this design: real prompts in a fresh ZCode session. That needs the
  installer and a new session, and is not run (assumption above).

## Evidence

- An agent pauses for human feedback at checkpoints or when it hits a blocker - B - https://www.anthropic.com/engineering/building-effective-agents - 2024-12-19 - "Agents can then pause for human feedback at checkpoints or when encountering blockers." Labelled unverified: WEAK on age (23 months); a guidance statement, not a versioned fact. It backs the decision to stop and ask, not any line of the implementation.
- Agent work is tested in a sandbox with guardrails before it is relied on - B - https://www.anthropic.com/engineering/building-effective-agents - 2024-12-19 - "We recommend extensive testing in sandboxed environments, along with the appropriate guardrails." Same label: unverified, WEAK on age. It backs the acceptance item about real prompts in a fresh session.

## Assumptions

The run moved to FAST mode before these four points were answered, so each takes the
recommended reading. The user can veto any of them.
- The brainstorming background wait under SLOW is kept with no deadline, as this spec
  describes. Deleting wait and cancel was the alternative.
- After the tests pass the run stops at the test suite. Nothing is installed; real
  prompts in a fresh session remain the user's call.
- ask.py chain writing the wrong mode in a SLOW session: the run first reported it,
  then fixed it after the review gate at the user's request.
- The spec got the inline self-review only. No four-lane spec review and no second
  independent breaker ran on the final design: lanes were unavailable.

Additional findings, reported and not fixed (outside the approved design):
1. ask.py chain writes the wrong mode in a SLOW session. Run this session: after the
   user's approval, "ask.py chain --pick A" wrote "mode": "fast" to chain.json while the
   mode stamp was slow. The cause is that mode_of returns "fast" for an empty text and
   chain passes an empty text. The 2026-11-17 SLOW spec and the SLOW NEXT line in
   handoff.py both say the chain is "mode slow". While the stamp is slow both readers
   check the stamp first, so no FAST path is taken. Fixed in this run, see Components.
2. z-brainstorming/SKILL.md is 504 lines before any change, over the 500-line target in
   docs/skill-criteria.md. This spec keeps it at 504 or fewer.

## Out of scope

- FAST: fast.md, every FAST branch string in _shared/handoff.py, ask.py fast,
  force_pick, and the FAST timeout pick of ask.py wait.
- The engine caps: falsifier, claim and mutant (try twice, then name the leftover).
- z-idea-to-spec and z-find-skills (no SLOW branch), z-video-shotcraft and
  z-viral-video-studio, awesome-gamedev-agent-skills-1.1.0, the sibling repos, .audit.
- Installing into the ZCode or dsh home; committing.
