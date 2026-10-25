# ✈️ ATC-ClearCast

> **A real-time, voice-enabled radio companion and Electronic Flight Strip tracker for ATC-SIM.**  
> *Created by Sobhit Sharma.*

---

## 📖 The Story Behind the Project

I have always been deeply passionate about aviation and air traffic control simulation. For years, I enjoyed playing **ATC-SIM**, a browser-based radar simulator. The simulation mechanics, sequencing challenges, and radar management are engaging—but playing it in complete radio silence always felt like something essential was missing.

Real-world air traffic control is almost entirely driven by voice communication, frequency discipline, and standard phraseology. 

I set out to fix that by building **ATC-ClearCast**: a personal passion project that listens to real-time events in the simulator, processes them through an international ICAO radiotelephony grammar engine, broadcasts authentic spoken radio transmissions, and renders a live Electronic Flight Progress Strip board in the terminal.

### 💡 A New Horizon for Browser Automation: Beyond QA Testing

As software and test automation engineers, we often pigeonhole browser automation tools like **Playwright** into testing sandboxes—running test assertions, validating user flows, and executing regression suites in CI/CD pipelines.

**ATC-ClearCast explores a different direction:**
What if browser automation isn't just used to validate applications, but acts as a **live runtime companion engine**? 

By leveraging Playwright's Chromium event loop, two-way JavaScript bindings (`expose_function`), and MutationObserver DOM streams, Playwright becomes an event-driven integration layer that breathes new life, voice accessibility, and external analytics into third-party web apps without modifying their server code.

---

## ✨ Features

- **🎙️ Authentic Voice Communications**: Converts silent game notifications into natural radiotelephony with realistic speech cadence and NATO/ICAO phonetics.
- **📐 ICAO Doc 4444 / Doc 9432 Grammar Pipeline**: Automatically extracts clearance intents (*route, heading, altitude, speed, runway, takeoff/landing*) and reorders scrambled game messages into standard international radiotelephony sequence.
- **📋 Live Electronic Flight Progress Strips**: Renders a real-time terminal board (via `rich`) showing active flights, aircraft models (`B77W`, `A388`), flight phases, assigned runways, headings, exit fixes, and elapsed time formatted in minutes and seconds (`2m 13s`).
- **📍 Smart Airport Detection**: Automatically detects the active airport from DOM elements (`.SanSerif9` / dropdowns) and dynamically personalizes arrival check-in greetings (e.g., *"with you entering Dubai terminal area, awaiting instructions"*).
- **⚠️ Conflict & Error Handling**: Replaces raw game messages with authentic pilot transmissions:
  - *"Unable to comply"* ➔ *"Conflict detected on runway or separation. Controller, please verify your last transmission and resequence."*
  - *"Invalid command"* ➔ *"Say again instruction, transmission unreadable. Tower, please guide."*
- **🚀 Local-First & Zero-Cost**: Runs entirely on your local machine using your installed Google Chrome and native TTS engines without cloud subscription fees or API latency.

---

## 🛠️ Architecture

```
                                  ATC-SIM Web Browser
                               (Playwright + Chromium)
                                          │
                  DOM MutationObserver & JavaScript Bridge (.SanSerif9, .ProgressStrip)
                                          │
                                          ▼
                                   watcher.py
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
         tracker.py (State Machine)                  phraseology_icao.py (Grammar)
   • Flight progress strips                    • Intent extraction (Doc 4444)
   • Runway, heading, fix                      • ICAO priority sorting
   • Age formatting (minutes/secs)             • Standardized radiotelephony
                  │                                               │
                  ▼                                               ▼
          ui.py (Terminal Board)                        tts.py (Speech Engine)
      Live Rich terminal dashboard                  Sequential radio transmission
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Google Chrome (or Edge/Chromium) installed on your machine

### 2. Setup Environment
```bash
# Clone the repository
git clone https://github.com/your-username/atc-clearcast.git
cd atc-clearcast

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate
# On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch ATC-ClearCast
```bash
python main.py
```
This automatically launches Google Chrome, navigates to ATC-SIM, and opens your live terminal Flight Strip board. Close the browser window or press `Ctrl+C` in the terminal to exit cleanly.

### Command-Line Options
```bash
python main.py --help

# Examples:
python main.py --rate 190            # Adjust speech rate (words per minute)
python main.py --aviation-digits    # Use ICAO pronunciation ("tree", "fife", "niner")
python main.py --flight-prefix      # Prefix callsigns with "Flight"
python main.py --speak-typed        # Also speak instructions you manually type
```

---

## 🧪 Running Unit Tests

Run the test suite verifying ICAO phraseology grammar, altitude formatting, and conflict handling:
```bash
python tests_phraseology.py
```

---

## ⚖️ Disclaimer

**ATC-ClearCast** is an independent, unofficial, open-source companion tool created solely for personal entertainment, simulation immersion, and educational exploration of browser automation. 

It is **not** affiliated, associated, authorized, endorsed by, or in any way officially connected with **atc-sim.com** or its creators. All game names, marks, and related assets are trademarks or registered trademarks of their respective owners.

---

## 👤 Author & Acknowledgments

- **Creator**: Sobhit Sharma
- Dedicated to flight simulation fans, air traffic control enthusiasts, and automation engineers pushing the boundaries of what browser tooling can do.
