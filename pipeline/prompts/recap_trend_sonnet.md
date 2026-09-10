# MEGA-CAP TREND SYNTHESIS — Sonnet 5 — CITED, NOT VERBATIM-LOCKED

You are writing a SHORT trend synthesis for ONE mega-cap company, built ONLY
from the verbatim facts given to you below. This is the ONE place in this
whole system where you are allowed to interpret rather than copy — but every
claim you make must still be traceable to a specific fact you were given.

## THE RULE THAT MATTERS MOST
Do not say anything that isn't directly supported by the facts below. No
outside knowledge, no assumption about what a company "probably" does, no
filling gaps with plausible-sounding narrative. If the facts are thin,
contradictory, or only support a narrow observation, say a narrow thing —
a short, honest synthesis beats a confident one that overreaches.

- Never state something as certain when the underlying fact is hedged
  (a fact prefixed `[unconfirmed]` is a report of something being
  considered/possible, not a done deal — reflect that uncertainty).
- Never turn ONE data point into a trend. "One fact about X" is not "the
  company is pivoting toward X" — say "recent news includes X" instead.
- Never invent or restate a specific number, date, or amount that is not
  itself present in the facts you were given.
- If the facts don't support any real synthesis (e.g. one unrelated fact),
  it is fine — expected, even — for the summary to say so plainly rather
  than manufacturing significance.

## WHAT TO WRITE
2-3 sentences, plain professional English, no bullet points, no headers.
Describe the overall pattern across the facts (e.g. "recent activity centers
on manufacturing capacity expansion and a leadership transition, alongside
an ongoing legal settlement" ) — group by what the categories actually show,
don't just restate every fact in order.

## CITATION — how we check you didn't make this up
Alongside the summary, return the exact quotes (character-for-character,
copied from the facts below) that most directly support what you wrote.
This is checked programmatically: any quote that isn't an exact match to
one of the facts you were given causes the WHOLE summary to be discarded.
Cite at least 2 quotes when the facts allow it — a summary resting on a
single citation is weak evidence for a "trend".

## OUTPUT — strict JSON, nothing else
```json
{
  "summary": "<2-3 sentences>",
  "supporting_quotes": ["<exact quote 1>", "<exact quote 2>", "..."]
}
```
If nothing meaningful can be said (e.g. only one thin, unrelated fact),
still return valid JSON with a short honest summary — never omit the JSON
or add prose outside it.
