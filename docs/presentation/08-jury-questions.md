# Likely jury questions

## What is actually decentralized?

In auction mode, each agent computes its own bid, maintains a local ledger, and resolves from bids it received. Failure suspicion is also made by peers. The process, bus, and environment are still centralized software components in this prototype; this is not a distributed deployment.

## Why use an auction instead of nearest-agent allocation?

Nearest distance alone ignores battery and existing workload. The auction uses route ETA and workload in its cost, and rejects agents whose battery cannot cover planned work plus a charger trip. Whether that improves outcomes must be shown by controlled experiments; it is not guaranteed for every scenario.

## How is battery considered?

Battery is a feasibility gate with a configurable safety margin. It is not directly added as a continuous term in the bid score. A low-battery idle agent heads to a charger. Charging stations have unlimited capacity in this model.

## How does priority affect allocation?

Priority changes the weight on time until pickup in the bid formula; task queues also execute higher-priority work first, then older tasks. The bid's route and battery estimate now model that same queue order. There is no deadline or service-level guarantee.

## What happens when an agent fails?

Peers infer failure after a heartbeat timeout, inspect their own ledgers, and re-auction unfinished tasks. A carried parcel is approximated at the last reported vehicle position. This is delayed, simulated recovery, not an instantaneous physical rescue.

## What happens with 100 agents?

The repository does not currently contain a 100-agent experiment result. The configured main suite reaches 50 agents and does not measure per-run computation time. We should run and profile 100-agent cases before making a scalability claim.

## What if communication overhead is high?

The bus counts generated transmissions and recipient deliveries, and supports configurable delay and message loss. It does not model bandwidth, congestion, or actual network resource limits. Results under message loss are only a first-order simulation study.

## What proves the approach works?

The code includes deterministic tests for bidding, winner selection, A*, recovery, UI behavior, and experiment repeatability, plus multi-seed experiment tooling. Those show software behavior under tested assumptions; they do not prove field performance. Re-run experiments after code changes and report the protocol, seeds, run horizon, and variability.

## Which parts are assumptions?

Grid geometry, vehicle speed, battery capacity/use, charging rate, task arrival rate, obstacle layout, timeout, and network behavior are configurable assumptions. They are not real-city or manufacturer-calibrated values.

## What are the most important limitations?

Single-process simulated communications, no collision avoidance/congestion, permanent failures, unlimited charger capacity, approximate parcel recovery location, no deadlines, and baseline information/cost asymmetries.

## What is the next credible improvement?

First make paired experiments replay exactly the same task arrivals, road events, and failures for each strategy. Then validate metrics and auction agreement under message loss before adding larger scalability claims or real networking.
