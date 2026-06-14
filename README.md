# acoustic-marten-deterrent

Acoustic deterrent for **stone martens** (beech martens) running on a
**Raspberry Pi**. It procedurally generates an irregular, unpleasant **audible**
sound (no ultrasound) so a marten won't want to settle in the building — attic,
garage, or under a car bonnet.

> **Humane deterrence:** the sound **does not harm** the marten, it just makes
> the place unpleasant. The **permanent fix** is always to find and **seal the
> entry holes** and **remove scent marks** (martens come back by smell). The
> deterrent buys time and lowers how attractive the space is — it does not
> replace the repair.

The sound is designed to be **habituation-resistant**: every element has a
random frequency, length, and order; gaps between bursts are random; and the
volume randomly jumps between bursts (startle effect).

## What happens on start

1. The device **starts deterring immediately** — it waits for no trigger.
2. It logs that it's starting, and plays a **startup test burst**
   (default ~8 s, `startup_test_s`) — use it to **set the volume**
   (alsamixer / `master_volume`).
3. Then it switches to normal operation: it fires deterrent bursts at
   **random intervals**. The startup burst can be disabled (`startup_test_s = 0`).

## Hardware

- **Raspberry Pi 3 or 4** (Raspberry Pi OS, both Bookworm and Bullseye).
- An **active (powered) speaker**:
  - **Small space:** a cheap USB-powered speaker (e.g. *Genius SP-Q160*),
    3.5 mm jack input → **3.5 mm M–M jack cable** from the Pi.
  - **Large space:** an active PA box (6.3 mm jack / XLR input → matching cable
    from the Pi's 3.5 mm jack).
- Optionally a USB sound card (better output than the built-in jack) — select it
  in the config via `audio_device`.

## Audio routing on the Pi

```bash
# Force output to the 3.5 mm jack (not HDMI):
sudo raspi-config            # System Options → Audio → Headphones
# or directly:
amixer cset numid=3 1        # 1 = jack, 2 = HDMI

# Set the volume with headroom below clipping:
alsamixer                    # arrows to adjust, M = mute toggle
```

Keep the volume on the lower side and fine-tune it during the startup burst.
Mind the neighbours.

## Installation

```bash
git clone https://github.com/austy246/acoustic-marten-deterrent.git
cd acoustic-marten-deterrent
chmod +x install.sh
./install.sh
```

`install.sh`:
- installs `libportaudio2` (apt),
- creates a `.venv` virtualenv with `numpy` + `sounddevice`
  (because of **PEP 668** on Bookworm we use a venv, not the system pip),
- creates `config.ini` from the example,
- installs the systemd unit (but does **not** enable it — see below).

Make sure your user is in the `audio` group:

```bash
sudo usermod -aG audio $USER   # then log out / log back in
```

## Test

```bash
.venv/bin/python -m marten_deterrent --list-devices   # list audio devices
.venv/bin/python -m marten_deterrent --once           # play a few elements and exit
```

It also runs on a regular PC/laptop (for testing the sound) — you just need
`numpy` and `sounddevice` installed.

## Running as a service

Intentionally **without auto-start on boot** (a safety decision — start it
manually):

```bash
sudo systemctl start acoustic-marten-deterrent.service   # turn on
sudo systemctl stop  acoustic-marten-deterrent.service   # turn off
sudo systemctl status acoustic-marten-deterrent.service  # status + log
journalctl -u acoustic-marten-deterrent.service -f       # live log
```

- `systemctl start` = run now.
- `systemctl enable` = start automatically on boot — **we do not do this.**
  If, after careful thought, you want it, run `sudo systemctl enable --now …`.

## Runtime control (without restarting the process)

State is driven by a **state file** (default `/run/marten/state`, contents
`on`/`off`). It's checked every iteration, so you can mute/unmute without a
restart:

```bash
echo off > /run/marten/state    # mute
echo on  > /run/marten/state    # deter again
```

If the file does not exist it counts as `on` (so the device deters right after
start).

## Remote access via Raspberry Pi Connect

Nobody is on site — you connect to the Pi remotely:

```bash
sudo apt install rpi-connect-lite
loginctl enable-linger $USER
rpi-connect on
rpi-connect signin            # prints a link, sign in via the browser
```

Then go to **connect.raspberrypi.com → Remote shell** and from there:

```bash
sudo systemctl start acoustic-marten-deterrent.service
echo off > /run/marten/state
```

## Configuration

A human-editable INI file (`config.ini`, see `config.example.ini`). Keys:

| Key | Default | Meaning |
|------|---------|--------|
| `audio_device` | (empty) | output device (index or part of the name); empty = default |
| `sample_rate` | `44100` | sample rate |
| `master_volume` | `0.7` | master volume 0–1 |
| `peak_ceiling_dbfs` | `-3` | digital headroom — peaks never exceed this (dBFS, ≤ 0) |
| `fade_ms` | `5` | fade in/out at element edges (ms), anti-click |
| `min_gap_s` | `8` | min random gap between bursts (s) |
| `max_gap_s` | `45` | max random gap between bursts (s) |
| `freq_min` | `1000` | lower frequency bound (Hz) |
| `freq_max` | `16000` | upper frequency bound (Hz) — higher adds nothing audibly |
| `startup_test_s` | `8` | length of the startup volume-setting burst (s); `0` = off |
| `max_runtime_hours` | `12` | after this much continuous runtime → auto off |
| `state_file` | `/run/marten/state` | on/off state file |
| `keepalive` | `false` | quiet tone during gaps to defeat speaker auto-standby |
| `keepalive_level_dbfs` | `-50` | keepalive tone level (dBFS) |

## Speaker protection

- **Digital headroom:** peaks held below `peak_ceiling_dbfs` (default −3 dBFS).
- **Fade in/out** (default 5 ms) at each element's edges → no speaker clicks.
- **Low duty cycle** (random gaps) → the voice coil cools between bursts.
- Frequencies capped above at `freq_max` (default 16 kHz).

## Safety notes

- **Auto-off timeout:** after `max_runtime_hours` (default 12 h) of continuous
  runtime the deterrent switches itself to `off` and waits to be re-armed (state
  file / restart). A fail-safe in case the internet drops and you can't reach the
  Pi via Connect.
- **Clean shutdown:** on `SIGTERM` (so also `systemctl stop`) it stops playback
  immediately.
- **Volume and neighbours:** the sound is audible and unpleasant by design — set
  a sensible volume and be considerate of the surroundings.

## Development / extension

The code is modular and typed (`src/marten_deterrent/`: `config`, `engine`,
`control`, `runner`, `cli`), easy to extend — e.g. with a later PIR sensor on
GPIO (fire bursts only on motion).

## License

MIT — see [LICENSE](LICENSE).
