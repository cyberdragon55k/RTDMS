# Real-Time Disaster Data Management System (RTDMS)

## Overview

The **Real-Time Disaster Data Management System (RTDMS)** is a Python-based platform designed to aggregate, analyze, and visualize disaster-related data in real time. This system aims to assist emergency responders, government agencies, and the general public by providing accurate and timely disaster data.

## Features

- **Real-Time Data Aggregation:** Collects disaster reports from multiple sources.
- **Data Visualization:** Interactive charts and maps for better understanding.
- **Automated Alerts:** Sends notifications based on predefined disaster thresholds.
- **User-Friendly Dashboard:** Accessible interface for monitoring disaster events.
- **Scalability:** Supports multiple data sources and formats.

## Technologies Used

- **Backend:** Python (Flask/Django)
- **Database:** MySQL/PostgreSQL
- **Frontend:** HTML, CSS, JavaScript (React/Vue)
- **APIs:** OpenWeather, USGS Earthquake API, Social Media Data

## Installation

### Prerequisites

- Python 3.x
- MySQL or PostgreSQL
- Node.js (for frontend)

### Steps

1. **Clone the Repository:**
   ```sh
   git clone https://github.com/cyberdragon55k/RTDMS.git
   cd RTDMS
   ```
2. **Install Dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
3. **Configure Database:**
   - Update `config.py` with database credentials.
   - Run migrations:
     ```sh
     python manage.py migrate
     ```
4. **Start the Server:**
   ```sh
   python app.py
   ```
5. **Run Frontend (if applicable):**
   ```sh
   cd frontend
   npm install
   npm start
   ```

## Usage

1. **Register/Login** to access the dashboard.
2. **View real-time disaster updates** on the map.
3. **Set alerts** for specific disaster types.
4. **Download reports** for analysis.

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch (`feature-branch`).
3. Commit your changes.
4. Push and submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For questions or collaborations, reach out to [cyberdragon55k](https://github.com/cyberdragon55k).

