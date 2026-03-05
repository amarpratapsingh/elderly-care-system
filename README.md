# Elderly Care Monitoring System

A comprehensive AI-powered monitoring system designed to ensure the safety and well-being of elderly individuals through continuous motion detection, voice interaction, automated alerts, and medication reminders.

## Features

- **Motion Detection**: Real-time video monitoring with inactivity alerts
- **Voice Assistant**: Natural language voice commands and responses in local language (Odia)
- **Activity Logging**: SQLite database for tracking all activities and alerts
- **Alert System**: Automated email notifications to caregivers
- **Medication Reminders**: Scheduled reminders for medications and meals
- **Caregiver Dashboard**: Streamlit web interface for monitoring status and logs
- **Adaptive Alerts**: Configurable thresholds for motion and inactivity

## System Requirements

- Python 3.8+
- Webcam or USB camera
- Microphone for voice commands
- Internet connection (for email alerts and voice synthesis)
- OpenAI API key (for advanced voice processing)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd elderly-care-system
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the system:
- Edit `config.json` with your settings
- Set up email credentials in alerts section
- Configure camera and audio parameters

5. Run the system:
```bash
python main.py
```

6. Access the dashboard:
```bash
streamlit run modules/dashboard.py
```

## Configuration

Edit `config.json` to customize:
- **Vision**: Camera ID, resolution, motion thresholds
- **Voice**: Language, audio sample rate
- **Alerts**: Email settings for notifications
- **Reminders**: Medicine and meal times

## Project Structure

```
elderly-care-system/
├── README.md
├── requirements.txt
├── config.json
├── .gitignore
├── main.py
├── utils.py
├── modules/
│   ├── __init__.py
│   ├── vision.py
│   ├── voice.py
│   ├── database.py
│   ├── alerts.py
│   ├── scheduler.py
│   └── dashboard.py
└── data/
    └── elderly_care.db
```

## Dependencies

See `requirements.txt` for complete list. Key packages:
- OpenCV (vision processing)
- NumPy (numerical operations)
- PyAudio (audio input)
- SpeechRecognition (voice commands)
- Streamlit (web dashboard)
- Schedule (reminder scheduling)

## Usage

### Starting the monitoring system:
```bash
python main.py
```

### Accessing the dashboard:
```bash
streamlit run modules/dashboard.py
```

### Voice Commands:
- "Hello" - Greet the system
- "Reminder" - Check upcoming reminders
- "Help" - Get assistance

## Logging

All activities are logged in SQLite database (`data/elderly_care.db`). Logs include:
- Motion detection events
- Voice commands
- Alert triggers
- Reminder confirmations

## Email Alerts

The system sends automated email alerts when:
- Inactivity is detected beyond configured threshold
- Emergency commands are issued
- Medication reminders are triggered

## Safety Notes

- Ensure proper internet connection for alert delivery
- Configure email with app-specific passwords (not main password)
- Test alerts before deploying to production
- Regularly backup the database

## Troubleshooting

### Camera not detected:
- Verify camera is connected
- Check `camera_id` in config.json (try 0, 1, 2)
- Run: `python -c "import cv2; print(cv2.getBuildInfo())"`

### Audio not working:
- Verify microphone is connected
- Test with: `python -c "import pyaudio; print(pyaudio.PyAudio().get_device_count())"`
- Check microphone permissions

### Email alerts not sending:
- Verify SMTP credentials in config.json
- Use app-specific password for Gmail
- Check firewall/antivirus blocking SMTP

## Support

For issues or feature requests, please contact the development team.

## License

MIT License - See LICENSE file for details

## Authors

Development Team - Elderly Care Solutions

## Version

1.0.0 - Initial Release
