# AutoSwarm: Urban EV Delivery Coordination Simulator

See the [presentation guide](docs/presentation/README.md) for a pitch, architecture overview, demo script, metric definitions, limitations, and jury Q&A.

## The idea, in one minute

Imagine a busy neighbourhood where delivery orders arrive all day. Instead of one central computer assigning every parcel, a fleet of electric vans coordinates locally. When an order appears, eligible vans estimate whether they can deliver it with their current battery and workload, then bid for it. The best bid wins.

If a van needs energy, it heads to a charging station. If a van fails while carrying orders, the other vans detect the missing heartbeats and can recover its work. The goal is to explore whether this decentralized fleet can keep deliveries moving through rush hour and vehicle or dispatcher failures.

This project is a **simulation**, not a deployed delivery service or a model trained on real city data. Its map is a 30-by-20 road grid that represents a small urban district.

## What the demo shows

- Eight electric-vehicle agents coordinate delivery tasks using decentralized auctions.
- Battery feasibility, charging stations, task capacity, route planning, and task deadlines affect measured outcomes. The default deadline clock is configurable and illustrative.
- Rush-hour order bursts, blocked roads, and vehicle failures can be triggered during a run.
- Heartbeats help agents detect failed peers; the surviving fleet can reclaim orphaned deliveries.
- Split-screen mode compares the auction fleet with central dispatch strategies (nearest idle and a battery-aware dispatcher).
- The auction fleet can be split into two communication groups. Each group continues bidding with its local task ledger; restoring the link exchanges ledgers and resolves conflicting task owners.
- The Results view (`E`) reads the experiment summaries saved under `results/`; it displays measured values and shows a run command when a suite is missing.
- Optional localhost UDP mode sends real JSON datagrams for packet-capture demos; agents still run in one process.
- The window displays the map, vehicles and battery levels, active orders, performance metrics, and a plain-English event feed.

## A presentation-ready example

At the start of the day, a customer places a delivery order. Nearby vans check their routes, battery, and current workload. Vans that cannot safely complete it do not bid; the lowest-cost eligible bid wins. When evening demand surges, the fleet distributes more orders across its available vehicles. If one van stops responding, its peers detect the failure and re-auction the stranded work. We compare this with centrally dispatched fleets and measure delivery performance and recovery.

## What we measure

The simulator records completed, waiting, lost, cancelled, on-time, late, and overdue deliveries; average delivery time; vehicle failures; battery energy used and charged; task reassignment and recovery time; fleet utilization; and message traffic. The default deadline is 90 simulated minutes at one minute per tick, an illustrative assumption rather than a real travel-time calibration. Experiment scripts run repeatable comparisons across seeds and export CSV summaries and charts.

## Run it

```bash
pip install -r requirements.txt
python main.py            # interactive window
python main.py --split    # compare central dispatch and auction side by side
python main.py --udp      # send auction messages over localhost UDP
python -m unittest discover -s tests
```

For Wireshark, capture on the Npcap Loopback Adapter with display filter `udp && ip.addr == 127.0.0.1`. The regular in-process transport remains the default and is used for repeatable experiment suites.

## Controls

`SPACE` pause | `UP`/`DOWN` speed | `R` new map | `TAB` switch strategy | `S` split screen\
`1` rush hour | `2` failure storm | `3` blocked road | `4` recovery demo | `D` dispatcher on/off | `H` heartbeats in feed\
`A` inspect bids and score inputs | `E` experiment results | `P` partition/restore auction network\
`T` switch between plain-English and technical message feeds\
`C` cancel the oldest order still waiting for assignment\
Click a vehicle to fail it | right-click a cell to block it | `ESC` quit

## Experiments

```bash
python experiments/run_experiments.py --suite sweep
python experiments/run_experiments.py --suite main
python experiments/make_charts.py --suite main
python experiments/run_experiments.py --suite paired-partition
python experiments/make_charts.py --suite paired-partition
```

Results are written to `results/<suite>/` as run data, summaries, settings, and charts.

## Assumptions and current limitations

Vehicle speed, battery capacity and consumption, charging rate, order arrival rate, and the one-minute-per-tick deadline clock are configurable simulation assumptions; they are not calibrated against real fleet or city data. Agents, world, and renderer run in one program. The default network is simulated; `--udp` sends optional loopback datagrams but does not separate agents into processes or model a production network. The partition control simulates communication loss between groups, not a real network outage. Ledger reconciliation is deterministic simulation logic and is not a formal distributed-consensus protocol. Vehicles may share a map cell, failures are permanent, chargers have unlimited capacity, and a failed vehicle's parcel location is approximated using its last heartbeat position. The central baselines do not include communication costs. These limits should be stated when presenting results.

## Main files

`config.py` (simulation settings) | `agent.py` (bidding, battery, heartbeat, recovery) | `baseline_dispatcher.py` (central baselines) | `simulation.py` (tick loop) | `environment.py` and `pathfinding.py` (grid and A*) | `communication.py` / `socket_bus.py` (in-process and optional UDP messages) | `metrics.py` and `experiments/` (results) | `main.py` (Pygame demo) | `tests/`
