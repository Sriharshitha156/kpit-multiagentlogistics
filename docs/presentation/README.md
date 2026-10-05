# Presentation guide

Use these short guides to prepare the demo or answer technical questions. They describe the current simulator, including its assumptions and limits.

## Roadmap status

The requested Phase 0–16 implementation checklist is complete, including the strict reviewer pass. Phase 15 has 76 automated tests. The original project brief's unimplemented scope is still stated plainly: there are no delivery deadlines or on-time/late metrics, and order cancellation has no GUI control. These are product limitations, not features to claim in a presentation.

1. [Project pitch](01-project-pitch.md) — 30-second and 2-minute explanations.
2. [Architecture](02-architecture.md) — components, message flow, and where decisions happen.
3. [Auction and routing](03-auction-and-routing.md) — bid formula, battery feasibility, and A*.
4. [Live demo script](04-live-demo.md) — commands, controls, and a short walkthrough.
5. [Metrics and experiments](05-metrics-and-experiments.md) — definitions, units, experiment coverage, and reproducibility caveats.
6. [Failure and recovery](06-failure-recovery.md) — what happens when a vehicle or dispatcher fails.
7. [Assumptions and limitations](07-assumptions-and-limitations.md) — claims to qualify in a presentation.
8. [Jury questions](08-jury-questions.md) — direct answers to likely technical challenges.

## Safe headline claim

This is a grid-based, single-process simulation of decentralized EV delivery task allocation. Agents bid using their own state and a simulated message bus; the project compares that approach with two central dispatch baselines. It is not a real-city deployment, deadline service, or networked fleet.

## Before presenting results

The CSVs in `results/` are outputs from earlier experiment runs. Re-run the relevant suite after code changes before presenting those numbers as evidence for the current version. Explain that seeds pair initial conditions and failure identities, but strategy runs can diverge in their later random events.
