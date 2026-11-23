# RSIAgent → EvoVS-RSI: controlled port, not a framework swap

> **Status (2026-11-23):** Architecture decision + an additive *control-plane prototype* in
> `scientific/src/evovs_science/rsi/protocol.py`. **Not** an end-to-end
> RSIAgent-enabled screening agent; no remote test or benchmark has run as part of
> this change. The protected evaluator, experimental arms, search-space code,
> Model/AutoML environments, and DSH engine are unchanged.
>
> Upstream inspiration: [AetherLabsAI/RSIAgent](https://github.com/AetherLabsAI/RSIAgent),
> [architecture](https://github.com/AetherLabsAI/RSIAgent/blob/main/docs/ARCHITECTURE.md).
> Implementations are original; no code from upstream is vendored.

## 1. Evidence-first diagnosis

The repository's [Phase 7 conclusions](../CONCLUSIONS.md) and
[Phase 8 handoff](../HANDOFF_P8.md) are the current starting points; the
[README](../README.md) retains older, provisional Phase 7 status.

* P7: R and M exposed the same tools and no runtime self-modification was
  triggered. Therefore P7 did **not** test Harness RSI, regardless of the names.
* P7: Validation AUROC distinguished models poorly relative to locked-AUROC
  variability; the small test cohorts and class imbalance undermine
  performance-sensitive candidate selection.
* P7: The fixed W pipeline was a weak baseline. Claims about memory or RSI
  beating a strong AutoML pipeline were not demonstrated.
* P8: `harness.propose` has **already been implemented**, frozen-search-space
  budgets are enforced, and an AutoGluon W baseline was smoke-tested.
  **Do not reimplement these as though absent.**
* P8 remains incomplete on the interaction-feature axis and budget-accounting
  comparability. No change in this PR affects either item.

RSIAgent's paper reports improvements in digital software environments. It does
**not** directly establish effectiveness for GPCR screening, DTA, or QSAR. Its
transferable contribution is an exploration/verification/memory *protocol*.

## 2. Architecture decision

Keep `deepseek-ai/dsh-superagent-prototype` as the Actor execution substrate.
No swap to RSIAgent's Python runtime, no changes to `src/core/engine.ts`,
`src/app/store.ts`, `src/research/registry.ts`, or the protected evaluator.

```text
                Trusted orchestration (host, not an Actor tool)
        Curriculum ──proposes practice / target curriculum──┐
                     │                                     │
                     ▼                                     ▼
        BRS: breadth-first practice                  DRS: target retry
        independent ticket workspaces                 focused experiments
                     │                                     │
                     ▼                                     ▼
              DSH Actor + current scientific tools (unchanged)
                     │
                artifact + manifest hash
                     │
                     ▼
           Independent Verifier (separate identity/context)
           [dataset / split / metrics / budget / artifacts]
                     │
            PASS / FAIL / UNRESOLVED / INFRA_ERROR
                     │
           verified evidence + Actor-owned lessons
                     │
                     ▼
     memory reconciliation; all-or-nothing BRS wave barrier
                     │
           frozen memory + pinned run fingerprints
                     │
                     ▼
       Sealed test-time execution / protected evaluation

       R only: Actor → harness.propose → shadow + gate
               → operator authorization → versioned promotion
                  (separate from memory learning)
```

**Role separation is operational, not merely prompt wording.** The Verifier
must run with a separate model session/principal and must not receive the
Actor's private chain-of-thought, durable memory, self-evaluation prose,
or inaccessible reference labels. The host provides only the candidate,
task-visible inputs, reproducible artifacts, and a verification rubric.
The official locked evaluator is a *different* protected process.

## 3. Learning phases (RSIAgent semantics)

### BRS — Broad Recursive Self-exploration

The Curriculum proposes a diverse wave of projects: assay label audits,
scaffold split/reproducibility exercises, feature-model coverage, incomplete
classes, feature dimension errors, ranking consistency, and no-hit-rate
assertions for unlabeled 100k screens.

* Every branch starts from the same canonical **pre-wave memory**.
* Each DSH Actor works in a separate ticket workspace and produces artifacts.
* Each Verifier returns a distinct receipt: PASS, FAIL, UNRESOLVED, or
  INFRA_ERROR, with evidence fingerprints.
* **No memory is published mid-wave**. All branches must resolve to PASS/FAIL
  before lessons are committed, serially in Curriculum order.
* A FAIL with grounded evidence may teach a failure lesson; a transport error
  or unresolved verdict may **not** become a success or learning claim.
* If any branch remains unresolved, the wave is blocked or quarantined.
  Do not silently merge the successful siblings.

### DRS — Deep Recursive Self-exploration

Start with an actual development-target attempt, not arbitrarily generated
practice. After verification, diagnose weak coverage and choose focused
practice, e.g. target-specific negative-transfer cases, unstable validation
under minority class resampling, or inconsistent Morgan/descriptor settings.

A successful practice lesson is **not** sufficient to declare the original
target solved. Reattempt the unchanged target and verify again. Do not
transform readiness advice from Curriculum into PASS. A lack of budget is
STALLED/BUDGET_EXHAUSTED, not convergence.

### Test-time execution

Freeze memory, the search-space fingerprint, data/split snapshots, and the
promoted Harness SHA. Disable Curriculum, memory updates, and further Harness
promotion. The independent `evaluation.locked` remains the only scorer.
Never pass the locked metrics or per-molecule errors back into any subsequent
learning loop in the same protocol lineage.

## 4. What the new code does and does not do

`scientific/src/evovs_science/rsi/protocol.py` is a pure-Python state machine
exposing:

| API | Invariant |
| --- | --- |
| `create_run` | Pin A/M/R arm and three immutable experiment fingerprints |
| `begin_wave` | Every BRS project has one pre-wave memory SHA |
| `submit_wave_result` | Require separate Actor/Verifier IDs and matching artifact digests |
| `commit_wave` | Reject partial, infrastructure, or unresolved waves; ordered memory commit |
| `begin_deep_target` | DRS begins with a real target attempt |
| `submit_target_attempt` | Distinguish verified PASS/FAIL from unscored outcomes |
| `submit_focused_practice` | Learn verified local lessons without declaring target victory |
| `register_harness_promotion` | R-only ledger for already gated and operator-approved changes |
| `freeze_for_test` / `attest_frozen` | Freeze memory and pin Harness/search-space identities |

The prototype stores memory lessons **inside the returned state object**; it
does not mutate the current `experience.store`. Fingerprints are canonical
SHA-256, and state methods return copies rather than mutating input objects.

**Important trust limitation:** `verification` is a *receipt schema*, not
a cryptographic attestation. A dishonest Actor could fabricate its own JSON
if the host lets it call these functions directly. The production host must
construct receipts itself after an independently executed Verifier, enforce
filesystem separation, and authenticate the outcome.

**Still missing:** the Curriculum LLM runner, DSH Ticket adapter, independent
Verifier execution/permissions, durable atomically committed memory,
claim-level reconciliation/contradiction handling, exploration recovery,
and official experiment orchestration. Do not report the prototype as an
operational end-to-end RSI agent.

## 5. Distinguishing the four experiment arms

| Arm | Workflow | Experience during learning | Harness self-modification |
| --- | --- | --- | --- |
| W | Strong AutoGluon baseline, no LLM | None | None |
| A | DSH Actor, Curriculum-controlled search | No cross-task memory | None |
| M | DSH Actor + Curriculum + Verifier | Verified memory accumulation and reuse | None |
| R | Same as M | Verified memory accumulation and correction | `harness.propose` + existing shadow/gate + operator-approved promotion |

The protocol implements A's no-memory rule; M/R both learn from verified
practice. **R only becomes causally different from M after a qualified,
actually deployed Harness change.** Simply granting `harness.propose`
access or renaming an arm is insufficient. Record the candidate ID, gate
receipt SHA, operator decision, before/after source SHA, and deployment point.
If no candidate is promoted, report that R and M share the same effective
Harness during the comparison.

Distinguish (1) *task-level search improvement* (different featurization/model
on a target), (2) *memory learning* (documented strategy reused in a later
target), and (3) *Harness RSI* (versioned code/policy/tool change). Only (3)
is Harness self-modification.

## 6. Scientific verifier rubric

Each Verifier must be able to establish, without any sealed test labels:

1. **Data provenance:** Ki, Kd, IC50, EC50 remain separate tasks; relation
   symbols are preserved; unmeasured pairs are not invented negatives.
2. **Split isolation:** grouped/scaffold split and duplicate-compound
   disjointness; no preprocessing or supervised selection fitted on validation
   or test molecules.
3. **Model validity:** exact feature dimensions match across train/rank;
   seed, environment, inputs, and training manifest can be reproduced.
4. **Selection validity:** compare on development validation only;
   report AUPRC and prevalence alongside AUROC; use uncertainty or multiple
   validation folds for close calls. Do **not** redefine the locked test
   metric as part of this PR.
5. **Budget / cost:** enforce per-target tool draw budget; count actual models,
   training seconds, LLM tokens, BRS/DRS learning overhead, and Harness
   shadow/replay overhead. Compare total costs over the identical target
   sequence and budget.
6. **Screening integrity:** an unlabeled screening library has no measurable
   hit rate or EF@1%; molecular ranking alone is not measured activity.
7. **Failures:** a model error is not a protocol failure if the Verifier
   verifies the error and the Actor learns the correct boundary; transport
   errors and incomplete evidence never become PASS.

## 7. Anti-premature-convergence Curriculum

The old experiment suggests memory may prematurely narrow model search.
BRS must therefore enforce *diversity* across frozen algorithm, feature, and
(where enabled) interaction-encoding axes, not just maximize its own
previous-best validation AUROC.

DRS should propose experiments expected to **falsify** existing memory claims:
counterexamples, alternative feature classes, distinct scaffolds, negative
transfer and underrepresented target families. Track coverage/novelty and
failures learned, rather than treating fewer tool calls as an automatic win.

Memory retrieval is conditional on endpoint, target family, split regime,
data size, class balance, representation and software version. Attach
applicability limits and counterexamples. A broad claim with weak evidence
must be weakened, superseded or quarantined rather than repeatedly reinforced.
The current prototype enforces basic evidence lineage, **not yet** a complete
semantic reconciliation engine.

## 8. Experimental design and non-goals

* Keep existing P8 W=AutoGluon, A/M/R, frozen experimental search universe,
  and preregistered held-out conditions. Do not silently change them mid-study.
* The Phase 8 handoff explicitly documents that the interaction-form axis and
  budget mapping are incomplete. Fix those in a separately reviewed experiment
  protocol, not as a side effect of this RSI port.
* Run paired target-level evaluations with repeated seeds/folds and report
  uncertainty, including the documented p7 noise floor.
* Compare quality **and** cumulative wall time, tokens, number of model fits,
  exploration overhead, memory I/O, shadow replays, and human promotions.
* Add ablations: BRS only; DRS only; both; verified memory vs unverified memory;
  Curriculum guided vs fixed curriculum; M vs R with verified promotions.
* A strong AutoML comparison is essential. It is a hypothesis, **not a
  guaranteed result**, that R can achieve comparable quality with lower cost.
* Do not change the basic LLM weights, mix assay endpoints, treat training
  refits as validation, or access locked per-sample information.

## 9. Incremental implementation plan

| Milestone | Scope | Acceptance |
| --- | --- | --- |
| **P0 (this PR)** | State machine + portable unit tests + architecture | Requires remote test run; no claims of integration or empirical gains |
| P1 | Authenticated, independently executed Verifier adapter for DSH Tickets | Deliberate false passes, bad manifests and mismatched artifacts rejected |
| P2 | BRS Curriculum/Actor scheduling + durable wave barrier, recovery journal | Independent branches start from same memory hash; crash/resume never double-publishes |
| P3 | DRS targeted practice + fresh same-target retry, conflict-aware memory | Failed practice cannot become target PASS; contradictory memories reconciled |
| P4 | Connect `harness.propose` to trace diagnosis, shadow/gate and operator promotion | R has demonstrably deployed Harness versions; M never does |
| P5 | Frozen test-time runner + complete W/A/M/R ablation | Locked labels remain sealed; costs and quality compared over matching splits/budgets |

### Production integration surfaces (review before editing)

* `src/research/registry.ts` / `tools.ts`: expose *safe task actions* to the Actor,
  but not `commit_wave`, `freeze_for_test`, `register_harness_promotion`,
  or direct evidence-write capabilities.
* `ops/phase7_seq.py`: source of historical sequential target orchestration;
  implement a new P9 driver rather than overwriting historical P7 records.
* `scientific/src/evovs_science/experience/store.py`: migrate to an immutable
  versioned memory backend after preserving historical entry compatibility.
* `evolution/gate.py` and `versions.json`: authoritative gate and
  promotion ledger; this PR does not relax or replace either.
* `scientific/src/evovs_science/evaluation/locked.py`: **do not touch**.
* `scientific/.venv` and `.venv-automl`: remain separate, version-pinned.

## 10. Verification and handoff

Per [AGENTS.md](../AGENTS.md), run all checks on the authorized internal
server, not a local machine. Suggested commands (not executed here):

```bash
PYTHONPATH=scientific/src python3 -m unittest scientific.tests.test_rsi_protocol -v
PYTHONPATH=scientific/src python3 -m unittest discover -s scientific/tests -p 'test_rsi_protocol.py' -v
```

No credentials, models, external data, locked labels, protected files or
new scientific dependencies are needed for these *pure protocol* unit tests.
Their results must be recorded before advancing beyond P0.

**Open design choices requiring separate user/operator approval before coding:**
whether to alter the DSH runtime, host transaction semantics, locked evaluator,
split/label/metric definitions, experiment budget, or baseline/search-space
specification. The current PR makes none of those changes.
