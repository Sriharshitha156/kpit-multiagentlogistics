# Smart Multi-Agent EV Delivery Simulator

## The idea, in one minute

Imagine a busy neighbourhood where delivery orders arrive all day. Instead of one central computer assigning every parcel, a fleet of electric vans coordinates locally. When an order appears, eligible vans estimate whether they can deliver it with their current battery and workload, then bid for it. The best bid wins.

If a van needs energy, it heads to a charging station. If a van fails while carrying orders, the other vans detect the missing heartbeats and can recover its work. The goal is to explore whether this decentralized fleet can keep deliveries moving through rush hour and vehicle or dispatcher failures.

This project is a **simulation**, not a deployed delivery service or a model trained on real city data. Its map is a 30-by-20 road grid that represents a small urban district.

## What the demo shows

- Eight electric-vehicle agents coordinate delivery tasks using decentralized auctions.
- Battery use, charging stations, task capacity, deadlines, and route planning affect which vehicle can take a job.
- Rush-hour order bursts, blocked roads, and vehicle failures can be triggered during a run.
- Heartbeats help agents detect failed peers; the surviving fleet can reclaim orphaned deliveries.
- Split-screen mode compares the auction fleet with central dispatch strategies (nearest idle and a battery-aware dispatcher).
- The window displays the map, vehicles and battery levels, active orders, performance metrics, and a plain-English event feed.

## A presentation-ready example

“At the start of the day, a customer places an order with a delivery deadline. Nearby vans check their routes, battery, and current workload. Vans that cannot safely complete it do not bid; the most suitable available van wins the job. When evening demand surges, the fleet distributes more orders across its available vehicles. If one van stops responding, its peers detect the failure and reassign the stranded work. We compare this with a centrally dispatched fleet and measure delivery performance and recovery.”

## What we measure

The simulator records completed, waiting, and lost deliveries; average delivery time in simulation ticks; vehicle failures and battery failures; task reassignment and recovery time; fleet utilization; and message traffic. The experiment scripts run repeatable comparisons across seeds and export CSV summaries and charts. Deadline-based on-time and late percentages are a possible next metric; they are not implemented yet.

## Run it

```bash
pip install -r requirements.txt
python main.py            # interactive window
python main.py --split    # compare central dispatch and auction side by side
python -m unittest discover -s tests
```

## Controls

`SPACE` pause | `UP`/`DOWN` speed | `R` new map | `TAB` switch strategy | `S` split screen\
`1` rush hour | `2` failure storm | `3` blocked road | `D` dispatcher on/off | `H` heartbeats in feed\
`A` auction bids (browse with `LEFT`/`RIGHT`, close with `A`, `ESC`, or click)\
Click a vehicle to fail it | right-click a cell to block it | `ESC` quit

## Experiments

```bash
python experiments/run_experiments.py --suite sweep
python experiments/run_experiments.py --suite main
python experiments/make_charts.py --suite main
```

Results are written to `results/<suite>/` as run data, summaries, settings, and charts.

## Assumptions and current limitations

Vehicle speed, battery capacity and consumption, charging rate, order arrival rate, and deadlines are configurable simulation assumptions; they are not calibrated against real fleet or city data. The network is simulated inside one program. Vehicles may share a map cell, failures are permanent, chargers have unlimited capacity, and a failed vehicle's parcel location is approximated using its last heartbeat position. The central baselines do not include communication costs. These limits should be stated when presenting results.

## Main files

`config.py` (simulation settings) | `agent.py` (bidding, battery, heartbeat, recovery) | `baseline_dispatcher.py` (central baselines) | `simulation.py` (tick loop) | `environment.py` and `pathfinding.py` (grid and A*) | `metrics.py` and `experiments/` (results) | `main.py` (Pygame demo) | `tests/`
