# AutoSwarm presentation guide

Use these short guides to prepare the demo or answer technical questions. They describe the current simulator, its assumptions, and its limits.

## Current implementation

The original implementation checklist and the final AutoSwarm integration pass are complete. The final pass adds a communication-partition demo with ledger synchronization, a CSV-backed experiment-results view, a plain-English event feed with a technical-log toggle, and actual bid-factor details in the auction inspector. Orders default to 90 simulated minutes at one minute per tick; this remains an illustrative assumption. Cancellation applies only before assignment.

1. [Project pitch](01-project-pitch.md) — 30-second and 2-minute explanations.
2. [Architecture](02-architecture.md) — components, message flow, and where decisions happen.
3. [Auction and routing](03-auction-and-routing.md) — bid formula, battery feasibility, and A*.
4. [Live demo script](04-live-demo.md) — commands, controls, and a short walkthrough.
5. [Metrics and experiments](05-metrics-and-experiments.md) — definitions, units, experiment coverage, and reproducibility caveats.
6. [Failure and recovery](06-failure-recovery.md) — what happens when a vehicle or dispatcher fails.
7. [Assumptions and limitations](07-assumptions-and-limitations.md) — claims to qualify in a presentation.
8. [Jury questions](08-jury-questions.md) — direct answers to likely technical challenges.

## Safe headline claim

AutoSwarm is a grid-based, single-process simulation of decentralized EV delivery task allocation. Agents bid using their local state and a simulated message bus; the project compares that approach with two central dispatch baselines and records deadline outcomes under configurable assumptions. A communication partition lets isolated groups keep bidding locally, then exchange task ledgers on reconnection. This is not a real-city deployment, production vehicle network, or formal consensus protocol.

## Before presenting results

The Results view (`E`) reads saved CSV summaries and shows the source suite, strategy, seed count, means, and standard deviations. Existing results may predate the final code changes. Re-run the relevant suite before presenting values as evidence for this version. Seeds pair initial conditions and failure identities, but strategy runs can diverge in later random events.
