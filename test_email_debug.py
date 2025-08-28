#!/usr/bin/env python3
"""
Test script to debug email sending and database lookups
"""

import requests
import json

def test_email_config():
    """Test email configuration"""
    print("🔧 Testing email configuration...")
    
    response = requests.get("https://74cc9569d223.ngrok-free.app/emailtest")
    data = response.json()
    
    print(f"✅ Email test endpoint response: {data}")
    
    if 'email_config' in data:
        print(f"📧 Email config: {data['email_config']}")
    else:
        print("⚠️  Email config not found in response")

def test_simple_email():
    """Test sending a simple email"""
    print("\n📧 Testing simple email...")
    
    payload = {
        "type": "welcome",
        "email": "daviddors12@gmail.com",
        "name": "David"
    }
    
    response = requests.post(
        "https://74cc9569d223.ngrok-free.app/emailtest",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    data = response.json()
    print(f"✅ Simple email test response: {data}")

def test_status_email():
    """Test sending a status email"""
    print("\n📧 Testing status email...")
    
    payload = {
        "type": "status_departed",
        "email": "daviddors12@gmail.com",
        "name": "David"
    }
    
    response = requests.post(
        "https://74cc9569d223.ngrok-free.app/emailtest",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    data = response.json()
    print(f"✅ Status email test response: {data}")

def test_status_update():
    """Test a status update to see if emails are triggered"""
    print("\n🔄 Testing status update...")
    
    payload = {
        "pickup_id": "TEST123",
        "parent_id": "1",
        "child_id": "1", 
        "pickup_person_id": "1",
        "status": "departed"
    }
    
    response = requests.post(
        "https://74cc9569d223.ngrok-free.app/update_status",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    data = response.json()
    print(f"✅ Status update test response: {data}")

if __name__ == "__main__":
    print("🧪 Starting email debugging tests...\n")
    
    test_email_config()
    test_simple_email()
    test_status_email()
    test_status_update()
    
    print("\n✅ All tests completed!")
    print("\n📋 Next steps:")
    print("1. Check your email (including spam folder)")
    print("2. Check the Flask app logs for detailed email information")
    print("3. If emails still don't arrive, check Hostinger SMTP settings") 