"""Runs one mission: watches the bot, asks the model when something changes,
checks its answer and sends the command to the game with .bot order.

  python run_mission.py            full run
  python run_mission.py --once     one decision, then stop
  python run_mission.py --dry-run  ask the model, but send nothing to the game
"""

import argparse
import getpass
import os
import time
import tomllib

from agent import decide, llm
from agent.runlog import RunLog
from agent.soap import Soap
from agent.telemetry import Telemetry


def connect_soap(cfg):
    user = os.environ.get("TB_SOAP_USER") or input("SOAP account: ")
    password = os.environ.get("TB_SOAP_PASS") or getpass.getpass("SOAP password: ")
    return Soap(cfg["soap"]["url"], user, password)


def wait_for_bot(telemetry, seconds=15):
    end = time.time() + seconds
    while telemetry.state is None and time.time() < end:
        time.sleep(0.5)
    return telemetry.state is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--once", action="store_true", help="make one decision, then stop")
    parser.add_argument("--dry-run", action="store_true", help="send nothing to the game")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    bot, mission, agent_cfg = cfg["bot"], cfg["mission"], cfg["agent"]

    soap = None if args.dry_run else connect_soap(cfg)
    telemetry = Telemetry(bot, cfg["telemetry"]["port"])
    telemetry.start()
    print(f"Waiting for telemetry of {bot} ...")
    if not wait_for_bot(telemetry):
        print(f"No telemetry for {bot}. Is AiPlayerbot.Observability = 1 and the bot online?")
        return

    log = RunLog("runs", f"{bot}_{cfg['ollama']['model'].replace(':', '-')}")
    log.write("run_start", bot=bot, model=cfg["ollama"]["model"], strategy="direct",
              dry_run=args.dry_run, config=cfg)
    print(f"Run log: {log.path}")

    system = decide.system_prompt(cfg)
    start = time.time()
    trigger = "the mission starts"
    history, events = [], []
    decisions, last_decision, wait_until, last_state_log = 0, 0.0, 0.0, 0.0
    last_pos, still_since = None, start
    result = None

    while result is None:
        time.sleep(1)
        now = time.time()
        state = telemetry.state
        minutes = (now - start) / 60

        new_events = telemetry.take_events()
        for event in new_events:
            log.write("game_event", **event)
        events += new_events
        if now - last_state_log >= 10:
            log.write("state", **{k: state.get(k) for k in
                      ("zone", "x", "y", "hp", "max_hp", "state", "travel_to", "travel_dist", "last_action")})
            last_state_log = now

        # End of the mission.
        if decide.distance_to(state, mission["target"]) <= mission["target"]["radius"]:
            result = "success"
        elif state["state"] == "dead":
            result = "failed: the bot died"
        elif minutes >= mission["time_limit_min"]:
            result = "failed: time limit"
        elif now - telemetry.state_time > 10:
            result = "stopped: no telemetry for 10 s"
        elif decisions >= agent_cfg["max_decisions"]:
            result = "stopped: decision limit"
        if result:
            break

        # When to ask the model.
        pos = (round(state["x"]), round(state["y"]))
        if pos != last_pos:
            last_pos, still_since = pos, now
        if trigger is None:
            anomalies = [e for e in new_events if e["kind"] == "ANOMALY"]
            if anomalies:
                trigger = f"the game reported {anomalies[-1].get('type')}"
            elif now - still_since >= agent_cfg["idle_seconds"] and now >= wait_until:
                still = int(now - still_since)
                trigger = f"you seem to be stuck for {still} seconds" if state["state"] == "stalled" \
                    else f"you have not moved for {still} seconds"
        if trigger is None or now - last_decision < agent_cfg["min_seconds_between_decisions"]:
            continue

        # Ask the model, check the answer, send it.
        user = decide.user_prompt(cfg, state, telemetry.money, minutes, trigger, events, history)
        answer, text, timing = llm.chat(cfg["ollama"], system, user, decide.SCHEMA)
        decisions += 1
        commands, error = decide.validate(cfg, answer, state)
        log.write("decision", n=decisions, trigger=trigger, prompt=user, answer=text,
                  valid=error is None, error=error, commands=commands, timing=timing)
        short = f"{(answer or {}).get('command')} {(answer or {}).get('target')}"
        print(f"[{minutes:5.1f} min] {trigger} -> {short} ({timing['wall_s']} s)"
              + (f"  REJECTED: {error}" if error else ""))

        if error:
            history.append(f"{short} -> rejected: {error}")
        else:
            for command in commands:
                order = f"bot order {bot} {command}"
                ok, reply, ms = soap.run(order) if soap else (True, "dry run", 0)
                log.write("order", command=order, ok=ok, reply=reply, ms=ms)
                print(f"           {order} -> {reply}")
            history.append(f"{short} -> sent at {minutes:.1f} min")
            if answer["command"] == "wait":
                wait_until = time.time() + int(float(answer["target"]))

        # Give the command time to work before calling the bot idle again.
        last_decision = still_since = time.time()
        trigger = None
        if args.once:
            result = "stopped: --once"

    minutes = (time.time() - start) / 60
    log.write("run_end", result=result, minutes=round(minutes, 2), decisions=decisions)
    print(f"Result: {result} after {minutes:.1f} min and {decisions} decisions.")


if __name__ == "__main__":
    main()
