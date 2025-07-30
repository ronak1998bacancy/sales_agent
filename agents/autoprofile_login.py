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
            s.settimeout(0.5)  # Reduced timeout for faster port checking
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
                except (OSError, ProcessLookupError):
                    pass
            
            time.sleep(1.5)  # Reduced from 4 seconds
            
            # Force kill any remaining processes
            for pid in all_processes_to_close:
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        os.kill(pid, signal.SIGKILL)
                except (OSError, ProcessLookupError, psutil.NoSuchProcess):
                    pass
            
            print(f"✅ Chrome processes cleaned up")
        else:
            print(f"✅ No Chrome processes found for {target_profile}")
            
        # Reduced wait time for ports to be released
        time.sleep(1)
        
    except Exception as e:
        print(f"⚠️ Error closing Chrome profile processes: {e}")

def find_available_debug_port(start_port=9224):
    """Find an available port for Chrome debugging"""
    for port in range(start_port, start_port + 10):  # Reduced range for faster checking
        if not is_port_in_use(port):
            print(f"✅ Found available debug port: {port}")
            return port
    print(f"❌ No available ports found starting from {start_port}")
    return None

def start_chrome_with_specific_profile(profile_dir="Profile 1"):
    """Start Chrome with the specific profile - OPTIMIZED FOR SPEED"""
    print(f"🚀 Starting Chrome with {profile_dir} profile...")

    # Default Chrome user data directory
    # user_data_dir = os.path.expanduser("~/.config/google-chrome")
    if os.name == "nt":
        user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    else:
        user_data_dir = os.path.expanduser("~/.config/google-chrome")
    
    # Verify profile exists
    profile_path = os.path.join(user_data_dir, profile_dir)
    if not os.path.exists(profile_path):
        print(f"❌ Profile directory does not exist: {profile_path}")
        return None, None

    # Find available debugging port
    debug_port = find_available_debug_port(9224)
    if not debug_port:
        return None, None
    
    # Create a lightweight temporary user data directory
    temp_user_data = f"{user_data_dir}_temp_{profile_dir.replace(' ', '_')}"
    
    # Quick copy of essential profile data only
    import shutil
    if os.path.exists(temp_user_data):
        shutil.rmtree(temp_user_data)
    
    os.makedirs(temp_user_data, exist_ok=True)
    
    # Copy only essential files for faster startup
    temp_profile_path = os.path.join(temp_user_data, profile_dir)
    os.makedirs(temp_profile_path, exist_ok=True)
    
    # Copy only critical files for authentication
    essential_files = ['Preferences', 'Local State', 'Cookies', 'Login Data', 'Web Data']
    for file_name in essential_files:
        src_file = os.path.join(profile_path, file_name)
        dst_file = os.path.join(temp_profile_path, file_name)
        if os.path.exists(src_file):
            try:
                if os.path.isfile(src_file):
                    shutil.copy2(src_file, dst_file)
                else:
                    shutil.copytree(src_file, dst_file)
            except Exception as e:
                print(f"   Warning: Could not copy {file_name}: {e}")
    
    print(f"✅ Copied essential profile files to temporary location")
    
    # Get the appropriate Chrome executable based on OS
    if os.name == "nt":
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
        ]
        chrome_exe = next((path for path in chrome_paths if os.path.exists(path)), None)
        if not chrome_exe:
            print("❌ Chrome executable not found in common locations")
            return None, None
    else:
        chrome_exe = 'google-chrome-stable'
    
    # Optimized Chrome flags for speed
    chrome_command = [
        chrome_exe,
        f'--remote-debugging-port={debug_port}',
        f'--user-data-dir={temp_user_data}',
        f'--profile-directory={profile_dir}',
        # '--headless=new',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--disable-extensions',
        '--no-first-run',
        '--new-window',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-background-networking',
        '--disable-background-sync',
        '--disable-client-side-phishing-detection',
        '--disable-default-apps',
        '--disable-hang-monitor',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-sync',
        '--disable-translate',
        '--disable-plugins-discovery',
        '--disable-preconnect',
        '--no-default-browser-check',
        '--no-pings',
        '--aggressive-cache-discard',  # For faster loading
        '--memory-pressure-off',
        '--fast-start'  # Enable fast startup
    ]

    try:
        # Start Chrome in background with OS-specific process group handling
        if os.name == "nt":
            # Windows: use creationflags
            process = subprocess.Popen(
                chrome_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Linux/macOS: use preexec_fn
            process = subprocess.Popen(
                chrome_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
        print(f"✅ Chrome started with profile '{profile_dir}' on port {debug_port} - PID: {process.pid}")
        # Reduced wait time for Chrome to start
        time.sleep(3)  # Reduced from 8 seconds
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
    """Verify that Chrome debugging is accessible - FASTER VERSION"""
    print(f"🔍 Verifying Chrome debugging connection on port {debug_port}...")
    
    max_retries = 8  # Reduced from 15
    for attempt in range(max_retries):
        try:
            response = requests.get(f'http://127.0.0.1:{debug_port}/json', timeout=3)  # Reduced timeout
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
            time.sleep(1.5)  # Reduced wait time
    
    print(f"❌ Could not connect to Chrome debugging port {debug_port}")
    return False

def setup_chrome_for_profile_one():
    """Setup Chrome specifically for Profile 1 - SPEED OPTIMIZED"""
    print("🔧 LINKEDIN CHROME AUTOMATION SETUP - PROFILE 1 ONLY")
    print("=" * 60)
    
    # Step 1: Close only Profile 1 Chrome processes and conflicting debug ports
    close_profile_specific_chrome("Profile 1")
    
    # Step 2: Start Chrome with Profile 1
    chrome_process, debug_port = start_chrome_with_specific_profile("Profile 1")
    
    if not chrome_process:
        print("❌ Failed to start Chrome with Profile 1")
        return False, None, None
    
    # Step 3: Verify debugging works
    if verify_chrome_debugging(debug_port):
        print("✅ Chrome debugging is ready!")
        return True, chrome_process, debug_port
    else:
        print("❌ Chrome debugging setup failed")
        try:
            chrome_process.terminate()
        except:
            pass
        return False, None, None

def create_linkedin_tab_fast(debug_port):
    """Connect to Chrome and create LinkedIn tab - FIXED VERSION"""
    print("🔗 Connecting to Chrome and opening LinkedIn...")
    
    # Less aggressive Chrome options
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
    
    # Keep only essential optimizations that don't break navigation
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-images")  # Keep this for speed
    chrome_options.add_argument("--disable-plugins")
    # Remove CSS and JavaScript disabling - they can break navigation
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        # Increase page load timeout and use different strategy
        driver.set_page_load_timeout(30)  # Increased timeout
        
        existing_tabs = driver.window_handles
        print(f"Found {len(existing_tabs)} existing tabs")
        
        # Use existing tab or create new one
        if len(existing_tabs) == 0:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[0])
        else:
            driver.switch_to.window(existing_tabs[0])
        
        # Try multiple navigation approaches
        print("🚀 Opening LinkedIn feed...")
        start_time = time.time()
        
        # Method 1: Direct navigation
        try:
            driver.get("https://www.linkedin.com/feed")
            print("✅ Direct navigation successful")
        except Exception as e:
            print(f"⚠️ Direct navigation failed: {e}")
            
            # Method 2: JavaScript navigation
            try:
                print("🔄 Trying JavaScript navigation...")
                driver.execute_script("window.location.href = 'https://www.linkedin.com/feed';")
                time.sleep(5)  # Wait for navigation
            except Exception as e2:
                print(f"⚠️ JavaScript navigation failed: {e2}")
                
                # Method 3: Step-by-step navigation
                print("🔄 Trying step-by-step navigation...")
                driver.get("https://www.linkedin.com")
                time.sleep(3)
                driver.get("https://www.linkedin.com/feed")
        
        # Wait for page to load properly
        try:
            # Wait for LinkedIn-specific elements
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test-id='feed-container']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".feed-container")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".application-outlet")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".authentication-outlet")),
                    EC.url_contains("linkedin.com")
                )
            )
            print("✅ LinkedIn page elements detected")
        except Exception as e:
            print(f"⚠️ Couldn't detect LinkedIn elements: {e}")
        
        load_time = time.time() - start_time
        current_url = driver.current_url
        print(f"✅ Page loaded in {load_time:.2f} seconds!")
        print(f"Current URL: {current_url}")
        
        # Better URL checking
        if "linkedin.com" in current_url.lower():
            if "feed" in current_url.lower():
                print("✅ Successfully accessed LinkedIn feed!")
            elif "login" in current_url.lower() or "challenge" in current_url.lower():
                print("⚠️ LinkedIn requires login - please login manually")
                print("   The page is ready for manual login")
            else:
                print(f"✅ On LinkedIn: {current_url}")
        else:
            print(f"❌ Navigation failed - still on: {current_url}")
            print("🔄 Attempting one more navigation...")
            try:
                driver.execute_script("window.location.replace('https://www.linkedin.com/feed');")
                time.sleep(5)
                print(f"Final URL: {driver.current_url}")
            except Exception as e:
                print(f"Final attempt failed: {e}")
        
        return driver
        
    except Exception as e:
        print(f"❌ Error connecting to Chrome: {e}")
        return None
    
