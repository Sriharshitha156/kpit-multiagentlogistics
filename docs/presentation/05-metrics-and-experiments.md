# Metrics and experiments

## Metrics currently calculated

| Metric | Definition in code | Unit / caveat |
|---|---|---|
| Created | Number of tasks spawned | Tasks |
| Completed | Tasks whose status is `COMPLETED` | Tasks |
| Waiting | Tasks whose status is `OPEN` | Tasks at the current end of run |
| Lost | Assigned/picked-up tasks whose current owner has failed | Current snapshot, not all failures over time |
| Average delivery time | Mean of `completed_tick - created_tick` for completed tasks | Simulation ticks; excludes unfinished tasks |
| Total distance | Sum of agent movement steps | Grid cells |
| Failed agents | Agents currently in `FAILED` state | Agents |
| Battery failures | Failed agents whose failure reason is `BATTERY` | Agents |
| Utilization | Sum of busy ticks divided by sum of alive ticks | Ratio; busy means pickup travel or delivery, not charging/idle |
| Reassigned tasks | Number of tasks with at least one recorded recovery reassignment | Unique tasks, not total reassignment events |
| Recovery events | Number of failed-owner-to-replacement assignments recorded | Events |
| Recovered deliveries | Reassigned tasks that eventually reached `COMPLETED` | Unique tasks |
| Recovery approach distance | Sum of each replacement agent's planned route from its position at reassignment to the parcel pickup point | Grid cells; not excess distance versus a no-failure counterfactual |
| Average reassignment time | Mean of failure tick to new-owner assignment tick for recorded recoveries | Simulation ticks |
| Average detection latency | First recorded peer-detection tick minus true failure tick | Simulation ticks; first detection only per failed agent |
| False suspicions | Count of false peer-failure declarations recorded by agents | Declarations, not a probability/rate |
| Messages sent | Bus transmissions | A broadcast counts once |
| Messages delivered | Recipient copies delivered by the bus | Broadcast counts once per recipient; lost messages excluded |
| Messages per completed task | Sent transmissions divided by completed deliveries | Undefined when nothing completed |

On-time/late percentage, deadlines, battery consumption, and recovery distance against a no-failure counterfactual are **not** currently reported. Computation time is reported only by the `paired-scale` suite.

## Baselines

- **B1:** central dispatcher assigns each waiting task to the nearest idle agent. It does not apply the auction battery feasibility rule and does not recover failed-owner tasks.
- **B2:** central dispatcher selects the lowest feasible bid using the agent bid calculation. It sees failures immediately and recovers orphaned work centrally.
- **AUCTION:** agents exchange bids and decide through their ledgers. The message bus simulates transport; this is not real networking.

These baselines differ in information and failure handling. Explain those differences when interpreting results.

## Existing experiment suites

Run a short paired smoke-scale suite:

```powershell
python experiments/run_experiments.py --suite paired-quick
```

Run the broader configured suite:

```powershell
python experiments/run_experiments.py --suite paired-main
python experiments/make_charts.py --suite paired-main
```

The paired main suite uses ten seeds, 1,500 ticks per job, and a failure point at tick 300. It varies fleet size (5, 10, 20, 50), task spawn probability, obstacle density, failed-agent count, dispatcher outage, and message loss. It does **not** test 25 or 100 agents, fixed task counts, low-battery stress as a separate scenario, or computation time.

### Scalability check

Run the dedicated, smaller scalability suite and generate its charts:

```powershell
python experiments/run_experiments.py --suite paired-scale-clean
python experiments/make_charts.py --suite paired-scale-clean
```

This suite uses three seeds and 600 ticks per run. It checks 5, 10, 25, 50, and 100 agents with 50 scheduled orders; 25, 50, and 100 scheduled orders with 25 agents; and obstacle densities of 0%, 10%, and 20% with 25 agents. Each case has a seeded failure load (about 10% of the fleet for the agent-count experiment; two agents in the other cases). The `paired-scale-clean` suite writes to a fresh results folder. The reported `compute_seconds` is wall-clock time for simulator setup, execution, and metric calculation on the machine running it. Treat that timing as machine dependent, and do not describe the three-seed run as proof of real-world scalability.

### What “paired requests” means

For one seed and scenario, the runner creates a list of orders in advance: when each order arrives, its pickup, destination, and priority. B1, B2, and AUCTION then receive that same list. In everyday terms, this is like comparing three delivery teams on the same day's orders, instead of giving each team a different day's work. This makes the strategy comparison easier to interpret; vehicles can still take different routes and finish different numbers of orders.

Use the `paired-*` suites for current comparisons. Their separate output folders keep older unpaired results intact. The task arrival schedule is replayed even if a strategy has many jobs waiting, so a paired run can exceed the interactive demo's open-task cap. The scalability suite uses exact order counts, distributed across the run by its seeded schedule.

## Reproducibility and fair comparison caveats

Paired jobs use controlled seeds, the same precomputed delivery requests, and the same failed agent IDs. Initial maps and starts use the same seed. Separate strategy runs can still diverge in movement, message delivery, and other later random events because their states and random-number consumption differ; only the scheduled requests and selected failures are deliberately matched.

Results in `results/` may predate the current code. Re-run the suite after implementation changes before citing values as evidence for this version. Report number of seeds, tick horizon, settings, variability, and limitations alongside any comparison.
