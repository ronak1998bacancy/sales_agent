import time
import schedule
from conversation_manager import ConversationManager

class EmailWebhookMonitor:
    def __init__(self, check_interval_minutes=5):
        self.manager = ConversationManager()
        self.check_interval = check_interval_minutes
        
    def monitor_replies(self):
        """Monitor for new replies and respond automatically"""
        print(f"🔍 Checking for new replies at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            self.manager.check_for_replies()
            print("✅ Check completed")
        except Exception as e:
            print(f"❌ Error during check: {e}")
    
    def start_monitoring(self):
        """Start continuous monitoring"""
        print(f"🚀 Starting email webhook monitor...")
        print(f"📧 Checking for replies every {self.check_interval} minutes")
        print("Press Ctrl+C to stop monitoring")
        
        # Schedule the monitoring function
        schedule.every(self.check_interval).minutes.do(self.monitor_replies)
        
        # Run initial check
        self.monitor_replies()
        
        # Keep running
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")

if __name__ == "__main__":
    monitor = EmailWebhookMonitor(check_interval_minutes=2)  # Check every 2 minutes
    monitor.start_monitoring()
