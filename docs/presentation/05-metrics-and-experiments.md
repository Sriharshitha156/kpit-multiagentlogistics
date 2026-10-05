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

On-time/late percentage, deadlines, battery consumption, computation time, and recovery distance above a no-failure counterfactual are **not** currently reported.

## Baselines

- **B1:** central dispatcher assigns each waiting task to the nearest idle agent. It does not apply the auction battery feasibility rule and does not recover failed-owner tasks.
- **B2:** central dispatcher selects the lowest feasible bid using the agent bid calculation. It sees failures immediately and recovers orphaned work centrally.
- **AUCTION:** agents exchange bids and decide through their ledgers. The message bus simulates transport; this is not real networking.

These baselines differ in information and failure handling. Explain those differences when interpreting results.

## Existing experiment suites

Run a short smoke-scale suite:

```powershell
python experiments/run_experiments.py --suite quick
```

Run the broader configured suite:

```powershell
python experiments/run_experiments.py --suite main
python experiments/make_charts.py --suite main
```

The main suite uses ten seeds, 1,500 ticks per job, and a failure point at tick 300. It varies fleet size (5, 10, 20, 50), task spawn probability, obstacle density, failed-agent count, dispatcher outage, and message loss. It does **not** test 25 or 100 agents, fixed task counts, low-battery stress as a separate scenario, or computation time.

## Reproducibility and fair comparison caveats

Jobs use controlled seeds and preselect the same failed agent IDs across strategies. Initial maps and starts are generated from the same seed. However, separate strategy runs can diverge in later random events as their world states and random-number consumption differ. Do not call every event sequence identical without validating it.

Results in `results/` may predate the current code. Re-run the suite after implementation changes before citing values as evidence for this version. Report number of seeds, tick horizon, settings, variability, and limitations alongside any comparison.
