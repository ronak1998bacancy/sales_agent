import time
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from dotenv import load_dotenv
import os
import datetime
import logging
from typing import Dict, List

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LinkedInScraper:
    def __init__(self, email, password, search_query="CEO", num_profiles=1):
        self.email = email
        self.password = password
        self.search_query = search_query
        self.num_profiles = num_profiles 
        self.results = []

    def setup_driver(self):
        """Set up Chrome driver with proper configuration"""
        chrome_options = Options()
        
        # Add arguments to avoid detection and improve stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        
        # Uncomment the next line if you want to run in headless mode
        # chrome_options.add_argument("--headless=new")
        
        try:
            # Use webdriver-manager to automatically download and manage ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return driver
        except Exception as e:
            logger.debug(f"Error setting up driver: {e}")
            return None

    def safe_find_element(self, driver, by, value, timeout=10):
        """Safely find an element with timeout"""
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            return None

    def safe_find_elements(self, driver, by, value, timeout=10):
        """Safely find elements with timeout"""
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return driver.find_elements(by, value)
        except TimeoutException:
            return []

    def login_to_linkedin(self, driver):
        """Log in to LinkedIn"""
        logger.debug("Logging in to LinkedIn...")
        
        try:
            driver.get("https://www.linkedin.com/login")
            time.sleep(2)
            
            # Wait for and fill email field
            email_field = self.safe_find_element(driver, By.ID, "username")
            if not email_field:
                logger.debug("Could not find email field")
                return False
            
            email_field.clear()
            # Type email character by character to simulate human typing
            for char in self.email:
                email_field.send_keys(char)
                time.sleep(0.1)
            time.sleep(1)
            
            # Wait for and fill password field
            password_field = self.safe_find_element(driver, By.ID, "password")
            if not password_field:
                logger.debug("Could not find password field")
                return False
            
            password_field.clear()
            # Type password character by character to simulate human typing
            for char in self.password:
                password_field.send_keys(char)
                time.sleep(0.1)
            time.sleep(1)
            
            # Click login button
            login_button = self.safe_find_element(driver, By.XPATH, "//button[@type='submit']")
            if not login_button:
                logger.debug("Could not find login button")
                return False
            
            login_button.click()
            time.sleep(2)
            
            # Check if login was successful by looking for the search bar or home feed
            success_indicators = [
                (By.ID, "global-nav-typeahead"),
                (By.CSS_SELECTOR, "[data-test-id='global-nav-typeahead']"),
                (By.CSS_SELECTOR, ".global-nav__primary-link"),
                (By.CSS_SELECTOR, ".feed-container"),
                (By.CSS_SELECTOR, ".search-global-typeahead__input")
            ]
            
            for by, value in success_indicators:
                if self.safe_find_element(driver, by, value, timeout=3):
                    logger.debug("Login successful")
                    return True
            
            # Check if we're being asked for verification
            if self.safe_find_element(driver, By.CSS_SELECTOR, "[data-test-id='challenge-form']", timeout=3):
                logger.debug("LinkedIn is asking for verification. Please complete it manually and press Enter to continue...")
                input()
                return True
            
            logger.debug("Login may have failed - could not find expected elements")
            return False
            
        except Exception as e:
            logger.debug(f"Login failed: {str(e)}")
            return False

    def clean_name(self, name_text):
        """Clean extracted name by removing LinkedIn UI elements"""
        if not name_text:
            return None
        
        # Remove common LinkedIn UI patterns
        name_text = re.sub(r'View .+?\'s profile', '', name_text)
        name_text = re.sub(r'• \d+\w+\s+\d+\w+ degree connection', '', name_text)
        name_text = re.sub(r'• \d+\w+\s+degree connection', '', name_text)
        name_text = re.sub(r'\n.*', '', name_text)  # Remove everything after newline
        
        # Clean up whitespace
        name_text = ' '.join(name_text.split())
        
        return name_text.strip() if name_text.strip() else None

    def extract_member_id_from_urn(self, urn):
        """Extract member ID from URN"""
        try:
            # URN format: urn:li:member:123456789
            if "member:" in urn:
                return urn.split("member:")[-1]
            return None
        except:
            return None

    def construct_profile_url(self, member_id):
        """Construct profile URL from member ID"""
        # LinkedIn profile URLs can sometimes be constructed as:
        # https://www.linkedin.com/in/[vanity-url] or
        # https://www.linkedin.com/profile/view?id=[member-id]
        # But the direct member ID approach doesn't always work
        # We'll try a different approach
        return f"https://www.linkedin.com/profile/view?id={member_id}"

    def extract_profile_urls_from_search_results(self, driver, search_results):
        """Extract only profile URLs from search results - detailed data will be extracted from individual profiles"""
        profile_urls = []
        
        for i, result in enumerate(search_results[:self.num_profiles]):
            try:
                logger.debug(f"Processing result {i+1}...")
                
                profile_url = None
                
                # Extract profile URL
                profile_link_selectors = [
                    ".search-result__result-link",
                    "a[data-control-name='search_srp_result']",
                    ".actor-name a",
                    "h3 a",
                    ".entity-result__title-text a",
                    ".app-aware-link"
                ]
                
                for selector in profile_link_selectors:
                    try:
                        profile_link = result.find_element(By.CSS_SELECTOR, selector)
                        href = profile_link.get_attribute("href")
                        if href and "/in/" in href:
                            profile_url = href.split('?')[0]
                            logger.debug(f"Found profile URL: {profile_url}")
                            break
                    except:
                        continue
                
                # If still no URL found, try all links
                if not profile_url:
                    try:
                        links = result.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "/in/" in href and "linkedin.com" in href:
                                profile_url = href.split('?')[0]
                                logger.debug(f"Found profile URL from any link: {profile_url}")
                                break
                    except:
                        pass
                
                if profile_url:
                    profile_urls.append(profile_url)
                    logger.debug(f"Successfully extracted URL for result {i+1}")
                else:
                    logger.debug(f"Could not extract profile URL from result {i+1}")
                    
            except Exception as e:
                logger.debug(f"Error processing search result {i+1}: {str(e)}")
                continue
        
        return profile_urls

    def extract_full_profile_data(self, driver, profile_url):
        """Navigate to individual profile and extract complete data"""
        try:
            logger.debug(f"Navigating to profile: {profile_url}")
            driver.get(profile_url)
            time.sleep(2)

            profile_data = {
                "profile_url": profile_url,
                "name": None,
                "company": None,
                "role": None,
                "company_url": None,
                "company_website": None,
                "location": None,
                "source": "LinkedIn"
            }

            # Extract name from profile page
            name_selectors = [
                "h1.text-heading-xlarge",
                ".pv-text-details__left-panel h1",
                ".text-heading-xlarge",
                "h1"
            ]
            for selector in name_selectors:
                name_element = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                if name_element:
                    name_text = self.clean_name(name_element.text)
                    if name_text:
                        profile_data["name"] = name_text
                        logger.debug(f"Found name: {name_text}")
                        break

            # Scroll to load experience section
            driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(2)

            # Extract experience section
            experience_list_selectors = [ 
                "li.artdeco-list__item"
            ]

            experience_entries = []
            
            for selector in experience_list_selectors:
                entries = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=5)
                if entries:
                    # Filter for valid experience entries with company logo
                    valid_entries = [e for e in entries if e.find_elements(By.CSS_SELECTOR, "a[data-field='experience_company_logo']")]
                    if valid_entries:
                        experience_entries = valid_entries
                        logger.debug(f"Found {len(valid_entries)} experience entries with selector: {selector}")
                        break
                           
            if experience_entries:
                # Take the first (most recent) experience entry
                first_entry = experience_entries[0]
                logger.debug("Processing first experience entry...")

                # Check if this is a single company with sub-positions (based on HTML structure)
                sub_components = first_entry.find_elements(By.CSS_SELECTOR, ".pvs-entity__sub-components")
                is_single_company = bool(sub_components)

                if is_single_company:
                    # Single company with multiple positions
                    logger.debug("Detected single company with sub-positions structure")
                    
                    # Extract company name from the main entry
                    company_elements = first_entry.find_elements(By.CSS_SELECTOR, ".display-flex.align-items-center.mr1.hoverable-link-text.t-bold span[aria-hidden='true']")
                    if company_elements:
                        company_name = company_elements[0].text.strip()
                        if company_name and len(company_name) > 1:
                            profile_data["company"] = company_name
                            logger.debug(f"Found company: {company_name}")

                    # Extract company URL
                    company_links = first_entry.find_elements(By.CSS_SELECTOR, "a[data-field='experience_company_logo']")
                    if company_links:
                        company_url = company_links[0].get_attribute("href").split('?')[0]
                        if "/company/" in company_url:
                            profile_data["company_url"] = company_url
                            logger.debug(f"Found company URL: {company_url}")
                        elif "search/results/all" in company_url:
                            # Fallback: search for company to get proper company URL
                            if profile_data.get("company"):
                                logger.debug(f"Company URL is a search link, searching for company: {profile_data['company']}")
                                company_info = self.search_company_website(driver, profile_data["company"])
                                if company_info.get("company_url"):
                                    profile_data["company_url"] = company_info["company_url"]
                                    logger.debug(f"Found company URL via search: {profile_data['company_url']}")

                    # Extract position from sub-components (first position is most recent)
                    # breakpoint()
                    sub_position_elements = first_entry.find_elements(By.CSS_SELECTOR, ".display-flex.align-items-center.mr1.t-bold span[aria-hidden='true']")
                    if sub_position_elements:
                        position = sub_position_elements[0].text.strip()
                        if position and len(position) > 1:
                            profile_data["role"] = position
                            logger.debug(f"Found position: {position}")
                else:
                    # Multiple companies, take the first (most recent)
                    logger.debug("Detected multiple companies structure")
                    
                    # Extract position from the main entry
                    position_elements = first_entry.find_elements(By.CSS_SELECTOR, ".display-flex.align-items-center.mr1.t-bold span[aria-hidden='true']")
                    if position_elements:
                        position = position_elements[0].text.strip()
                        if position and len(position) > 1:
                            profile_data["role"] = position
                            logger.debug(f"Found position: {position}")

                    # Extract company name
                    company_name_elements = first_entry.find_elements(By.CSS_SELECTOR, ".t-14.t-normal span[aria-hidden='true']")
                    for element in company_name_elements:
                        text = element.text.strip()
                        # if text and "·" in text and ("Full-time" in text or "Part-time" in text or "Contract" in text):
                        company_name = text.split("·")[0].strip()
                        if company_name and len(company_name) > 1 and company_name != "Present":
                            profile_data["company"] = company_name
                            logger.debug(f"Found company: {company_name}")
                            break

                    # Extract company URL
                    company_links = first_entry.find_elements(By.CSS_SELECTOR, "a[data-field='experience_company_logo']")
                    if company_links:
                        company_url = company_links[0].get_attribute("href").split('?')[0]
                        if "/company/" in company_url:
                            profile_data["company_url"] = company_url
                            logger.debug(f"Found company URL: {company_url}")
                        elif "search/results/all" in company_url:
                            # Fallback: search for company to get proper company URL
                            if profile_data.get("company"):
                                logger.debug(f"Company URL is a search link, searching for company: {profile_data['company']}")
                                company_info = self.search_company_website(driver, profile_data["company"])
                                if company_info.get("company_url"):
                                    profile_data["company_url"] = company_info["company_url"]
                                    logger.debug(f"Found company URL via search: {profile_data['company_url']}")

            # Extract location
            location_selectors = [
                ".text-body-small.inline.t-black--light.break-words",
                ".pv-text-details__left-panel .text-body-small",
                ".text-body-small"
            ]
            for selector in location_selectors:
                location_element = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=3)
                if location_element:
                    location_text = location_element.text.strip()
                    if location_text and "connection" not in location_text.lower() and len(location_text) < 100:
                        profile_data["location"] = location_text
                        logger.debug(f"Found location: {location_text}")
                        break

            # Extract company website if company_url exists
            if profile_data.get("company_url"):
                logger.debug(f"Navigating to company page: {profile_data['company_url']}")
                driver.get(profile_data["company_url"])
                time.sleep(2)
                website_info = self.extract_company_website(driver)
                if website_info.get("company_website"):
                    profile_data["company_website"] = website_info["company_website"]
                    logger.debug(f"Found company website: {profile_data['company_website']}")

            return profile_data

        except Exception as e:
            logger.debug(f"Error extracting profile data: {e}")
            return {"profile_url": profile_url}

    def get_company_website_from_profile(self, driver, profile_data):
        """Navigate to profile and extract company website"""
        profile_url = profile_data.get('profile_url')
        company = profile_data.get('company')
        
        if not profile_url:
            logger.debug(f"No profile URL available for {profile_data.get('name', 'Unknown')}")
            if company:
                logger.debug(f"Trying to search for company: {company}")
                # Try to search for company directly
                return self.search_company_website(driver, company)
            return {}
        
        try:
            logger.debug(f"Navigating to profile: {profile_url}")
            driver.get(profile_url)
            time.sleep(2)
            
            company_info = {}
            
            # Try to find company link in experience section
            try:
                # Look for experience section with multiple selectors
                experience_selectors = [
                    "#experience",
                    ".experience-section",
                    "[data-section='experience']",
                    ".pv-profile-section__card-header h2:contains('Experience')"
                ]
                
                experience_section = None
                for selector in experience_selectors:
                    experience_section = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                    if experience_section:
                        break
                
                if experience_section:
                    # Find company links
                    company_link_selectors = [
                        "a[href*='/company/']",
                        ".pv-entity__secondary-title a",
                        ".experience-item__company a"
                    ]
                    
                    company_links = []
                    for selector in company_link_selectors:
                        try:
                            links = experience_section.find_elements(By.CSS_SELECTOR, selector)
                            company_links.extend(links)
                        except:
                            continue
                    
                    if company_links:
                        company_url = company_links[0].get_attribute("href").split('?')[0]
                        company_info["company_url"] = company_url
                        logger.debug(f"Found company URL: {company_url}")
                        
                        # Navigate to company page
                        driver.get(company_url)
                        time.sleep(2)
                        
                        # Extract company website
                        website_info = self.extract_company_website(driver)
                        company_info.update(website_info)
                            
            except Exception as e:
                logger.debug(f"Error navigating to company page: {e}")
                
            return company_info
            
        except Exception as e:
            logger.debug(f"Error getting company info from profile: {e}")
            return {}

    def extract_company_website(self, driver):
        """Extract company website from company page"""
        try:
            logger.debug("Looking for company website...")
            
            # Wait for page to load
            time.sleep(2)
            
            # Try to find and click About section first
            logger.debug("Looking for About section...")
            about_selectors = [
                "a[href*='/about/']",
                ".org-page-navigation__item-anchor[href*='about']",
                "a.org-page-navigation__item-anchor[href*='about']"
            ]
            
            about_clicked = False
            for selector in about_selectors:
                try:
                    about_link = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                    if about_link:
                        logger.debug("Found About section, clicking...")
                        about_link.click()
                        time.sleep(4)
                        about_clicked = True
                        break
                except Exception as e:
                    continue
            
            if not about_clicked:
                logger.debug("Could not find About section, looking for website on main page...")
            
            # Look for website in About section or main page
            website_selectors = [
                # Website link in About section based on the HTML you provided
                ".org-about-module__margin-bottom a[href*='http']:not([href*='linkedin.com'])",
                "dd.mb4.t-black--light.text-body-medium a[href*='http']:not([href*='linkedin.com'])",
                ".link-without-visited-state[href*='http']:not([href*='linkedin.com'])",
                
                # General website selectors
                ".org-about-company-module a[href*='http']:not([href*='linkedin.com'])",
                ".org-top-card-summary-info-list__info-item a[href*='http']:not([href*='linkedin.com'])",
                "a[href*='www.']:not([href*='linkedin.com'])",
                "a[href*='http']:not([href*='linkedin.com']):not([href*='mailto']):not([href*='tel'])",
                
                # Fallback selectors
                ".company-page-details__website a",
                ".basic-info-about-company a[href*='http']"
            ]
            
            for selector in website_selectors:
                try:
                    website_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in website_elements:
                        href = element.get_attribute("href")
                        if href and self.is_valid_website_url(href):
                            logger.debug(f"Found company website: {href}")
                            return {"company_website": href}
                except Exception as e:
                    continue
            
            logger.debug("No company website found")
            return {}
            
        except Exception as e:
            logger.debug(f"Error extracting company website: {e}")
            return {}

    def is_valid_website_url(self, url):
        """Check if URL is a valid website URL"""
        if not url:
            return False
        
        # Convert to lowercase for checking
        url_lower = url.lower()
        
        # Exclude LinkedIn and other social media URLs
        excluded_domains = [
            'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
            'youtube.com', 'mailto:', 'tel:', 'javascript:', '#'
        ]
        
        for domain in excluded_domains:
            if domain in url_lower:
                return False
        
        # Must contain http or www
        if not ('http' in url_lower or 'www.' in url_lower):
            return False
        
        # Must be a reasonable length
        if len(url) < 8 or len(url) > 200:
            return False
        
        return True

    def search_company_website(self, driver, company_name):
        """Search for company website when no profile URL is available"""
        try:
            logger.debug(f"Searching LinkedIn for company: {company_name}")
            search_url = f"https://www.linkedin.com/search/results/companies/?keywords={company_name.replace(' ', '%20')}"
            driver.get(search_url)
            time.sleep(2)
            
            # Find first company result with updated selectors
            company_result_selectors = [
                ".entity-result__item",
                ".reusable-search__result-container",
                ".search-results-container li"
            ]
            
            company_results = []
            for selector in company_result_selectors:
                try:
                    company_results = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=10)
                    if company_results:
                        logger.debug(f"Found {len(company_results)} company results with selector: {selector}")
                        break
                except:
                    continue
            
            if company_results:
                for i, result in enumerate(company_results[:3]):  # Check first 3 results
                    try:
                        # Look for company link
                        company_link_selectors = [
                            ".entity-result__title-text a",
                            ".app-aware-link",
                            "h3 a",
                            ".result-card__title a"
                        ]
                        
                        company_link = None
                        for link_selector in company_link_selectors:
                            try:
                                company_link = result.find_element(By.CSS_SELECTOR, link_selector)
                                if company_link and company_link.get_attribute("href"):
                                    break
                            except:
                                continue
                        
                        if company_link:
                            company_url = company_link.get_attribute("href").split('?')[0]
                            company_name_found = company_link.text.strip()
                            
                            # Check if this is a reasonable match
                            if company_name.lower() in company_name_found.lower() or company_name_found.lower() in company_name.lower():
                                logger.debug(f"Found matching company: {company_name_found} at {company_url}")
                                
                                # Navigate to company page
                                driver.get(company_url)
                                time.sleep(2)
                                
                                # Extract website
                                website_info = self.extract_company_website(driver)
                                website_info["company_url"] = company_url
                                return website_info
                        
                    except Exception as e:
                        logger.debug(f"Error processing company result {i+1}: {e}")
                        continue
            
            logger.debug(f"No matching company found for: {company_name}")
            return {}
            
        except Exception as e:
            logger.debug(f"Error searching for company: {e}")
            return {}
        
    def search_for_ctos(self, driver):
        """Search for CTOs on LinkedIn"""
        logger.debug(f"Searching for {self.num_profiles} CTO profiles...")
        
        try:
            # Navigate directly to LinkedIn search page with query
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={self.search_query.replace(' ', '%20')}"
            logger.debug(f"Navigating to: {search_url}")
            driver.get(search_url)
            time.sleep(2)
            
            # Wait for page to load and check if we're on search results
            current_url = driver.current_url
            if "search/results/people" not in current_url:
                logger.debug("Not on search results page, trying alternative method...")
                
                # Alternative method: use search box
                driver.get("https://www.linkedin.com/")
                time.sleep(2)
                
                # Find the search box and enter the query
                search_box_selectors = [
                    "input[placeholder*='Search']",
                    ".search-global-typeahead__input input",
                    "#global-nav-typeahead input",
                    ".search-global-typeahead__input"
                ]
                
                search_box = None
                for selector in search_box_selectors:
                    search_box = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                    if search_box:
                        break
                
                if not search_box:
                    logger.debug("Could not find search box")
                    return []
                    
                logger.debug("Found search box, entering query...")
                search_box.clear()
                time.sleep(1)
                
                # Type query character by character
                for char in self.search_query:
                    search_box.send_keys(char)
                    time.sleep(0.1)
                
                search_box.send_keys(Keys.RETURN)
                time.sleep(2)
                
                # Check if we're now on search results
                current_url = driver.current_url
                if "search/results" not in current_url:
                    logger.debug("Still not on search results page")
                    return []
            
            
            # Ensure we're on People results tab
            logger.debug("Looking for People filter...")
            people_filter_found = False
            
            # Try to find and click People filter
            people_filter_selectors = [ 
                "//button[contains(@aria-label, 'People')]"
            ]
            
            for selector in people_filter_selectors:
                try:
                    if selector.startswith("//"):
                        people_filter = self.safe_find_element(driver, By.XPATH, selector, timeout=3)
                    else:
                        people_filter = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=3)
                    
                    if people_filter and people_filter.is_displayed():
                        try:
                            people_filter.click()
                            time.sleep(2)
                            logger.debug("Successfully clicked People filter")
                            people_filter_found = True
                            break
                        except:
                            # Try JavaScript click
                            driver.execute_script("arguments[0].click();", people_filter)
                            time.sleep(2)
                            logger.debug("Successfully clicked People filter via JS")
                            people_filter_found = True
                            break
                except:
                    continue
 
            if not people_filter_found:
                logger.debug("Could not find People filter, checking if already on people results...")
                # Check if we're already on people results
                current_url = driver.current_url
                if "search/results/people" not in current_url:
                    # Try to navigate directly to people search
                    people_url = f"https://www.linkedin.com/search/results/people/?keywords={self.search_query.replace(' ', '%20')}"
                    driver.get(people_url)
                    time.sleep(2)
                    logger.debug(f"Navigated directly to people search: {people_url}")
            
            # Wait a bit more for results to load
            # time.sleep(2)
            
            # Look for search results with multiple selector strategies
            logger.debug("Looking for search results...")
            search_results = []
            
            # Try different selectors for search results
            search_results_selectors = [ 
                ".search-results-container li"
            ]
            
            for selector in search_results_selectors:
                try:
                    search_results = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=10)
                    if search_results and len(search_results) > 0:
                        logger.debug(f"Found {len(search_results)} results using selector: {selector}")
                        break
                except:
                    continue
             

            # If no results found, try scrolling and waiting
            if not search_results:
                logger.debug("No results found, trying to scroll and wait...")
                driver.execute_script("window.scrollTo(0, 1000);")
                time.sleep(2)
                
                for selector in search_results_selectors:
                    try:
                        search_results = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=5)
                        if search_results and len(search_results) > 0:
                            logger.debug(f"Found {len(search_results)} results after scroll using selector: {selector}")
                            break
                    except:
                        continue
            
            if not search_results:
                logger.debug("No search results found with any selector")
                logger.debug(f"Current URL: {driver.current_url}")
                logger.debug(f"Page title: {driver.title}")
                return []
            
            logger.debug(f"Found {len(search_results)} total results")
             
            # Filter for CTO results - be more flexible with filtering
            valid_results = search_results
            # cto_keywords = ["CTO", "Chief Technology Officer", "Chief Technical Officer", "Technology Officer", "Tech Officer"]
            
            # for result in search_results:
            #     try:
            #         result_text = result.text.strip().upper()
            #         if result_text and any(keyword.upper() in result_text for keyword in cto_keywords):
            #             valid_results.append(result)
            #             if len(valid_results) >= self.num_profiles:
            #                 break
            #     except:
            #         continue
            
            # logger.debug(f"Found {len(valid_results)} valid CTO results")
            
            if valid_results:
                return self.extract_profile_urls_from_search_results(driver, valid_results)
            else:
                logger.debug("No valid CTO results found")
                # Return first few results anyway for debugging
                logger.debug("Returning first few results for debugging...")
                return self.extract_profile_urls_from_search_results(driver, search_results[:self.num_profiles])
            
        except Exception as e:
            logger.debug(f"Search failed: {str(e)}")
            return []
        
    def main(self):
        """Main function to run the scraper"""
        driver = self.setup_driver()
        if not driver:
            logger.debug("Failed to set up driver")
            return []
        
        try:
            if not self.login_to_linkedin(driver):
                logger.debug("Login failed. Exiting...")
                return []
            
            # Get profile URLs from search results
            start = time.time()
            profile_urls = self.search_for_ctos(driver)
             
            end = time.time()
            logger.debug(f"Time taken to search for CTOs: {end - start} seconds")
            
            
            if not profile_urls:
                logger.debug("No profiles found")
                return []
            
            logger.debug(f"\nFound {len(profile_urls)} profile URLs")
            
            # Extract detailed data from each profile
            profile_data_list = []
            for i, profile_url in enumerate(profile_urls, 1):
                logger.debug(f"\nProcessing profile {i}/{len(profile_urls)}: {profile_url}") 
                profile_data = self.extract_full_profile_data(driver, profile_url) 
                if profile_data:
                    profile_data_list.append(profile_data)
                
                time.sleep(2)  # Be polite with delays
            
            # Print results
            # Ensure all required keys are present in each dictionary
            required_keys = ['name', 'role', 'company', 'company_url', 'company_website']
            profile_data_list = [item for item in profile_data_list if all(item.get(key) is not None for key in required_keys)]

            if not profile_data_list:
                logger.debug("No valid profiles found by scrapping which has company and role information")
            logger.debug("\n" + "="*60)
            logger.debug("SCRAPING RESULTS:")
            logger.debug("="*60)
            
            for i, result in enumerate(profile_data_list, 1):
                logger.debug(f"\nProfile {i}:")
                logger.debug(f"name: {result.get('name', 'N/A')}")
                logger.debug(f"role: {result.get('role', 'N/A')}")
                logger.debug(f"company: {result.get('company', 'N/A')}")
                logger.debug(f"location: {result.get('location', 'N/A')}")
                logger.debug(f"profile_url: {result.get('profile_url', 'N/A')}")
                logger.debug(f"company_url: {result.get('company_url', 'N/A')}")
                logger.debug(f"company_website: {result.get('company_website', 'N/A')}")
                logger.debug("-" * 50)
            
            return profile_data_list
        
        except KeyboardInterrupt:
            logger.debug("\nScraping interrupted by user")
            return []
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            return []
        finally:
            # Always close the browser
            driver.quit()
            logger.debug("Browser closed")

class CustomLeadDiscoveryAgent:
    name = "custom_lead_discovery"
    description = "Custom lead discovery from LinkedIn CEO/CTO search"
    input_schema = {}
    output_schema = {"leads": List[Dict]}

    async def run(self, state):
        logger.debug(f"[{datetime.datetime.now()}] Starting custom_lead_discovery")
        # Initialize scraper with credentials from .env
        LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
        LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
        SEARCH_QUERY = state.get("search_query", "CTO")  # Default to CTO
        NUM_PROFILES = state.get("num_profiles", 3)

        scraper = LinkedInScraper(
            email=LINKEDIN_EMAIL,
            password=LINKEDIN_PASSWORD,
            search_query=SEARCH_QUERY,
            num_profiles=NUM_PROFILES
        )
        results = scraper.main()
        # User's code goes here to populate 'leads' if needed; results is the list
        logger.debug(f"[{datetime.datetime.now()}] Completed custom_lead_discovery: {len(results)} leads found")
        return {"leads": results}