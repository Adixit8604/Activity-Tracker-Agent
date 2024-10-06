import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.uix.modalview import ModalView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from io import BytesIO
import pyotp
import qrcode
import json
import os
import re
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Path for the JSON file to store users
json_file = 'users_db.json'

# Load users from JSON file, or initialize an empty dictionary
def load_users():
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            return json.load(f)
    else:
        return {}

# Save users to JSON file
def save_users(users_db):
    with open(json_file, 'w') as f:
        json.dump(users_db, f, indent=4)

# Function to generate QR code for TOTP setup and return it as base64
def generate_qr_code_base64(secret_key, user_email):
    totp = pyotp.TOTP(secret_key)
    uri = totp.provisioning_uri(user_email, issuer_name="MyApp")
    
    # Generate QR code
    qr = qrcode.make(uri)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    
    # Convert to base64 for in-memory handling
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_base64

# Email validation using regex
def is_valid_email(email):
    regex = r'^\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.match(regex, email) is not None

# Function to send OTP email
def send_email(receiver_email, subject, message):
    sender_email = "abhimrt8604@gmail.com"  
    sender_password = "uxrh jhuf bqnn xfhp"  # Use app password for Gmail

    # Create email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))

    # Setup SMTP server
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)  # Gmail's SMTP server
        server.starttls()
        server.login(sender_email, sender_password)

        # Send email
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print(f"Email sent to {receiver_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# First screen to input email and submit
class FirstScreen(Screen):
    def handle_email_submit(self):
        email = self.ids.email_input.text.strip()
        verification_label = self.ids.verification_label
        users_db = load_users()  # Load the existing users

        if is_valid_email(email):
            if email in users_db:
                verification_label.text = f"Email {email} is already registered. Proceeding to OTP screen..."
                self.process_verified_user(email)
            else:
                verification_label.text = "Waiting for verification..."
                self.send_verification_email(email)  # Only send email if user doesn't exist
        else:
            verification_label.text = "Invalid email format. Please enter a valid email."

    def send_verification_email(self, email):
        self.verification_token = pyotp.random_base32()  # Generate a unique token
        verification_link = f"http://localhost:8080/verify?email={email}&token={self.verification_token}"
        subject = "Email Verification"
        message = f"Click the link to verify your email: {verification_link}"

        # Send verification email
        send_email(email, subject, message)
        self.ids.verification_label.text = f"Verification email sent to {email}. Please check your inbox."

        # Simulate waiting for verification
        Clock.schedule_once(lambda dt: self.process_verified_user(email), 5)  # Simulate delay for email verification

    def process_verified_user(self, email):
        users_db = load_users()

        if email in users_db:
            # User exists, proceed to QR code screen
            self.manager.current = 'qr_screen'
            qr_screen = self.manager.get_screen('qr_screen')
            qr_screen.setup_for_existing_user(email)
        else:
            # New user, proceed to QR code screen
            self.manager.current = 'qr_screen'
            qr_screen = self.manager.get_screen('qr_screen')
            qr_screen.setup_for_new_user(email)

# Screen to generate and display QR code for OTP
class QRScreen(Screen):
    def setup_for_existing_user(self, email):
        self.current_email = email
        users_db = load_users()
        self.generated_secret = users_db[email]['secret_key']
        
        self.ids.otp_input.disabled = False
        self.ids.otp_submit_btn.disabled = False
        self.ids.done_label.text = f"User {email} exists. Please enter OTP."
        self.ids.done_label.color=(0,0,1,1)

    def setup_for_new_user(self, email):
        self.current_email = email
        secret_key = pyotp.random_base32()  # Generate a new secret key
        self.generated_secret = secret_key

        qr_base64 = generate_qr_code_base64(secret_key, email)
        img_data = BytesIO(base64.b64decode(qr_base64))
        img = CoreImage(img_data, ext="png")
        self.ids.qr_image.texture = img.texture

        self.ids.qr_image.opacity = 1  # Make QR code visible
        self.ids.done_label.text = f"New user: {email}. Scan the QR code in your authenticator app."
        self.ids.done_label.color=(0,0,1,1)
        self.ids.otp_input.disabled = False
        self.ids.otp_submit_btn.disabled = False

        # Send secret key via email for TOTP setup
        send_email(email, "Your Secret Key", f"Your secret key for TOTP: {secret_key}")

    def verify_otp(self):
        otp = self.ids.otp_input.text.strip()
        totp = pyotp.TOTP(self.generated_secret)

        if totp.verify(otp):
            self.ids.done_label.text = "You are done!"
            self.ids.done_label.color = (0, 1, 0, 1)  # Green text for success
            self.manager.current = 'done_screen'  # Move to done screen

            # Save user if new
            if self.current_email:
                users_db = load_users()
                users_db[self.current_email] = {'secret_key': self.generated_secret}
                save_users(users_db)

        else:
            self.ids.done_label.text = "Wrong OTP"
            self.ids.done_label.color = (1, 0, 0, 1)  # Red text for error
            self.ids.otp_input.text = ""  # Clear OTP input for retry

class DoneScreen(Screen):
    pass

# Main Application Class
class MyApp(App):
    def build(self):
        Window.clearcolor = (0.9, 0.9, 0.9, 1)  # Light gray background
        sm = ScreenManager()
        sm.add_widget(FirstScreen(name='first_screen'))
        sm.add_widget(QRScreen(name='qr_screen'))
        sm.add_widget(DoneScreen(name='done_screen'))
        return sm

# Run the app
if __name__ == '__main__':
    MyApp().run()
