

import smtplib
from email.mime.text import MIMEText

smtp_server = "smtp.mail.eu-west-1.awsapps.com"
smtp_port = 465
smtp_user = "info@docupura.com"
smtp_pass = "\"w9E51\"^gB5E0\""

msg = MIMEText("Hello from AWS WorkMail SMTP!")
msg['Subject'] = "Test Email"
msg['From'] = smtp_user
msg['To'] = "daviddors12@gmail.com"

with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
    server.login(smtp_user, smtp_pass)
    server.sendmail(smtp_user, [msg['To']], msg.as_string())


