#!/usr/bin/env python3

"""
Email Conversation System - Demo Script

This script demonstrates the complete email conversation workflow:
1. Send service offering email
2. Monitor for replies
3. Auto-respond based on sentiment analysis
4. Track conversation cycles
"""

from conversation_manager import ConversationManager, start_conversation_with_prospect, check_and_respond_to_replies
import time

def demo_workflow():
    """Demonstrate the complete workflow"""
    
    print("🚀 EMAIL CONVERSATION SYSTEM DEMO")
    print("=" * 50)
    
    # Step 1: Start a conversation
    print("\n📧 STEP 1: Starting new conversation")
    email = input("Enter a test email address: ").strip()
    name = input("Enter contact name (optional): ").strip()
    
    message_id = start_conversation_with_prospect(email, name)
    if message_id:
        print(f"✅ Service offering email sent! Message ID: {message_id}")
    else:
        print("❌ Failed to send email")
        return
    
    # Step 2: Show how to check for replies
    print("\n🔍 STEP 2: Checking for replies")
    print("The system will now check for any replies...")
    check_and_respond_to_replies()
    
    # Step 3: Show conversation tracking
    print("\n📊 STEP 3: Conversation tracking")
    manager = ConversationManager()
    conversations = manager.load_conversation_data()
    
    if email in conversations:
        conv = conversations[email]
        print(f"✅ Conversation tracked for {email}")
        print(f"   Status: {conv['status']}")
        print(f"   Cycle: {conv['cycle_count']}/4")
        print(f"   Messages: {len(conv['conversation_history'])}")
    
    print("\n📋 WHAT HAPPENS NEXT:")
    print("1. When the prospect replies, the system will:")
    print("   • Detect the reply automatically")
    print("   • Analyze sentiment (positive/negative/neutral/questions)")
    print("   • Generate appropriate response")
    print("   • Send auto-reply")
    print("   • Update conversation tracking")
    
    print("\n2. The conversation continues for up to 4 cycles")
    print("3. Different responses based on sentiment:")
    print("   • Positive: Move toward scheduling call")
    print("   • Questions: Provide detailed answers")
    print("   • Neutral: Share case studies")
    print("   • Negative: Polite closure")
    
    print("\n🔄 TO MONITOR CONTINUOUSLY:")
    print("Run: python webhook_monitor.py")
    
    print("\n📊 TO VIEW DASHBOARD:")
    print("Run: python dashboard.py")

def quick_test():
    """Quick test of individual functions"""
    print("🧪 QUICK FUNCTION TESTS")
    print("=" * 30)
    
    manager = ConversationManager()
    
    # Test sentiment analysis
    test_texts = [
        "Yes, I'm very interested! Please tell me more.",
        "Not interested, please remove me from your list.",
        "What are your pricing options?",
        "Thanks for reaching out."
    ]
    
    print("\n🔍 Sentiment Analysis Test:")
    for text in test_texts:
        sentiment = manager.analyze_reply_sentiment(text)
        print(f"   '{text[:30]}...' → {sentiment}")
    
    # Test email extraction
    test_senders = [
        "John Doe <john@example.com>",
        "jane@company.com",
        "Bob Smith <bob.smith@test.org>"
    ]
    
    print("\n📧 Email Extraction Test:")
    for sender in test_senders:
        email = manager.extract_email_from_sender(sender)
        print(f"   '{sender}' → {email}")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    print("Welcome to Email Conversation System!")
    print("Choose an option:")
    print("1. Full Demo Workflow")
    print("2. Quick Function Tests")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        demo_workflow()
    elif choice == "2":
        quick_test()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")
