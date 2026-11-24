# SENTINEL Wokwi ESP32 Simulation Guide

## Quick Launch in Wokwi (Browser)
1. Open **https://wokwi.com/projects/new/esp32**.
2. Paste [`sketch.ino`](sketch.ino) into the `sketch.ino` tab.
3. Paste [`diagram.json`](diagram.json) into the `diagram.json` tab.
4. Click **Library Manager (+)** or paste [`libraries.txt`](libraries.txt) into the `libraries.txt` tab.
5. Click **Start Simulation (Green Play)**.
6. Open your SENTINEL Dashboard (**http://localhost:8000**) &rarr; click **Hardware Twin (ESP32)** in the top pill navigation bar.

## Addressable 16-LED Zone Mapping
| LED Index | Campus Zone | Meaning |
| :--- | :--- | :--- |
| `0 – 3` | Tech Pro Building (`TPB-F1` .. `TPB-F4`) | Green = Safe, Amber = Hold, Red = Threat |
| `4 – 7` | Academic Building (`AB-F1` .. `AB-F4`) | Green = Safe, Amber = Hold, Red = Threat |
| `8 – 9` | Laboratory Building (`LB-F1` .. `LB-F2`) | Green = Safe, Amber = Hold, Red = Threat |
| `10` | `GATE-W` Status | Green = Open, Red = Blocked |
| `11` | `GATE-NE` Status | Green = Open, Red = Blocked |
| `12 – 15` | Campus Global Beacon | Mirrors Overall System Threat Level |

## Bidirectional Defense Demo Flow
1. **Dashboard &rarr; Wokwi:** Trigger **Gate-W Threat** or upload a threat video in SENTINEL. Immediately watch LED `10` turn Red, OLED display `EVAC: GATE-NE`, and the buzzer chirp/alarm.
2. **Wokwi &rarr; Dashboard:** Press the **Red THREAT TRIGGER** button (or turn the **ACOUSTIC dB** knob all the way up) in Wokwi. Watch SENTINEL immediately switch to `CRITICAL`, log the event in `sentinel.db`, and reroute all 36 rooms. Press the **Green ALL-CLEAR RESET** button to clear everything back to `NORMAL`.