def cleanup_temp_data(profile_dir="Profile 1"):
    """Clean up temporary user data directory"""
    if os.name == "nt":
        user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    else:
        user_data_dir = os.path.expanduser("~/.config/google-chrome")
    temp_user_data = f"{user_data_dir}_temp_{profile_dir.replace(' ', '_')}"
    
    try:
        if os.path.exists(temp_user_data):
            import shutil
            shutil.rmtree(temp_user_data)
            print(f"✅ Cleaned up temporary data")
    except Exception as e:
        print(f"⚠️ Could not clean up temp data: {e}")

def get_chrome_profiles():
    """Get all Chrome profiles and their associated email addresses"""
    # user_data_dir = os.path.expanduser("~/.config/google-chrome")
    if os.name == "nt":
        user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    else:
        user_data_dir = os.path.expanduser("~/.config/google-chrome")
    local_state_path = os.path.join(user_data_dir, "Local State")
    
    profiles = {}
    
    try:
        if os.path.exists(local_state_path):
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.load(f)
            
            profile_info = local_state.get('profile', {}).get('info_cache', {})
            
            for profile_id, profile_data in profile_info.items():
                profile_name = profile_data.get('name', 'Unknown')
                
                # Try to get email from preferences
                pref_file = os.path.join(user_data_dir, profile_id, "Preferences")
                email = "No email found"
                
                if os.path.exists(pref_file):
                    try:
                        with open(pref_file, 'r', encoding='utf-8') as f:
                            prefs = json.load(f)
                        
                        # Try multiple paths to find email
                        account_info = prefs.get('account_info', [])
                        if account_info:
                            email = account_info[0].get('email', 'No email')
                        else:
                            # Try other locations
                            signin_info = prefs.get('signin', {})
                            if signin_info:
                                email = signin_info.get('AllowedUsername', 'No email')
                    except:
                        pass
                
                profiles[profile_id] = {
                    'name': profile_name,
                    'email': email,
                    'path': os.path.join(user_data_dir, profile_id)
                }
    
    except Exception as e:
        print(f"Error reading Chrome profiles: {e}")
    
    return profiles

