from flask import Flask, render_template, Response, jsonify,request
import cv2
import numpy as np
import mediapipe as mp
import pygame
import mysql.connector
import time 

sleep_start_time = None
sms_sent = False
guardian_number_global = None
operator_name_global = "Operator"  
yawn_start_time = None
yawn_alert_active = False
head_out_of_focus_start = None
current_location = {"lat": 0, "lng": 0}

app = Flask(__name__)

# ==========================================
# 1. GLOBAL STATE (The Data Bridge)
# ==========================================
prev_status = "ACTIVE"
monitor_state = {
    "status": "Scanning...",
    "ear": 0.35, 
    "drowsy_episodes": 0,
    "sleep_alerts": 0,
    "risk": "NOMINAL",
    "perclos": 0,
    "yawn_count": 0,       
    "focus_status": "Front"
}

# ==========================================
# 2. SYSTEM INITIALIZATION
# ==========================================
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True)

pygame.mixer.init()
try:
    sleep_sound= pygame.mixer.Sound("alarm.wav")
    focus_sound= pygame.mixer.Sound("focus.wav")
    # yawn_sound= pygame.mixer.Sound("yawn.wav")

except pygame.error:
    print("Warning: alarm.wav not found. Audio alarms will not play.")
    sleep_sound=None
    focus_sound=None
def play_alert(sound_obj):
    if sound_obj and not pygame.mixer.get_busy():
        sound_obj.play()

def compute(ptA, ptB):
    return np.linalg.norm(ptA - ptB)

def get_ear(a, b, c, d, e, f):
    up = compute(b, d) + compute(c, e)
    down = compute(a, f)
    return up / (2.0 * down)

def blinked(ratio):
    if ratio > 0.42:
        return 2 # Active
    elif 0.38 < ratio <= 0.42:
        return 1 # Drowsy
    else:
        return 0 # Sleeping

# ==========================================
# 3. THE ENGINE (With Graph Smoothing)
# ==========================================
def generate_frames():
    global monitor_state, sleep_start_time, sms_sent, guardian_number_global, prev_status, operator_name_global
    
    cap = cv2.VideoCapture(0)
    
    sleep = 0
    drowsy = 0
    active = 0
    
    # Trackers to prevent rapid-fire counting
    is_sleeping = False
    is_drowsy = False
    
    # The Buffer for Smoothing the Graph
    ear_buffer = []
    BUFFER_SIZE = 10 
    
    while True:
        ret, frame = cap.read()
        if not ret: break
            
        h, w, _ = frame.shape 
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                def get_point(index):  
                    lm = face_landmarks.landmark[index]
                    return np.array([int(lm.x * w), int(lm.y * h)])

                left_ear = get_ear(get_point(33), get_point(160), get_point(158), get_point(153), get_point(144), get_point(133))
                right_ear = get_ear(get_point(362), get_point(385), get_point(387), get_point(373), get_point(380), get_point(263))
                avg_ear = (left_ear + right_ear) / 2.0
                
                ear_buffer.append(avg_ear)
                if len(ear_buffer) > BUFFER_SIZE:
                    ear_buffer.pop(0)
                
                smoothed_ear = sum(ear_buffer) / len(ear_buffer)
                monitor_state["ear"] = round(smoothed_ear, 3)

                left_blink = blinked(left_ear)
                right_blink = blinked(right_ear)

                if left_blink == 0 or right_blink == 0:
                    sleep += 1
                    drowsy = 0
                    active = 0
                    monitor_state["perclos"] = min(sleep * 8, 100)
                    if sleep > 6:
                        monitor_state["status"] = "SLEEPING !!!"
                        monitor_state["risk"] = "CRITICAL"
                        
                        if not is_sleeping:
                            monitor_state["sleep_alerts"] += 1
                            is_sleeping = True 
                            
                        if sleep_sound:
                            play_alert(sleep_sound)

                elif left_blink == 1 or right_blink == 1:
                    sleep = 0
                    active = 0
                    drowsy += 1
                    monitor_state["perclos"] = 40
                    if drowsy > 6:
                        monitor_state["status"] = "DROWSY"
                        monitor_state["risk"] = "ELEVATED"
                        sleep_start_time = None
                        sms_sent = False
                        
                        if not is_drowsy:
                            monitor_state["drowsy_episodes"] += 1
                            is_drowsy = True

                else:
                    drowsy = 0
                    sleep = 0
                    active += 1
                    monitor_state["perclos"] = 0
                    if active > 6:
                        monitor_state["status"] = "ACTIVE"
                        monitor_state["risk"] = "NOMINAL"
                        
                        is_sleeping = False
                        is_drowsy = False
                        sleep_start_time = None
                        sms_sent = False
                        pygame.mixer.stop()
        else:
            sleep_start_time = None
            sms_sent = False
            monitor_state["status"] = "NO FACE DETECTED"
        global prev_status

