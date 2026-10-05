# Live demo script

## Start the simulator

From the repository folder in PowerShell:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Start directly in comparison mode with:

```powershell
python main.py --split
```

The left side starts with central B2; the right side is the decentralized auction fleet. In split mode, press `TAB` to switch the central baseline between B1 and B2.

### Optional localhost packet demo

The standard run uses the deterministic in-process bus. To send auction messages as actual UDP datagrams over loopback, run:

```powershell
python main.py --udp --nohelp
```

In Wireshark, capture on the Npcap Loopback Adapter and use the display filter `udp && ip.addr == 127.0.0.1`. Press `1` to create orders, then look for JSON UDP payloads containing message types such as `TASK_REQUEST`, `TASK_BID`, and `TASK_ACCEPT`. This mode still runs all agents in one process. Configured simulated message loss happens before a datagram is sent, so those intentionally dropped messages will not appear in the capture.

### Cancelling an order (developer demo)

An order can be cancelled while it is still waiting for a vehicle. In Python, call `sim.cancel_task(task_id)`: it returns `True` when the order is cancelled and `False` if the task is missing or has already left the waiting state. In auction mode, the desk broadcasts `TASK_CANCEL` and each vehicle marks that order cancelled in its local ledger. The interactive screen does not currently have a cancel button.

## Four-minute walkthrough

### 1. Orient the audience

Point out the grid district, charging stations, vehicles and battery bars, pickup squares, delivery rings, and route lines. Explain that each cell is an abstract road segment; it is not a real city map.

### 2. Create demand and inspect an auction

Press `1` for a rush of orders. Point to the message feed for requests, bids, and accepts. Press `A` to open auction details. Show one task's priority, bids, accepted winner, and tie rule. Use left/right arrows for earlier auctions. Explain that the panel records sends; a missing bid can mean infeasible or not recorded under packet loss.

### 3. Show battery and routing

Point out a battery bar and route line. Explain that battery is used to reject infeasible bids and agents travel to a charger when idle and low on charge. Press `3` to block roads; the system avoids protected cells and the map generator keeps the free map connected.

### 4. Demonstrate deterministic failure recovery

Close the welcome/help overlay if it is open, then press `4`. The simulator resets to a clean run, places a high-priority delivery at Agent 1's location, lets the normal allocation strategy choose the carrier, and fails that vehicle after pickup. In split view, both strategies receive a matching task setup; central B2 may recover immediately while the auction fleet waits for heartbeat-based detection. Watch the message feed, then inspect the task's auction history with `A`.

The `Rescue` value shows replacement-to-parcel route distance and how many recovered tasks eventually completed. The route distance is the replacement's approach distance, not a measured increase over a no-failure counterfactual.

For a less scripted failure, click a vehicle with an active route. Its peers wait for the heartbeat timeout, suspect the silent vehicle, and start a new auction for unfinished work. The exact replacement can vary.

### 5. Compare strategies

Press `S` for split view. Explain B1 as nearest idle without a battery feasibility rule; B2 as a central dispatcher using the cost/battery rule with immediate failure knowledge; and AUCTION as agents deciding from messages. Treat this as a visual demonstration, not a statistically controlled result.

## Useful controls

| Key/action | What it does |
|---|---|
| `SPACE` | Pause/resume |
| `UP` / `DOWN` | Change simulation speed |
| `1` | Add a rush-hour burst |
| `2` | Fail several vehicles, leaving one alive |
| `3` | Block several roads |
| `4` | Reset and run the deterministic fail-while-carrying recovery demo |
| `A` | Open auction details; arrows browse history |
| `S` | Toggle split-screen comparison |
| `TAB` | Switch allocation strategy (or B1/B2 in split view) |
| `D` | Toggle central dispatcher when a central strategy is active |
| Left-click vehicle | Fail it |
| Right-click grid cell | Try to block the cell |
| `ESC` | Quit |

## Practice note

Try the flow once before presenting. The chosen vehicle and exact timings depend on the current simulation state and seed; describe the behavior rather than promising a particular agent ID will win.
