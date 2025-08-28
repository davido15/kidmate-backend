import os
import logging
from flask import current_app
from flask_mail import Mail, Message
from threading import Thread
from datetime import datetime

# Initialize Flask-Mail
mail = Mail()

class EmailService:
    """Email notification service for KidMate application"""
    
    @staticmethod
    def send_async_email(app, msg):
        """Send email asynchronously"""
        with app.app_context():
            try:
                logging.info(f"Attempting to send email to {msg.recipients}")
                logging.info(f"Email subject: {msg.subject}")
                logging.info(f"Mail configuration - Server: {app.config.get('MAIL_SERVER')}, Port: {app.config.get('MAIL_PORT')}, Username: {app.config.get('MAIL_USERNAME')}")
                
                mail.send(msg)
                logging.info(f"Email sent successfully to {msg.recipients}")
            except Exception as e:
                logging.error(f"Failed to send email: {str(e)}")
                import traceback
                logging.error(f"Email sending error traceback: {traceback.format_exc()}")
    
    @staticmethod
    def send_email(subject, recipients, body, html_body=None):
        """Send email notification"""
        try:
            logging.info(f"Creating email message - Subject: {subject}, Recipients: {recipients}")
            
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=body,
                html=html_body
            )
            
            logging.info(f"Email message created successfully, starting async send")
            
            # Send email asynchronously
            Thread(
                target=EmailService.send_async_email,
                args=(current_app._get_current_object(), msg)
            ).start()
            
            logging.info(f"Async email thread started for recipients: {recipients}")
            return True
        except Exception as e:
            logging.error(f"Error creating email message: {str(e)}")
            import traceback
            logging.error(f"Email creation error traceback: {traceback.format_exc()}")
            return False
    
    @staticmethod
    def send_welcome_email(user_email, user_name):
        """Send welcome email to new users"""
        subject = "Welcome to KidMate - Your Account is Ready!"
        body = f"""
        Dear {user_name},
        
        Welcome to KidMate! Your account has been successfully created.
        
        We're excited to help you manage your child's pickup and dropoff services.
        
        If you have any questions, please don't hesitate to contact our support team.
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Welcome to KidMate!</h2>
            <p>Dear {user_name},</p>
            <p>Welcome to KidMate! Your account has been successfully created.</p>
            <p>We're excited to help you manage your child's pickup and dropoff services.</p>
            <p>If you have any questions, please don't hesitate to contact our support team.</p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(subject, [user_email], body, html_body)
    
    @staticmethod
    def send_pickup_notification(parent_email, parent_name, child_name, pickup_person_name, pickup_time):
        """Send pickup notification to parent"""
        subject = f"Pickup Update: {child_name} is being picked up"
        body = f"""
        Dear {parent_name},
        
        Your child {child_name} is being picked up by {pickup_person_name} at {pickup_time}.
        
        You can track the journey in real-time through the KidMate app.
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Pickup Update</h2>
            <p>Dear {parent_name},</p>
            <p>Your child <strong>{child_name}</strong> is being picked up by <strong>{pickup_person_name}</strong> at {pickup_time}.</p>
            <p>You can track the journey in real-time through the KidMate app.</p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(subject, [parent_email], body, html_body)
    
    @staticmethod
    def send_dropoff_notification(parent_email, parent_name, child_name, dropoff_location, dropoff_time):
        """Send dropoff notification to parent"""
        subject = f"Dropoff Complete: {child_name} has arrived safely"
        body = f"""
        Dear {parent_name},
        
        Your child {child_name} has been safely dropped off at {dropoff_location} at {dropoff_time}.
        
        Thank you for using KidMate!
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Dropoff Complete</h2>
            <p>Dear {parent_name},</p>
            <p>Your child <strong>{child_name}</strong> has been safely dropped off at <strong>{dropoff_location}</strong> at {dropoff_time}.</p>
            <p>Thank you for using KidMate!</p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(subject, [parent_email], body, html_body)
    
    @staticmethod
    def send_payment_confirmation(parent_email, parent_name, amount, payment_id, journey_date):
        """Send payment confirmation email"""
        subject = f"Payment Confirmation - KidMate"
        body = f"""
        Dear {parent_name},
        
        Your payment of ${amount} has been successfully processed.
        
        Payment Details:
        - Payment ID: {payment_id}
        - Amount: ${amount}
        - Journey Date: {journey_date}
        
        Thank you for your payment!
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Payment Confirmation</h2>
            <p>Dear {parent_name},</p>
            <p>Your payment of <strong>${amount}</strong> has been successfully processed.</p>
            <br>
            <h3>Payment Details:</h3>
            <ul>
                <li><strong>Payment ID:</strong> {payment_id}</li>
                <li><strong>Amount:</strong> ${amount}</li>
                <li><strong>Journey Date:</strong> {journey_date}</li>
            </ul>
            <p>Thank you for your payment!</p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(subject, [parent_email], body, html_body)
    
    @staticmethod
    def send_password_reset_email(user_email, reset_token):
        """Send password reset email"""
        reset_url = f"https://yourdomain.com/reset-password?token={reset_token}"
        subject = "Password Reset Request - KidMate"
        body = f"""
        Dear User,
        
        You have requested to reset your password for your KidMate account.
        
        Please click the following link to reset your password:
        {reset_url}
        
        If you didn't request this password reset, please ignore this email.
        
        This link will expire in 1 hour.
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Dear User,</p>
            <p>You have requested to reset your password for your KidMate account.</p>
            <p>Please click the following link to reset your password:</p>
            <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>If you didn't request this password reset, please ignore this email.</p>
            <p><strong>This link will expire in 1 hour.</strong></p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(subject, [user_email], body, html_body)
    
    @staticmethod
    def send_attendance_notification(parent_email, parent_name, child_name, attendance_date, status):
        """Send attendance notification"""
        subject = f"Attendance Update: {child_name} - {attendance_date}"
        body = f"""
        Dear {parent_name},
        
        Attendance update for {child_name} on {attendance_date}:
        Status: {status}
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>Attendance Update</h2>
            <p>Dear {parent_name},</p>
            <p>Attendance update for <strong>{child_name}</strong> on {attendance_date}:</p>
            <p><strong>Status:</strong> {status}</p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(subject, [parent_email], body, html_body)
    
    @staticmethod
    def send_journey_status_notification(parent_email, parent_name, child_name, pickup_person_name, status, timestamp, additional_info=None):
        """Send journey status notification"""
        status_messages = {
            'scheduled': {
                'subject': f"Journey Scheduled: {child_name}",
                'title': "Journey Scheduled",
                'message': f"Your child {child_name}'s pickup journey has been scheduled.",
                'details': f"Pickup Person: {pickup_person_name}"
            },
            'pending': {
                'subject': f"Journey Started: {child_name}",
                'title': "Journey Started",
                'message': f"Your child {child_name}'s pickup journey has been initiated.",
                'details': f"Pickup Person: {pickup_person_name} - Journey is ready to begin."
            },
            'departed': {
                'subject': f"Pickup Person Departed: {child_name}",
                'title': "Pickup Person Departed",
                'message': f"Your pickup person {pickup_person_name} has departed to pick up {child_name}.",
                'details': "The pickup person is on their way to the pickup location."
            },
            'picked': {
                'subject': f"Child Picked Up: {child_name}",
                'title': "Child Picked Up",
                'message': f"Your child {child_name} has been picked up by {pickup_person_name}.",
                'details': "Your child is now in transit to the destination."
            },
            'arrived': {
                'subject': f"Arrived at Destination: {child_name}",
                'title': "Arrived at Destination",
                'message': f"Your child {child_name} has arrived at the destination with {pickup_person_name}.",
                'details': "The journey is almost complete."
            },
            'completed': {
                'subject': f"Journey Completed: {child_name}",
                'title': "Journey Completed",
                'message': f"Your child {child_name}'s journey has been completed successfully.",
                'details': "Thank you for using KidMate!"
            },
            'pickup_started': {
                'subject': f"Pickup Started: {child_name}",
                'title': "Pickup Started",
                'message': f"Your child {child_name} is being picked up by {pickup_person_name}.",
                'details': "You can track the journey in real-time through the KidMate app."
            },
            'in_transit': {
                'subject': f"In Transit: {child_name}",
                'title': "Journey In Progress",
                'message': f"Your child {child_name} is currently in transit with {pickup_person_name}.",
                'details': "The journey is progressing smoothly."
            },
            'cancelled': {
                'subject': f"Journey Cancelled: {child_name}",
                'title': "Journey Cancelled",
                'message': f"Your child {child_name}'s journey has been cancelled.",
                'details': additional_info or "Please contact support if you have any questions."
            },
            'delayed': {
                'subject': f"Journey Delayed: {child_name}",
                'title': "Journey Delayed",
                'message': f"Your child {child_name}'s journey has been delayed.",
                'details': additional_info or "We apologize for the inconvenience. We'll keep you updated."
            }
        }
        
        status_info = status_messages.get(status, {
            'subject': f"Journey Update: {child_name}",
            'title': "Journey Update",
            'message': f"Your child {child_name}'s journey status has been updated to: {status}",
            'details': "Please check the app for more details."
        })
        
        body = f"""
        Dear {parent_name},
        
        {status_info['message']}
        
        {status_info['details']}
        
        Time: {timestamp}
        
        Best regards,
        The KidMate Team
        """
        
        html_body = f"""
        <html>
        <body>
            <h2>{status_info['title']}</h2>
            <p>Dear {parent_name},</p>
            <p>{status_info['message']}</p>
            <p>{status_info['details']}</p>
            <p><strong>Time:</strong> {timestamp}</p>
            <br>
            <p>Best regards,<br>The KidMate Team</p>
        </body>
        </html>
        """
        
        return EmailService.send_email(status_info['subject'], [parent_email], body, html_body) 