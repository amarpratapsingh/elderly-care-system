# Elderly Care AI System

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)
![Database](https://img.shields.io/badge/DB-SQLite-003B57)
![License](https://img.shields.io/badge/License-MIT-green.svg)

AI-assisted elderly safety monitoring system with computer vision, voice interaction, reminder scheduling, caregiver alerts, and a Streamlit dashboard.

## Features

- 🎥 **Real-time vision monitoring** with motion detection and inactivity tracking
- 🎙️ **Voice assistant workflow** for listening, intent processing, and spoken responses
- 🚨 **Caregiver alerting** via SMTP email (test, inactivity, emergency)
- ⏰ **Medication/reminder scheduler** with daily and one-time jobs
- 🗄️ **SQLite logging layer** for activities, alerts, voice logs, and reminders
- 📊 **Streamlit dashboard** for live status, history, and alert operations
- ⚙️ **Config-driven behavior** using a single `config.json`
- 🛡️ **Graceful shutdown behavior** and resilient runtime state handling

## Installation

1. **Clone repository**

```bash
git clone <your-repo-url>
cd elderly-care-system
```

2. **Create and activate virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. **Install dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Prepare data folders** (optional, auto-created by app)

```bash
mkdir -p data logs data/audio
```

5. **Set email credentials** in `config.json` (or environment/secrets for deployment)

## Configuration

All runtime behavior is controlled from `config.json`.

- `system`
    - `name`: Display/system name
    - `log_level`: Log verbosity (e.g., `INFO`, `DEBUG`)

- `vision`
    - `camera_id`: Camera index (usually `0`)
    - `width`, `height`: Capture resolution
    - `fps`: Target display/update FPS
    - `motion_threshold`: Pixel-delta threshold for motion
    - `min_contour_area`: Contour area cutoff for true motion
    - `inactivity_threshold_seconds`: Seconds before inactivity state
    - `roi_enabled`: Optional ROI toggle

- `voice`
    - `language`: Primary speech language (e.g., `or`)
    - `fallback_language`: Secondary language
    - `sample_rate`: Audio sample rate
    - `chunk_duration`: Capture chunk duration
    - `stt_engine`: STT engine mode (`google`, etc.)

- `alerts`
    - `caregiver_email`: Destination recipient
    - `smtp_server`, `smtp_port`: SMTP host/port
    - `smtp_username`: SMTP login username
    - `smtp_password`: SMTP password/app password
    - `inactivity_warning_seconds`: Warning threshold
    - `inactivity_critical_seconds`: Critical threshold

- `reminders`
    - Any reminder key with:
        - `time`: `HH:MM`
        - `message`: Spoken reminder text

- `database`
    - `path`: SQLite DB location (default `data/elderly_care.db`)

## Usage

### Run core monitoring service

```bash
python main.py
```

### Run dashboard

```bash
streamlit run modules/dashboard.py
```

### Recommended local workflow

Open two terminals:

- Terminal 1: `python main.py`
- Terminal 2: `streamlit run modules/dashboard.py`

## Project Structure

```text
elderly-care-system/
├── config.json
├── main.py
├── README.md
├── requirements.txt
├── utils.py
├── modules/
│   ├── __init__.py
│   ├── alerts.py
│   ├── dashboard.py
│   ├── database.py
│   ├── scheduler.py
│   ├── vision.py
│   └── voice.py
├── data/
│   └── elderly_care.db
├── logs/
└── test_*.py
```

## Troubleshooting

### 1) Streamlit warning: `use_column_width` deprecated

- Cause: Streamlit API update
- Fix: replace `use_column_width=True` with `use_container_width=True`

### 2) Camera not opening

- Verify webcam is connected and free
- Try changing `vision.camera_id` (`0`, `1`, `2`)
- Test separately:

```bash
python test_camera.py
```

### 3) Microphone initialization fails

- Check OS microphone permission
- Ensure required audio libs are installed
- Test voice capture separately:

```bash
python test_stt.py
```

### 4) Email alerts fail

- Confirm `alerts.smtp_username`, `alerts.smtp_password`, `alerts.caregiver_email`
- For Gmail, use app password (not account password)
- Verify SMTP host/port and firewall rules

### 5) Dashboard shows “Coming Soon” for camera feed

- Dashboard launched correctly, but that section is currently placeholder UI
- Live OpenCV windows are available via test scripts, not full embedded stream

## Demo

Add your media under `docs/demo/` and reference it here.

- Dashboard screenshot:

```markdown
![Dashboard](docs/demo/dashboard.png)
```

- Optional animated demo:

```markdown
![Demo GIF](docs/demo/demo.gif)
```

> Tip: Keep GIF size small (<10 MB) for fast loading on GitHub.

## License

This project is licensed under the MIT License.

If you add a `LICENSE` file, keep this section aligned with that file.
