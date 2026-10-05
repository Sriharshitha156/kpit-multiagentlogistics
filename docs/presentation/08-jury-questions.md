# Likely jury questions

## What is actually decentralized?

In auction mode, each agent computes its own bid, maintains a local ledger, and resolves from bids it received. Failure suspicion is also made by peers. The process, bus, and environment are still centralized software components in this prototype; this is not a distributed deployment.

## Why use an auction instead of nearest-agent allocation?

Nearest distance alone ignores battery and existing workload. The auction uses route ETA and workload in its cost, and rejects agents whose battery cannot cover planned work plus a charger trip. Whether that improves outcomes must be shown by controlled experiments; it is not guaranteed for every scenario.

In the recent three-seed stress run, high demand averaged 49% completion for B1, 96% for B2, and 95% for AUCTION. Under normal demand, all were about 97% complete, while AUCTION's average delivery time was longer than B2's (26.3 vs 22.9 ticks). The evidence supports battery/workload-aware allocation over the naive nearest baseline in some cases; it does not show that decentralized AUCTION is better than smart central B2.

## How is battery considered?

Battery is a feasibility gate with a configurable safety margin. It is not directly added as a continuous term in the bid score. A low-battery idle agent heads to a charger. The simulator now records movement energy used and energy added at chargers, in battery units; these are not calibrated to kilowatt-hours. Charging stations have unlimited capacity in this model.

## How does priority affect allocation?

Priority changes the weight on time until pickup in the bid formula; task queues also execute higher-priority work first, then older tasks. The bid's route and battery estimate model that same queue order. Orders carry a default 90-minute deadline for measuring outcomes, using an illustrative one-minute-per-tick conversion; bidding does not guarantee a deadline.

## What happens when an agent fails?

Peers infer failure after a heartbeat timeout, inspect their own ledgers, and re-auction unfinished tasks. The deterministic demo uses key 4 to fail a carrier after pickup. A carried parcel is approximated at the last reported vehicle position. This is delayed, simulated recovery, not an instantaneous physical rescue.

## What recovery data do we record?

For each reassigning event, we record the failed/replacement agent IDs, failure and reassignment ticks, elapsed recovery time, the replacement's route distance to the parcel, and eventual delivery outcome. The route distance is not an estimate of extra distance compared with a counterfactual run.

## What happens with 100 agents?

The paired scalability batch tested 100 agents, 50 scheduled orders, 10 seeded failures, and 600 ticks over three seeds. All strategies averaged 48.7 completed orders out of 50 (97.3%). On the machine used for that batch, average simulator time per run was about 0.86 seconds for B1, 3.13 for B2, and 7.12 for AUCTION; AUCTION sent about 23,864 messages per run. These are simulation and host-specific measurements, not evidence for a real 100-vehicle fleet or larger scales.

## What if communication overhead is high?

The in-process bus counts generated transmissions and recipient deliveries, and supports configurable delay and message loss. An optional `--udp` mode sends the serialized messages over localhost UDP, where Wireshark can capture them. In a five-seed sweep, 20% simulated message loss produced about 13% conflicting accepted auctions; at 50% loss, about 54 auctions per run had no observed accept claim. The lower conflict fraction at 50% reflects fewer auctions reaching acceptance. Neither transport models bandwidth, congestion, or real network partitions, and the global audit cannot prove what each agent received. This is not a distributed-consensus guarantee.

## What proves the approach works?

The code currently has 80 automated tests for bidding, winner selection, A*, recovery, edge cases, UI behavior, UDP message transfer, and experiment repeatability. The paired stress batch has 63 simulator runs (three strategies × seven cases × three seeds), the scale batch has 99 runs, the auction consistency sweep has 30 runs, and the energy batch has 36 runs. The metrics come from simulator state, not hand-entered results. These demonstrate software behavior under the stated assumptions; they do not prove field performance. Report the protocol, seeds, run horizon, and variability.

## What is genuinely new here?

The project brings together agent-local bidding, battery feasibility, priority-aware task queues, heartbeat-based recovery, and inspectable message/audit views in one teaching simulator. The auction and A* methods are standard techniques; the defensible contribution is the integrated, reproducible demonstration, not a claim of a new allocation algorithm.

## Which parts are assumptions?

Grid geometry, vehicle speed, battery capacity/use, charging rate, task arrival rate, obstacle layout, timeout, and network behavior are configurable assumptions. They are not real-city or manufacturer-calibrated values.

## What are the most important limitations?

Single-process simulated communications, no collision avoidance/congestion, permanent failures, unlimited charger capacity, approximate parcel recovery location, assumed tick-to-minute conversion, and baseline information/cost asymmetries.

## What is the next credible improvement?

If separate-process deployment becomes a requirement, move from the optional localhost demo to isolated agent processes and test packet loss, timing, and recovery there. For the current simulator, the next useful improvement is to model bandwidth or charger capacity if those are central to the claim.

## Strict reviewer verdict

This is a credible, testable teaching prototype for decentralized task allocation. It is not evidence that an auction will outperform a well-informed central dispatcher: paired results show B2 is often at least as strong, and the auction pays extra message and runtime costs. The strongest defensible claim is that agents can coordinate through local bids and recover work in this simulation, with measurable behavior under seeded load and failure scenarios.

Before presenting, regenerate the experiment results from the current commit and state the seed count and run horizon. Do not claim real-city readiness, guaranteed consensus under message loss, real-world deadline performance, collision-safe routing, or production-scale networking. The model has no collision or traffic model and no charger capacity limit. Order cancellation is available only before assignment; the GUI cancels the oldest waiting order.
