#!/usr/bin/env python3

"""
Test the webhook server functionality
"""

import requests
import json
import time

def test_webhook_server():
    """Test the webhook server endpoints"""
    
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Webhook Server")
    print("=" * 40)
    
    # Test 1: Check server status
    print("\n1. 📊 Testing server status...")
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            print("✅ Server is running!")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Status check failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        print("💡 Make sure to run: python simple_webhook_server.py")
        return
    
    # Test 2: Test manual email check
    print("\n2. 🔍 Testing manual email check...")
    try:
        response = requests.post(f"{base_url}/manual-check")
        if response.status_code == 200:
            print("✅ Manual check triggered!")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Manual check failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Manual check error: {e}")
    
    # Test 3: Get conversations
    print("\n3. 📋 Getting conversations...")
    try:
        response = requests.get(f"{base_url}/conversations")
        if response.status_code == 200:
            conversations = response.json()
            print(f"✅ Found {len(conversations)} conversations")
            for email, conv in conversations.items():
                print(f"   - {email}: {conv['status']} (cycle {conv['cycle_count']})")
        else:
            print(f"❌ Get conversations failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Get conversations error: {e}")
    
    # Test 4: Start new conversation (optional)
    print("\n4. 📧 Test starting new conversation? (y/n): ", end="")
    if input().lower().strip() == 'y':
        email = input("Enter test email: ").strip()
        name = input("Enter test name: ").strip()
        
        try:
            data = {"email": email, "name": name}
            response = requests.post(f"{base_url}/start-conversation", json=data)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Conversation started! Message ID: {result['message_id']}")
            else:
                print(f"❌ Start conversation failed: {response.status_code}")
                print(f"   Error: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Start conversation error: {e}")
    
    print("\n🎉 Webhook server testing complete!")
    print("\n💡 Next steps:")
    print("   - Open http://localhost:5000 in browser")
    print("   - Click 'Trigger Manual Check' button")
    print("   - For real webhooks, use ngrok to expose server")

def test_webhook_endpoint():
    """Test the actual webhook endpoint"""
    print("\n🔔 Testing webhook endpoint...")
    
    try:
        # Simulate a webhook call
        webhook_data = {
            "message": {
                "data": "test notification",
                "messageId": "test123"
            }
        }
        
        response = requests.post(
            "http://localhost:5000/gmail-webhook",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Webhook endpoint working!")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook test error: {e}")

if __name__ == "__main__":
    test_webhook_server()
    test_webhook_endpoint()
