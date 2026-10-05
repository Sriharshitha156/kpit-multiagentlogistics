# Likely jury questions

## What is actually decentralized?

In auction mode, each agent computes its own bid, maintains a local ledger, and resolves from bids it received. Failure suspicion is also made by peers. The process, bus, and environment are still centralized software components in this prototype; this is not a distributed deployment.

## Why use an auction instead of nearest-agent allocation?

Nearest distance alone ignores battery and existing workload. The auction uses route ETA and workload in its cost, and rejects agents whose battery cannot cover planned work plus a charger trip. Whether that improves outcomes must be shown by controlled experiments; it is not guaranteed for every scenario.

In the recent three-seed stress run, high demand averaged 49% completion for B1, 96% for B2, and 95% for AUCTION. Under normal demand, all were about 97% complete, while AUCTION's average delivery time was longer than B2's (26.3 vs 22.9 ticks). The evidence supports battery/workload-aware allocation over the naive nearest baseline in some cases; it does not show that decentralized AUCTION is better than smart central B2.

## How is battery considered?

Battery is a feasibility gate with a configurable safety margin. It is not directly added as a continuous term in the bid score. A low-battery idle agent heads to a charger. Charging stations have unlimited capacity in this model.

## How does priority affect allocation?

Priority changes the weight on time until pickup in the bid formula; task queues also execute higher-priority work first, then older tasks. The bid's route and battery estimate now model that same queue order. There is no deadline or service-level guarantee.

## What happens when an agent fails?

Peers infer failure after a heartbeat timeout, inspect their own ledgers, and re-auction unfinished tasks. The deterministic demo uses key 4 to fail a carrier after pickup. A carried parcel is approximated at the last reported vehicle position. This is delayed, simulated recovery, not an instantaneous physical rescue.

## What recovery data do we record?

For each reassigning event, we record the failed/replacement agent IDs, failure and reassignment ticks, elapsed recovery time, the replacement's route distance to the parcel, and eventual delivery outcome. The route distance is not an estimate of extra distance compared with a counterfactual run.

## What happens with 100 agents?

The paired scalability batch tested 100 agents, 50 scheduled orders, 10 seeded failures, and 600 ticks over three seeds. All strategies averaged 48.7 completed orders out of 50 (97.3%). On the machine used for that batch, average simulator time per run was about 0.86 seconds for B1, 3.13 for B2, and 7.12 for AUCTION; AUCTION sent about 23,864 messages per run. These are simulation and host-specific measurements, not evidence for a real 100-vehicle fleet or larger scales.

## What if communication overhead is high?

The bus counts generated transmissions and recipient deliveries, and supports configurable delay and message loss. In a five-seed sweep, 20% message loss produced about 13% conflicting accepted auctions; at 50% loss, about 54 auctions per run had no observed accept claim. The latter also explains why the conflict fraction falls slightly at 50%: fewer auctions reached any acceptance. The bus does not model bandwidth, congestion, or actual network resource limits, and its global audit cannot prove what each agent received. This is a first-order simulation study, not a distributed-consensus guarantee.

## What proves the approach works?

The code includes 63 automated tests for bidding, winner selection, A*, recovery, UI behavior, and experiment repeatability. The paired stress batch has 63 simulator runs (three strategies × seven cases × three seeds), and the scale batch has 99 runs (three strategies × eleven settings × three seeds). The metrics come from simulator state, not hand-entered results. These demonstrate software behavior under the stated assumptions; they do not prove field performance. Report the protocol, seeds, run horizon, and variability.

## What is genuinely new here?

The project brings together agent-local bidding, battery feasibility, priority-aware task queues, heartbeat-based recovery, and inspectable message/audit views in one teaching simulator. The auction and A* methods are standard techniques; the defensible contribution is the integrated, reproducible demonstration, not a claim of a new allocation algorithm.

## Which parts are assumptions?

Grid geometry, vehicle speed, battery capacity/use, charging rate, task arrival rate, obstacle layout, timeout, and network behavior are configurable assumptions. They are not real-city or manufacturer-calibrated values.

## What are the most important limitations?

Single-process simulated communications, no collision avoidance/congestion, permanent failures, unlimited charger capacity, approximate parcel recovery location, no deadlines, and baseline information/cost asymmetries.

## What is the next credible improvement?

Measure how often agents disagree about auction winners as message loss rises, and add bandwidth or charger-capacity limits if those are central to the intended claim. Consider sockets only if a real networked deployment is a project requirement; the current simulator intentionally uses a deterministic in-process bus.
