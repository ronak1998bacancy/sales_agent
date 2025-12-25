import json
import os
from datetime import datetime
from conversation_manager import ConversationManager

class ConversationDashboard:
    def __init__(self):
        self.manager = ConversationManager()
        
    def display_dashboard(self):
        """Display conversation dashboard"""
        conversations = self.manager.load_conversation_data()
        
        if not conversations:
            print("📭 No conversations found")
            return
        
        print("=" * 80)
        print("📊 CONVERSATION DASHBOARD")
        print("=" * 80)
        
        total_conversations = len(conversations)
        active_conversations = len([c for c in conversations.values() if c['status'] == 'waiting_for_reply'])
        completed_conversations = len([c for c in conversations.values() if c['status'] == 'completed'])
        ended_conversations = len([c for c in conversations.values() if c['status'] == 'ended_negative'])
        
        print(f"📈 Total Conversations: {total_conversations}")
        print(f"🔄 Active (Waiting for Reply): {active_conversations}")
        print(f"✅ Completed: {completed_conversations}")
        print(f"❌ Ended (Negative): {ended_conversations}")
        print("-" * 80)
        
        for email, conv in conversations.items():
            status_emoji = {
                'waiting_for_reply': '⏳',
                'completed': '✅',
                'ended_negative': '❌'
            }.get(conv['status'], '❓')
            
            print(f"\n{status_emoji} {email}")
            print(f"   Name: {conv.get('recipient_name', 'Unknown')}")
            print(f"   Cycle: {conv['cycle_count']}/{self.manager.max_cycles}")
            print(f"   Status: {conv['status']}")
            print(f"   Last Contact: {conv['last_sent_time'][:19]}")
            print(f"   Messages: {len(conv['conversation_history'])}")
            
            # Show recent activity
            if conv['conversation_history']:
                last_message = conv['conversation_history'][-1]
                print(f"   Last: {last_message['type'].title()} - {last_message['timestamp'][:19]}")
        
        print("=" * 80)
    
    def display_conversation_details(self, email):
        """Display detailed conversation history for a specific email"""
        conversations = self.manager.load_conversation_data()
        
        if email not in conversations:
            print(f"❌ No conversation found for {email}")
            return
        
        conv = conversations[email]
        print("=" * 80)
        print(f"📧 CONVERSATION DETAILS: {email}")
        print("=" * 80)
        print(f"Name: {conv.get('recipient_name', 'Unknown')}")
        print(f"Status: {conv['status']}")
        print(f"Cycle: {conv['cycle_count']}/{self.manager.max_cycles}")
        print("-" * 80)
        
        for i, msg in enumerate(conv['conversation_history'], 1):
            msg_type = "📤 SENT" if msg['type'] == 'sent' else "📥 RECEIVED"
            print(f"\n{i}. {msg_type} - {msg['timestamp'][:19]}")
            print(f"   Subject: {msg['subject']}")
            if msg['type'] == 'received' and 'sentiment' in msg:
                print(f"   Sentiment: {msg['sentiment']}")
            print(f"   Body: {msg['body'][:200]}...")
            print("-" * 40)
        
        print("=" * 80)

def main():
    dashboard = ConversationDashboard()
    
    while True:
        print("\n📊 CONVERSATION DASHBOARD MENU")
        print("1. View All Conversations")
        print("2. View Specific Conversation")
        print("3. Start New Conversation")
        print("4. Check for Replies")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == "1":
            dashboard.display_dashboard()
            
        elif choice == "2":
            email = input("Enter email address: ").strip()
            dashboard.display_conversation_details(email)
            
        elif choice == "3":
            email = input("Enter prospect email: ").strip()
            name = input("Enter prospect name (optional): ").strip()
            from conversation_manager import start_conversation_with_prospect
            start_conversation_with_prospect(email, name)
            
        elif choice == "4":
            print("Checking for replies...")
            from conversation_manager import check_and_respond_to_replies
            check_and_respond_to_replies()
            
        elif choice == "5":
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
