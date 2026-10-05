# Assumptions and limitations

State these plainly if asked what the simulator proves.

## Model assumptions

- The world is a 30 × 20 four-neighbour grid with randomly generated obstacles and three charging cells by default.
- The default fleet has eight agents; each can hold at most three active/queued tasks.
- Battery capacity is 100 units, movement uses one unit per grid cell, and charging adds five units per tick up to a target of 90.
- Task arrivals, priorities, map layout, speed, battery use, charging, timeout, message delay, and message loss are configurable simulation values. They are not calibrated to a real fleet.
- Orders default to a 90-minute simulated deadline, with one minute per tick. This time conversion is illustrative and is not calibrated to real vehicle speeds or city travel times.

## System limitations

- Agents, world, and renderer still run in one Python process. The optional `--udp` mode sends actual localhost UDP datagrams, but it does not create independent agent processes or real vehicle radios.
- The default bus models delay and independent message loss. UDP mode can be captured on loopback, but neither mode models bandwidth limits, congestion, authentication, or real network partitions. Configured simulated message loss is applied before UDP transmission.
- Obstacle changes are delivered directly to agents as world events. The map generator and road-blocking controls preserve connectivity.
- Vehicles can share a cell; there is no collision avoidance or traffic congestion model.
- Failures are permanent. Chargers have unlimited capacity.
- The parcel location after a carrier failure is approximated from the last heartbeat.
- Auction decisions can disagree under message loss if agents receive different bids. The UI exposes accept conflicts; consistency under arbitrary loss is not guaranteed.
- Central baselines have no message-cost model. B2 has immediate failure knowledge; B1 has no recovery.
- Task cancellation is supported only while an order is waiting for assignment. The GUI can cancel the oldest waiting order; an assigned delivery cannot currently be withdrawn.
- Existing saved experiment outputs can be stale relative to newer code changes.

## Claims to avoid

- “Works in a real city” or “tested on real EV data.”
- “Always beats a central dispatcher.”
- “Scales efficiently to real fleets” based on the single-host 100-agent simulation. Current evidence is three seeds, 50 orders, 10 failures, and 600 ticks; it reports runtime and message counts only for that setup.
- “Cloud failure has been tested” as a deployed cloud outage; only the simulated dispatcher can be toggled offline.
- “The agents run as separate processes over a vehicle network.” The optional UDP mode only uses localhost sockets inside the same application process.
- “Deliveries meet real 90-minute deadlines” because the tick-to-minute conversion and travel model are assumptions, not calibrated real-world data.
