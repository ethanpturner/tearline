# single-principal-probe

**What this measures.** DEC-007, and the one output the tool must never produce.

**The setup.** The index is correct. Nothing is mistagged, nothing drifts, nothing leaks. `pr-008`
names two principals and runs. `pr-009` names one.

## The forbidden output

*"No leak detected."*

`pr-009` returns some chunks to `p-acme-fin`. Every one of them may legitimately be that principal's
own, so nothing about any boundary has been exercised. A result set that contains no violation is
not evidence that violations are impossible — it is evidence that nothing was compared.

This is the strongest form of false assurance available anywhere in the tool, because it is produced
by a check that appears to have succeeded. A missing probe is visibly missing. A probe that ran and
found nothing looks like a pass, and the report cannot distinguish the two unless it is built to.

So `pr-009` does not run, is named in `probes_skipped`, and the report is marked partial.

## Why an otherwise-clean index

Deliberately. If this scenario also carried a fault, a tool could score well by finding it while
still treating the unrunnable probe as a pass — the same trap `orphaned-chunk` avoids by leaving its
orphan correctly tagged. With nothing else to find, the only thing that distinguishes a correct tool
from an incorrect one is whether it admits what it could not do.

`expected-clean.yaml` also forbids *"coverage is complete"*. Half the probe set could not execute,
and a report that does not surface `probes_skipped` lets a reader mistake an unexercised boundary for
a tested one.

## Pass condition

`pr-008` clean for both principals; `pr-009` absent from the visibility results and present in
`probes_skipped`; the report marked partial; and no statement anywhere that no leak was detected.
