# 7.0 (from 6.3) — speed-first rewrite

- Hard turn budgets: Spike 2, Bounded 2, Architectural 3-4 human turns.
- "Assume, don't ask": >=80%-likely answers become vetoable assumptions in the design.
- Merge rules: questions+design in one message; approaches+design in one message;
  spec write+commit+4 parallel reviewers in one turn; companion offer rides with
  the first question batch (was its own round-trip).
- New fanout-playbook.md: width table, partition axes, worker prompt template with
  bounded (<=150 words) output contract, model tiering (haiku/sonnet), background
  dispatch, merge protocol, 64-call hard cap.
- Progressive disclosure: SKILL.md -25% words; architectural.md loaded only on that
  path; visual-companion.md -58% words; reviewers run in the commit message.
- scripts/ unchanged (already 50ms polling, 100ms watch debounce).
