# F6 Decision: Heap Matching Algorithm

**Date:** 2026-04-19
**Context:** F6.S01 — Spatial Matching of heaps between two surveys
**Status:** Decided

## Problem

Given two sets of heap polygons from surveys A and B of the same site, we need
to match corresponding heaps (same physical heap measured at two different times)
and detect added, removed, and ambiguous cases.

## Options Considered

### 1. Greedy Assignment (sorted by IoU descending)

- **Complexity:** O(n² log n) — compute all pairwise IoUs, sort, greedily assign
- **Optimality:** Local optimum. Can fail on adversarial cases: if heap A₁
  overlaps B₁ slightly more than B₂, greedy assigns A₁→B₁, but B₂ has no other
  candidate and remains unmatched — even though the global optimum would be
  A₁→B₂ (freeing B₁ for another A heap).
- **Implementation:** ~30 lines of custom code, no external dependency.

### 2. Hungarian Algorithm (scipy.optimize.linear_sum_assignment)

- **Complexity:** O(n³) — for n ≤ 100 heaps (realistic steel-plant site), this
  is trivially fast (<100 ms even at n=100).
- **Optimality:** Global optimum on the cost matrix. Guarantees the maximum total
  IoU across all assignments.
- **Implementation:** One-liner via `scipy.optimize.linear_sum_assignment`.
  scipy is already a project dependency.

## Ambiguous Cases (both algorithms)

Neither algorithm handles merges (two A heaps → one B heap) or splits
(one A heap → two B heaps) natively. Both require post-processing:

- **Detection:** For each matched pair (aᵢ, bⱼ), check the raw IoU matrix for
  other candidates above the IoU threshold. If aᵢ has IoU > threshold with
  multiple B heaps, or bⱼ has IoU > threshold with multiple A heaps, flag the
  pair as `"ambiguous"`.
- **No automatic resolution:** Ambiguous cases are surfaced in the UI with an
  orange badge for manual operator review. Automatic merge/split would be
  error-prone and against the project's design philosophy of operator control.

## Decision

**Hungarian algorithm via `scipy.optimize.linear_sum_assignment`.**

### Rationale

1. **Correctness over simplicity:** Hungarian guarantees global optimum for
   negligible additional complexity. The greedy failure mode (described above)
   is realistic for adjacent heaps in a steel plant.
2. **Trivial implementation cost:** scipy is already installed; the call is
   a single function invocation.
3. **Performance is irrelevant:** At n ≤ 100, O(n³) completes in milliseconds.
4. **Post-processing is identical:** Ambiguity detection is the same for both.

### Threshold tuning

- `iou_threshold = 0.3` (default): two polygons must overlap by at least 30%
  to be considered the same heap. Allows for moderate shape changes between
  surveys while rejecting coincidental adjacency.
- `stability_threshold = 0.05`: matched heaps with |ΔV|/V_A < 5% are classified
  as "unchanged" to avoid noise in the comparison view.

Both thresholds are configurable via `ComparisonConfig` and exposed in the UI
as sliders with sensible defaults.
