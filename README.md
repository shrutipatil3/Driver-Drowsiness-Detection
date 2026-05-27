# 🚗 Driver Drowsiness Detection System

A real-time computer vision and web application designed to prevent road accidents by detecting driver fatigue and drowsiness. This project features a full-stack architecture combining deep learning/computer vision with a secure web dashboard and an automated emergency alert system.

---

## 🎯 Features
* **Real-time Fatigue Detection:** Uses a webcam to monitor the driver's face and tracks eye closure duration.
* **Dual Audio Alerts:** Plays specific warnings (`alarm.wav` and `focus.wav`) instantly when drowsiness or distraction is detected.
* **Secure Authentication:** User signup and login system to access the main system dashboard.
* **Automated SMS Alerts:** Integrated with Twilio to send immediate text alerts to emergency contacts if a driver falls asleep.
* **Live Mapping:** Embedded Google Maps API on the main dashboard for real-time tracking.

---

## 🛠️ Tech Stack
* **Backend Framework:** Python (Flask)
* **Frontend:** HTML5, CSS3, JavaScript (Dashboard view)
* **Computer Vision:** OpenCV, NumPy
* **Database:** MySQL (Managed via XAMPP phpMyAdmin)
* **APIs & Services:** Google Maps API, Twilio SMS API

---

## 📦 Project Structure
When navigating this repository, the files are organized as follows:
* `app.py` — The core Flask backend running the OpenCV logic, database queries, and routing.
* `database.sql` — Database schema export to recreate the user login tables in XAMPP.
* `templates/` — Contains frontend UI (`login.html` and `index2.html` dashboard).
* `static/` — Stores graphic assets like `logo.png`.
* `requirements.txt` — Holds the precise list of library versions needed to run the environment.

---

## 🚀 Installation & Setup Guide

### 1. Database Configuration (XAMPP)
1. Open the **XAMPP Control Panel** and start **Apache** and **MySQL**.
2. Navigate to `http://localhost/phpmyadmin/` in your browser.
3. Create a new database matching the name specified in your local `app.py`.
4. Click the **Import** tab, select the `database.sql` file from this project, and execute it to generate the tables.

### 2. Local Environment Setup
1. Clone this repository to your local machine:
   ```bash
   git clone [https://github.com/shrutipatil3/Driver-Drowsiness-Detection.git](https://github.com/shrutipatil3/Driver-Drowsiness-Detection.git)
2. Create and activate a Python virtual environment, then install all dependencies:
   pip install -r requirements.txt
3. API Key Configuration
   Before launching, ensure you configure the placeholder keys in your local files:
     Google Maps: Add your credential string inside templates/index2.html.
     Twilio SMS: Update the account_sid, auth_token, and phone variables inside app.py.
4. Running the App
   Execute the main application file:
   python app.py
   Open your web browser and go to http://127.0.0.1:5000/ to view the application portal.