# ===============================
# SMS BLOCK (FIXED)
# ===============================
        if "SLEEP" in monitor_state["status"]:
            if prev_status != "SLEEPING":
                sleep_start_time = time.time()
                sms_sent = False
                prev_status="SLEEPING"
            sleep_duration = time.time() - sleep_start_time
            
            print("Sleep duration:", sleep_duration, "SMS_sent:",sms_sent)
            
            if sleep_duration > 5 and not sms_sent:
                print("SMS condition reached")
                if guardian_number_global:
                    send_sms(guardian_number_global)
                    sms_sent = True
                else:
                    print("ERROR: No guardian number found for this session.")
        else:
            sleep_start_time = None
            sms_sent = False
            prev_status="ACTIVE"
        prev_status = "SLEEPING" if "SLEEP" in monitor_state["status"] else "OTHER"

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        # Threshold for an open mouth (usually > 25-30 pixels depending on camera distance)
        top_inner_lip = get_point(13)
        bottom_inner_lip = get_point(14)
        mouth_opening = compute(top_inner_lip, bottom_inner_lip)
        if mouth_opening > 30: 
            if yawn_start_time is None:
                yawn_start_time = time.time() 
            
            yawn_duration = time.time() - yawn_start_time
            
            if yawn_duration >= 3: 
                monitor_state["status"] = "YAWNING ALERT"
                if not yawn_alert_active:
                    monitor_state["yawn_count"] += 1
                    yawn_alert_active = True 
                
                if focus_sound:
                    play_alert(sleep_sound)
        else:
            yawn_start_time = None
            yawn_alert_active = False

        # --- 3. HEAD POSE / FOCUS DETECTION ---
        # Points: Nose (1), Left Eye (33), Right Eye (263)
        nose = face_landmarks.landmark[1]
        if nose.x < 0.4:  # Looking too far right
            current_focus = "Right"
        elif nose.x > 0.6: # Looking too far left
            current_focus = "Left"
        else:
            current_focus = "Front"

        monitor_state["focus_status"] = current_focus

        if current_focus != "Front":
            if head_out_of_focus_start is None:
                head_out_of_focus_start = time.time()
            
            if (time.time() - head_out_of_focus_start) > 2:
                monitor_state["status"] = "FOCUS FOCUS!"
                if focus_sound:
                    play_alert(focus_sound)
        else:
            head_out_of_focus_start = None
        
    cap.release()

#======================================
# SMS format using twilio
#======================================
from twilio.rest import Client

def send_sms(number):
    global operator_name_global,current_location
    try:
        # Masked for GitHub security
        account_sid = 'YOUR_TWILIO_ACCOUNT_SID'
        auth_token = 'YOUR_TWILIO_AUTH_TOKEN'
        twilio_number = 'YOUR_TWILIO_PHONE_NUMBER' 

        maps_link = f"https://www.google.com/maps?q={current_location['lat']},{current_location['lng']}"
        
        alert_msg = (
            f"\n--- SYSTEM ALERT ---\n"
            f"DROWSINESS DETECTED\n"
            f"Operator: {operator_name_global}\n"
            f"Status: Continuous Sleeping for 7+ seconds while driving\n"
            f"Live Location: {maps_link}\n" 
            f"Time: {time.strftime('%I:%M %p')}\n"
            f"Action: Wake operator immediately."
        )
        client = Client(account_sid, auth_token)

        formatted_number = f"+91{number}" if not str(number).startswith('+') else number
        message = client.messages.create(
            body=alert_msg,
            from_=twilio_number,
            to=formatted_number
        )
        # print(f"SMS SENT TO {operator_name_global}: {message.sid}")
        print(f"DEBUG: Status: {message.status} | Error: {message.error_code} | SID: {message.sid}")
    except Exception as e:
        print(f"TWILIO ERROR: {e}")

# ==========================================
# 4. SERVER ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('index2.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats', methods=['GET', 'POST']) 
def stats():
    global current_location
    if request.method == 'POST':
        data = request.json
        if data and 'lat' in data:
            current_location = data 
    return jsonify(monitor_state)

#database connection
db = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="mp2_db",
    port=3306
)

cursor = db.cursor()
#for registration the data 
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        query = """
        INSERT INTO user 
        (first_name, last_name, email, password, user_phone, guardian_phone)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (
            data['first_name'],
            data['last_name'],
            data['email'],
            data['password'],
            data['user_phone'],
            data['guardian_phone'],
        )

        cursor.execute(query, values)
        db.commit()
        print("Insert success")
        return jsonify({"success": True})
    except Exception as e:
        print("Error:",e)
        return jsonify({"success":False,"message":str(e)})

@app.route('/login', methods=['POST'])
def login():
    global guardian_number_global, operator_name_global  
    try:
        data = request.json
        email = data['email']
        password = data['password']

        query = "SELECT password, guardian_phone, first_name, last_name FROM user WHERE email=%s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()

        if user is None:
            return jsonify({"success": False, "message": "User not found"})

        stored_password, guardian_phone, f_name, l_name = user
        print(guardian_phone)
        if stored_password == password:
            guardian_number_global = guardian_phone
            operator_name_global = f"{f_name} {l_name}" 
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Wrong password"})        
    except Exception as e:
        return jsonify({"success": False, "message": "Server error"})
 
if __name__ == "__main__":
    app.run(debug=True)

# Force language recalculation 
