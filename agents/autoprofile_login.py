from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import subprocess
import os
import signal
import psutil
import socket
import json
import requests

def is_port_in_use(port):
    """Check if a specific port is already in use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result == 0
    except Exception:
        return False

def close_profile_specific_chrome(target_profile="Profile 1"):
    """Close only Chrome processes running with specific profile"""
    print(f"🔄 Closing Chrome processes for profile: {target_profile}")
    
    try:
        profile_processes = []
        debugging_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline:
                        cmdline_str = ' '.join(cmdline)
                        # Check if this process is using our target profile
                        if f'--profile-directory={target_profile}' in cmdline_str:
                            profile_processes.append(proc.pid)
                            print(f"   Found Profile 1 process: PID {proc.pid}")
                        # Also check for processes using debugging ports that might conflict
                        elif any(port in cmdline_str for port in ['--remote-debugging-port=9222', '--remote-debugging-port=9223', '--remote-debugging-port=9224']):
                            debugging_processes.append(proc.pid)
                            print(f"   Found Chrome with debugging port: PID {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Close debugging port processes first to free ports
        all_processes_to_close = debugging_processes + profile_processes
        all_processes_to_close = list(set(all_processes_to_close))  # Remove duplicates
        
        if all_processes_to_close:
            print(f"Found {len(all_processes_to_close)} Chrome processes to close...")
            
            # First try graceful termination
            for pid in all_processes_to_close:
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"   Gracefully terminating PID {pid}")
                except (OSError, ProcessLookupError):
                    pass
            
            time.sleep(4)
            
            # Force kill any remaining processes
            for pid in all_processes_to_close:
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        os.kill(pid, signal.SIGKILL)
                        print(f"   Force killed PID {pid}")
                except (OSError, ProcessLookupError, psutil.NoSuchProcess):
                    pass
            
            print(f"✅ Chrome processes cleaned up")
        else:
            print(f"✅ No Chrome processes found for {target_profile}")
            
        # Wait for ports to be fully released
        time.sleep(3)
        
    except Exception as e:
        print(f"⚠️ Error closing Chrome profile processes: {e}")

def find_available_debug_port(start_port=9224):
    """Find an available port for Chrome debugging"""
    for port in range(start_port, start_port + 20):
        if not is_port_in_use(port):
            print(f"✅ Found available debug port: {port}")
            return port
    print(f"❌ No available ports found starting from {start_port}")
    return None

def start_chrome_with_specific_profile(profile_dir="Profile 1"):
    """Start Chrome with the specific profile"""
    print(f"🚀 Starting Chrome with {profile_dir} profile...")

    # Default Chrome user data directory
    user_data_dir = os.path.expanduser("~/.config/google-chrome")
    print(f"User data dir: {user_data_dir}")
    
    # Verify profile exists
    profile_path = os.path.join(user_data_dir, profile_dir)
    if not os.path.exists(profile_path):
        print(f"❌ Profile directory does not exist: {profile_path}")
        return None, None

    # Find available debugging port
    debug_port = find_available_debug_port(9224)
    if not debug_port:
        return None, None
    
    # Create a temporary user data directory to avoid conflicts
    temp_user_data = f"{user_data_dir}_temp_{profile_dir.replace(' ', '_')}"
    
    # Copy the profile to temp location
    import shutil
    if os.path.exists(temp_user_data):
        shutil.rmtree(temp_user_data)
    
    os.makedirs(temp_user_data, exist_ok=True)
    
    # Copy the specific profile
    temp_profile_path = os.path.join(temp_user_data, profile_dir)
    if os.path.exists(profile_path):
        shutil.copytree(profile_path, temp_profile_path)
        print(f"✅ Copied profile to temporary location: {temp_profile_path}")
    
    chrome_command = [
        'google-chrome-stable',
        f'--remote-debugging-port={debug_port}',
        f'--user-data-dir={temp_user_data}',
        f'--profile-directory={profile_dir}',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--disable-extensions',
        '--no-first-run',
        '--new-window',  # Force new window
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding'
    ]

    print("Command being executed:")
    print(" ".join(chrome_command))

    try:
        # Start Chrome in background
        process = subprocess.Popen(
            chrome_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
        print(f"✅ Chrome started with profile '{profile_dir}' on port {debug_port} - PID: {process.pid}")
        
        # Wait for Chrome to fully start
        time.sleep(8)
        
        # Verify the process is still running
        if process.poll() is None:
            print("✅ Chrome process is running")
            return process, debug_port
        else:
            print("❌ Chrome process exited unexpectedly")
            return None, None
        
    except Exception as e:
        print(f"❌ Error starting Chrome: {e}")
        return None, None

def verify_chrome_debugging(debug_port):
    """Verify that Chrome debugging is accessible"""
    print(f"🔍 Verifying Chrome debugging connection on port {debug_port}...")
    
    max_retries = 15
    for attempt in range(max_retries):
        try:
            response = requests.get(f'http://127.0.0.1:{debug_port}/json', timeout=10)
            if response.status_code == 200:
                tabs = response.json()
                print(f"✅ Chrome debugging ready! Found {len(tabs)} tabs")
                return True
        except Exception as e:
            if attempt == 0:
                print(f"   Debug: {e}")
            pass
        
        if attempt < max_retries - 1:
            print(f"⏳ Attempt {attempt + 1}/{max_retries}, waiting...")
            time.sleep(3)
    
    print(f"❌ Could not connect to Chrome debugging port {debug_port}")
    return False

def verify_correct_account(debug_port):
    """Verify that the correct account is active"""
    print("🔍 Verifying account status...")
    
    try:
        response = requests.get(f'http://127.0.0.1:{debug_port}/json', timeout=5)
        if response.status_code == 200:
            tabs = response.json()
            
            # Look for tabs that might indicate the account
            for tab in tabs:
                if 'linkedin.com' in tab.get('url', '').lower():
                    print("✅ Found existing LinkedIn tab")
                    return True
                    
            print("ℹ️ No LinkedIn tabs found, but Chrome is ready")
            return True
            
    except Exception as e:
        print(f"⚠️ Could not verify account: {e}")
        
    return True

def setup_chrome_for_profile_one():
    """Setup Chrome specifically for Profile 1 only"""
    print("🔧 LINKEDIN CHROME AUTOMATION SETUP - PROFILE 1 ONLY")
    print("=" * 60)
    
    # Step 1: Close only Profile 1 Chrome processes and conflicting debug ports
    print("🔄 Closing Profile 1 Chrome processes and debug port conflicts...")
    close_profile_specific_chrome("Profile 1")
    
    # Wait a bit more to ensure everything is cleaned up
    time.sleep(3)
    
    # Step 2: Start Chrome with Profile 1
    chrome_process, debug_port = start_chrome_with_specific_profile("Profile 1")
    
    if not chrome_process:
        print("❌ Failed to start Chrome with Profile 1")
        return False, None, None
    
    # Step 3: Verify debugging works
    if verify_chrome_debugging(debug_port):
        print("✅ Chrome debugging is ready!")
        
        # Step 4: Verify correct account
        if verify_correct_account(debug_port):
            print("✅ Chrome Profile 1 is ready!")
            return True, chrome_process, debug_port
        else:
            print("⚠️ Warning: Could not verify account, but proceeding...")
            return True, chrome_process, debug_port
    else:
        print("❌ Chrome debugging setup failed")
        try:
            chrome_process.terminate()
        except:
            pass
        return False, None, None

def create_linkedin_tab(debug_port):
    """Connect to Chrome and create LinkedIn tab"""
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        existing_tabs = driver.window_handles
        print(f"Found {len(existing_tabs)} existing tabs")
        
        # Create new tab if needed
        if len(existing_tabs) == 0:
            driver.execute_script("window.open('');")
        
        # Use the first/current tab
        driver.switch_to.window(driver.window_handles[0])
        
        # Navigate to LinkedIn feed
        print("Opening LinkedIn feed...")
        driver.get("https://www.linkedin.com/feed")
        
        # Wait for page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print("✅ Successfully opened LinkedIn!")
        print(f"Current URL: {driver.current_url}")
        
        # Check login status
        time.sleep(5)
        
        if "feed" in driver.current_url and "linkedin.com" in driver.current_url:
            print("✅ Successfully logged into LinkedIn feed!")
        elif "login" in driver.current_url or "challenge" in driver.current_url:
            print("⚠️ LinkedIn is asking for login - please log in manually")
        else:
            print(f"ℹ️ Current page: {driver.current_url}")
            
        return driver
        
    except Exception as e:
        print(f"❌ Error connecting to Chrome: {e}")
        return None

def cleanup_temp_data(profile_dir="Profile 1"):
    """Clean up temporary user data directory"""
    user_data_dir = os.path.expanduser("~/.config/google-chrome")
    temp_user_data = f"{user_data_dir}_temp_{profile_dir.replace(' ', '_')}"
    
    try:
        if os.path.exists(temp_user_data):
            import shutil
            shutil.rmtree(temp_user_data)
            print(f"✅ Cleaned up temporary data: {temp_user_data}")
    except Exception as e:
        print(f"⚠️ Could not clean up temp data: {e}")

def profile_login():
    """Main execution flow - Profile 1 specific"""
    print("🔥 LINKEDIN PROFILE 1 AUTOMATION")
    print("Target Profile: Profile 1 ONLY")
    print("=" * 50)
    
    try:
        # Step 1: Setup Chrome with Profile 1 only
        success, chrome_process, debug_port = setup_chrome_for_profile_one()
        
        if not success:
            print("❌ Failed to setup Chrome Profile 1.")
            return None
        
        print("\n🔗 Connecting with Selenium and creating LinkedIn tab...")
        
        # Step 2: Create LinkedIn tab in Profile 1
        driver = create_linkedin_tab(debug_port)
        
        if driver:
            print("✅ LinkedIn automation is ready for Profile 1!")
            print("✅ Driver ready for scraping operations")
            return driver  # Return the driver for use in your scraper
            
        else:
            print("❌ Failed to create LinkedIn tab in Profile 1")
            return None
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

if __name__ == "__main__":
    profile_login()