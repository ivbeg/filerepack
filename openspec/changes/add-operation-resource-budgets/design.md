## Context

RAR size checks occur after extraction, nested archives receive fresh limits, standalone/PSD decompression is unbounded, and stream peeking can block without a read deadline.

This design covers R13, B5 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Carry an operation context through nested packers, asset walkers, validators, and subprocesses.
- Goal: Enforce root-input cumulative decoded bytes/member/depth/deadline budgets and shared live batch scratch/memory/CPU policy.
- Goal: Validate extraction member identities and link containment.
- Goal: Bound stream peeking, decoder output, subprocess logs, and cancellation.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. A root input owns cumulative decoding/member/depth counters shared by its descendants; bulk coordination owns concurrent scratch/memory/CPU reservations across root inputs.
2. Retain existing max-extract-size and ratio defaults and explicit zero-disable semantics, but make their scope and any additional limits explicit.
3. Preflight estimates are advisory; enforce streaming caps and monitored extraction/encoder limits. Document monitoring granularity/overshoot for external writers.
4. Normalize extracted paths and links before allowing writes; unsupported duplicate/case-colliding or escaping identities fail closed.
5. Deadlines cover peeking, encode/decode, verification, nested processing, and cancellation; process ownership permits termination on budget exhaustion.

## Risks / Trade-offs

- External tools write independently; exact byte prevention may require controlled output paths/streaming, with bounded documented monitoring overshoot.
- CPU auto-count alone is insufficient; separate worker count from encoder thread budget and shared live resources.

## Migration Plan

1. Propagate the context internally without breaking existing RepackOptions entry points.
2. Translate legacy extraction options into the shared policy and document expanded protection scope.

## Verification

- Assert budget failures preserve sources and release process/scratch reservations.
- Measure memory/scratch behavior and document external monitoring bounds rather than claim unsupported hard guarantees.