def find_profile_by_email(email):
    """Find Chrome profile directory by email address"""
    print(f"🔍 Searching for profile with email: {email}")
    
    profiles = get_chrome_profiles()
    
    print("\n📋 Available Chrome Profiles:")
    print("-" * 50)
    for profile_id, info in profiles.items():
        print(f"Profile: {profile_id}")
        print(f"  Name: {info['name']}")
        print(f"  Email: {info['email']}")
        print(f"  Path: {info['path']}")
        print()
    
    # Search for matching email
    for profile_id, info in profiles.items():
        if email.lower() in info['email'].lower():
            print(f"✅ Found matching profile!")
            print(f"   Profile ID: {profile_id}")
            print(f"   Name: {info['name']}")
            print(f"   Email: {info['email']}")
            return profile_id
    
    print(f"❌ No profile found with email: {email}")
    print("Available emails:")
    for profile_id, info in profiles.items():
        if info['email'] != "No email found":
            print(f"  - {info['email']}")
    
    return None

# MODIFY THESE EXISTING FUNCTIONS

def start_chrome_with_email_profile(email):
    """Start Chrome with profile found by email - MODIFIED VERSION"""
    profile_id = find_profile_by_email(email)
    
    if not profile_id:
        return None, None
    
    print(f"🚀 Starting Chrome with profile for: {email}")
    
    # Use the existing function but with dynamic profile
    return start_chrome_with_specific_profile(profile_id)

def setup_chrome_for_email(email):
    """Setup Chrome for specific email - MODIFIED VERSION"""
    print(f"🔧 LINKEDIN CHROME AUTOMATION SETUP - EMAIL: {email}")
    print("=" * 60)
    
    # Find profile by email
    profile_id = find_profile_by_email(email)
    if not profile_id:
        return False, None, None
    
    # Step 1: Close specific profile Chrome processes
    close_profile_specific_chrome(profile_id)
    
    # Step 2: Start Chrome with found profile
    chrome_process, debug_port = start_chrome_with_specific_profile(profile_id)
    
    if not chrome_process:
        print(f"❌ Failed to start Chrome with profile for {email}")
        return False, None, None
    
    # Step 3: Verify debugging works
    if verify_chrome_debugging(debug_port):
        print("✅ Chrome debugging is ready!")
        return True, chrome_process, debug_port
    else:
        print("❌ Chrome debugging setup failed")
        try:
            chrome_process.terminate()
        except:
            pass
        return False, None, None

# MODIFY THE MAIN FUNCTION
def profile_login_with_email(email):
    """Main execution flow - Email-based profile selection"""
    print("🔥 DYNAMIC LINKEDIN AUTOMATION")
    print(f"Target Email: {email}")
    print("=" * 50)
    
    total_start_time = time.time()
    
    try:
        # Step 1: Setup Chrome with email-based profile
        success, chrome_process, debug_port = setup_chrome_for_email(email)
        
        if not success:
            print(f"❌ Failed to setup Chrome for email: {email}")
            return None, None
        
        # Step 2: Create LinkedIn tab
        driver = create_linkedin_tab_fast(debug_port)
        
        if driver:
            total_time = time.time() - total_start_time
            print(f"✅ LinkedIn automation ready in {total_time:.2f} seconds!")
            print(f"✅ Driver ready for {email}'s profile")
            return driver, chrome_process
            
        else:
            print(f"❌ Failed to create LinkedIn tab for {email}")
            return None, None
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None, None

if __name__ == "__main__":
    # OLD CODE:
    # driver = profile_login()
    
    # NEW CODE:
    email = input("Enter email address: ").strip()
    
    if not email:
        print("❌ No email provided!")
        exit(1)
    
    driver = profile_login_with_email(email)
    if driver:
        print(f"Driver ready for {email}'s profile!")
        # Your scraping code can use the driver here
    else:
        print("Failed to setup driver")