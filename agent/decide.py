"""Builds the prompt, checks the model's answer and turns it into bot commands.

This is the "direct" strategy: one prompt, one JSON command.
"""

import math

# Zone ids from the telemetry (AreaTable.dbc) for the mission area.
ZONES = {
    1: "Dun Morogh",
    10: "Duskwood",
    12: "Elwynn Forest",
    33: "Stranglethorn Vale",
    40: "Westfall",
    44: "Redridge Mountains",
    1519: "Stormwind City",
    1537: "Ironforge",
}

# The target is a free string, not an enum of valid places, so that wrong
# places stay visible as invalid commands in the results.
SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "enum": ["travel", "taxi", "wait"]},
        "target": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["command", "target", "reason"],
}


def zone_name(state):
    return ZONES.get(state.get("zone"), f"zone {state.get('zone')}")


def distance_to(state, target):
    if state.get("map") != target["map"]:
        return math.inf
    return math.hypot(state["x"] - target["x"], state["y"] - target["y"])


def flight_master_near(cfg, state, yards=8.0):
    """The flight master the bot stands next to, or None."""
    for master in cfg.get("flight_masters", []):
        if distance_to(state, master) <= yards:
            return master
    return None


def system_prompt(cfg):
    facts = "\n".join(f"- {fact}" for fact in cfg["mission"]["facts"])
    places = ", ".join(cfg["travel"]["destinations"])
    return f"""You control a character in World of Warcraft (vanilla).
Mission: {cfg["mission"]["goal"]}
Time limit: {cfg["mission"]["time_limit_min"]} minutes.
{facts}

Answer with exactly one command as JSON:
- travel: walk to a place. target is one of: {places}
- taxi: fly from the flight master next to you. target is one of the flights listed for that flight master.
- wait: do nothing for a while. target is the number of seconds (10 to 120).
Keep the reason to one short sentence."""


def user_prompt(cfg, state, money, minutes, trigger, events, history):
    zone = zone_name(state)
    hp = round(100 * state["hp"] / max(state["max_hp"], 1))
    lines = [
        f"Time used: {minutes:.1f} of {cfg['mission']['time_limit_min']} minutes.",
        f"Position: {zone} (x {state['x']:.0f}, y {state['y']:.0f}). Health {hp}%. State: {state['state']}.",
    ]
    if state.get("travel_to"):
        lines.append(f"Travelling to: {state['travel_to']}, {state['travel_dist']} yards left.")
    else:
        lines.append("Travelling to: nothing.")
    if money is not None:
        lines.append(f"Money: {money // 10000}g {money // 100 % 100}s {money % 100}c.")
    master = flight_master_near(cfg, state)
    if master:
        lines.append(f"Flight master next to you: {master['name']}, flights to: {', '.join(master['routes'])}.")
    else:
        lines.append("Flight master next to you: none.")
    if events:
        lines.append("Recent events: " + "; ".join(describe(e) for e in events[-5:]) + ".")
    if history:
        lines.append("Your last commands:")
        lines += [f"- {h}" for h in history[-5:]]
    lines.append(f"You are asked now because: {trigger}.")
    lines.append("Choose the next command.")
    return "\n".join(lines)


def describe(event):
    if event["kind"] == "event":
        details = " ".join(str(event[k]) for k in ("info1", "info2") if event.get(k))
        return f"{event.get('event')} {details}".strip()
    return f"{event['kind']} {event.get('type', '')} {event.get('details', '')}".strip()


def validate(cfg, answer, state):
    """Returns (bot commands, None) or (None, error text)."""
    if not isinstance(answer, dict):
        return None, "answer is not a JSON object"
    command = answer.get("command")
    target = str(answer.get("target", "")).strip()

    if command == "travel":
        for place in cfg["travel"]["destinations"]:
            if place.lower() == target.lower():
                # Follow and stay would hold the bot in place, so clear them first.
                return ["nc -follow,-stay", f"go travel {place}"], None
        return None, f"unknown travel destination '{target}'"

    if command == "taxi":
        master = flight_master_near(cfg, state)
        if not master:
            return None, "no flight master next to the bot"
        for name, number in master["routes"].items():
            if name.lower() == target.lower():
                return [f"taxi {number}"], None
        return None, f"no flight to '{target}' from {master['name']}"

    if command == "wait":
        try:
            seconds = int(float(target))
        except ValueError:
            return None, f"wait needs a number of seconds, got '{target}'"
        if not 10 <= seconds <= 120:
            return None, f"wait must be 10 to 120 seconds, got {seconds}"
        return [], None

    return None, f"unknown command '{command}'"
