# TortoiseBots LLM agent

An external agent that lets a local language model (through Ollama) make the
slow, high-level decisions of one TortoiseBots bot, for example where to travel
or which flight to take. The bot's own AI still does everything fast (movement,
combat). Made for a bachelor's thesis on local LLMs for MMORPG bots.

```
bot telemetry (UDP) -> trigger -> prompt -> Ollama (JSON schema) -> check -> .bot order over SOAP
```

The model never runs server commands itself. It can only choose `travel`,
`taxi` or `wait`, and the answer is checked against the lists in
`config.toml` before anything is sent.

## Requirements

- A TortoiseWoW server with the TortoiseBots module that has `.bot order`.
- `aiplayerbot.conf`: `AiPlayerbot.Observability = 1` (telemetry, UDP 9195).
- `mangosd.conf`: `SOAP.Enabled = 1`, and the server built with `ENABLE_SOAP=ON`.
- `tortoise_bots.conf`: the bot listed in `TortoiseBots.RemoteOrderBots`.
- A SOAP account with administrator rank (4).
- Ollama with the model from `config.toml`.
- Python 3.11 or newer. No extra packages.

## Use

```
python run_mission.py --dry-run --once   ask the model once, send nothing
python run_mission.py --once             one decision, sent to the game
python run_mission.py                    full mission
```

The SOAP account and password are read from `TB_SOAP_USER` and
`TB_SOAP_PASS`, or asked for at start.

Every run writes `runs/<time>_<bot>_<model>.jsonl`: the start settings, bot
state every 10 s, game events, every decision (prompt, answer, check result,
timing) and every order sent with the server's reply.

## Files

| File | Job |
|---|---|
| `run_mission.py` | Main loop: when to ask the model, when the mission ends |
| `agent/telemetry.py` | Receives the bot's state and events from the server |
| `agent/decide.py` | Prompt, answer check, translation to bot commands |
| `agent/llm.py` | Ollama call (thinking off, JSON schema, fixed seed) |
| `agent/soap.py` | Sends `.bot order` to the server |
| `agent/runlog.py` | Writes the run log |
| `config.toml` | Bot, mission, model, places and flight masters |
