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
import os, random
import datetime
import logging
from typing import Dict, List
import random
from agents.autoprofile_login import profile_login_with_email

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LinkedInScraper:
    def __init__(self, email, search_query="CEO", num_profiles=1, buffer_multiplier=2.0, max_additional_searches=5):
        self.email = email 
        self.search_query = search_query
        self.num_profiles = num_profiles 
        # Increase buffer multiplier for larger requests
        self.buffer_multiplier = max(buffer_multiplier, 1.5 if num_profiles <= 10 else 2.0)
        # Increase max searches for larger requests  
        self.max_additional_searches = max(max_additional_searches, num_profiles // 5)
        self.results = []

    def is_valid_profile(self, profile_data):
        """Check if profile meets minimum requirements (name, role, company_url)"""
        return (profile_data and 
                profile_data.get('name') and 
                profile_data.get('company_url') and 
                profile_data.get('role'))

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
        
        # Enable headless mode
        chrome_options.add_argument("--headless=new")
        
        try:
            # Use webdriver-manager to automatically download and manage ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return driver
        except Exception as e:
            logger.error(f"Error setting up driver: {e}")  # Changed to error level
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
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
            
            # Wait for and fill email field
            email_field = self.safe_find_element(driver, By.ID, "username")
            if not email_field:
                logger.debug("Could not find email field")
                return False
            
            email_field.clear()
            # Type email character by character to simulate human typing
            for char in self.email:
                email_field.send_keys(char)
                time.sleep(0.01)
            
            # Wait for and fill password field
            password_field = self.safe_find_element(driver, By.ID, "password")
            if not password_field:
                logger.debug("Could not find password field")
                return False
            
            password_field.clear()
            # Type password character by character to simulate human typing
            for char in self.password:
                password_field.send_keys(char)
                time.sleep(0.01)
            
            # Click login button
            login_button = self.safe_find_element(driver, By.XPATH, "//button[@type='submit']")
            if not login_button:
                logger.debug("Could not find login button")
                return False
            
            login_button.click()

            # Wait for login to complete and redirect to feed page
            max_wait = 20  # seconds
            start_time = time.time()
            captcha_detected = False
            
            while time.time() - start_time < max_wait:
                current_url = driver.current_url
                page_source = driver.page_source.lower()
                
                # Check for CAPTCHA indicators
                captcha_indicators = [
                    "challenge", "captcha", "security check", "verify", 
                    "puzzle", "slider", "robot", "human"
                ]
                
                if any(indicator in page_source for indicator in captcha_indicators):
                    if not captcha_detected:
                        logger.debug("🔒 CAPTCHA/Security challenge detected!")
                        logger.debug("Please solve the CAPTCHA manually...")
                        logger.debug("The script will wait for you to complete it.")
                        captcha_detected = True
                    
                    # Check every 2 seconds during CAPTCHA
                    time.sleep(2)
                    continue
                
                # Check for successful login
                if current_url.startswith("https://www.linkedin.com/feed"):
                    logger.debug("✅ Login successful - Redirected to feed page")
                    return True
                
                # Check if we're away from login page (another success indicator)
                if "login" not in current_url and "challenge" not in current_url:
                    logger.debug(f"✅ Login successful - Now at: {current_url}")
                    return True
                
                # More frequent checks during normal login
                time.sleep(0.5 if not captcha_detected else 2)
            
            # Final check
            current_url = driver.current_url
            if "login" not in current_url or "feed" in current_url:
                logger.debug("✅ Login appears successful after timeout")
                return True
            
            logger.debug(f"❌ Login timeout - Still at: {current_url}")
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
        
        for i, result in enumerate(search_results):
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

    def search_for_additional_profiles(self, driver, existing_urls, needed_count):
        """Search for additional profiles when we need more valid ones"""
        logger.debug(f"Searching for {needed_count} additional profiles...")
        
        try:
            # Scroll down to load more results or go to next page
            current_url = driver.current_url
            
            # Try scrolling first
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            
            # Look for "Next" button or load more results
            next_selectors = [
                "button[aria-label='Next']",
                ".artdeco-pagination__button--next",
                "a[aria-label='Next']"
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=3)
                    if next_button and next_button.is_enabled():
                        logger.debug("Found Next button, clicking...")
                        next_button.click()
                        time.sleep(random.uniform(2, 4))
                        break
                except:
                    continue
            
            # Extract new results
            search_results_selectors = [".search-results-container li"]
            
            new_results = []
            for selector in search_results_selectors:
                try:
                    search_results = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=10)
                    if search_results:
                        new_results = search_results
                        logger.debug(f"Found {len(new_results)} additional results")
                        break
                except:
                    continue
            
            if new_results:
                new_urls = self.extract_profile_urls_from_search_results(driver, new_results)
                # Filter out URLs we already have
                additional_urls = [url for url in new_urls if url not in existing_urls]
                logger.debug(f"Found {len(additional_urls)} new unique URLs")
                return additional_urls[:needed_count * 2]  # Get extra in case some are invalid
            
            return []
            
        except Exception as e:
            logger.debug(f"Error searching for additional profiles: {e}")
            return []

    def extract_company_website(self, driver):
        """Extract company website from company page"""
        try:
            logger.debug("Looking for company website...")
            
            # Wait for page to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        ".org-top-card-summary__title, .org-page-navigation__items, a[href^='http']"
                    ))
                )
            except TimeoutException:
                logger.debug("Company page did not load in time.")
            
            # Try to find and click About section first
            logger.debug("Looking for About section...")
            about_selectors = [
                "a[href*='/about/']"
            ]
            
            about_clicked = False
            for selector in about_selectors:
                try:
                    about_link = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                    if about_link:
                        logger.debug(f"Found About section with {selector} selector, clicking...")
                        about_link.click()
                        try:
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((
                                    By.CSS_SELECTOR,
                                    ".org-about-module__margin-bottom, .org-about-company-module"
                                ))
                            )
                        except TimeoutException:
                            logger.debug("About section content did not load after clicking About.")
                        about_clicked = True
                        break
                except Exception as e:
                    continue
            
            if not about_clicked:
                logger.debug("Could not find About section, looking for website on main page...")
            
            # Look for website in About section or main page
            website_selectors = [
                # Website link in About section based on the HTML you provided
                ".org-about-module__margin-bottom a[href*='http']:not([href*='linkedin.com'])"
            ]
            
            for selector in website_selectors:
                try:
                    website_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in website_elements:
                        href = element.get_attribute("href")
                        if href and self.is_valid_website_url(href):
                            logger.debug(f"Found company website: {href} with {selector} selector")
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
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        ".entity-result__item, .reusable-search__result-container, .search-results-container li"
                    ))
                )
            except TimeoutException:
                logger.debug("Company search results did not load.")
            
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
        """Search for CTOs on LinkedIn with proper pagination support"""
        logger.debug(f"Searching for {self.num_profiles} profiles...")
        
        try:
            # Navigate directly to LinkedIn search page with query
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={self.search_query.replace(' ', '%20')}"
            logger.debug(f"Navigating to: {search_url}")
            driver.get(search_url)
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".search-results-container, .reusable-search__result-container"))
                )
            except TimeoutException:
                logger.debug("Search results did not load in time.")

            # Wait for page to load and check if we're on search results
            current_url = driver.current_url
            if "search/results/people" not in current_url:
                logger.debug("Not on search results page, trying alternative method...")
                
                # Alternative method: use search box
                driver.get("https://www.linkedin.com/")
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search'], .search-global-typeahead__input"))
                    )
                except TimeoutException:
                    logger.debug("Search input did not load in time.")
                
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
                
                search_box.send_keys(Keys.RETURN)
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            ".search-results-container, .reusable-search__result-container, .search-result__info"
                        ))
                    )
                except TimeoutException:
                    logger.debug("Search results did not load in time after hitting Enter.")
                
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
                            try:
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, ".search-results-container li, .reusable-search__result-container"))
                                )
                            except TimeoutException:
                                logger.debug("People search results did not load after filter click.")
                            logger.debug("Successfully clicked People filter")
                            people_filter_found = True
                            break
                        except:
                            # Try JavaScript click
                            driver.execute_script("arguments[0].click();", people_filter)
                            try:
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, ".search-results-container li, .reusable-search__result-container"))
                                )
                            except TimeoutException:
                                logger.debug("People search results did not load after filter click.")
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
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((
                                By.CSS_SELECTOR,
                                ".search-results-container li, .reusable-search__result-container"
                            ))
                        )
                    except TimeoutException:
                        logger.debug("People search results did not load after fallback navigation.")
                    logger.debug(f"Navigated directly to people search: {people_url}")
            
            # NEW: Multi-page scraping logic
            all_profile_urls = []
            page_count = 0
            max_pages = 10  # Safety limit
            target_urls_needed = int(self.num_profiles * self.buffer_multiplier)
            
            logger.debug(f"Target URLs needed: {target_urls_needed}")
            
            while len(all_profile_urls) < target_urls_needed and page_count < max_pages:
                page_count += 1
                logger.debug(f"Processing page {page_count}...")
                
                # Wait a bit for page content to load
                time.sleep(random.uniform(2, 4))
                
                # Get search results from current page
                search_results = []
                search_results_selectors = [".search-results-container li"]
                
                for selector in search_results_selectors:
                    try:
                        search_results = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=10)
                        if search_results and len(search_results) > 0:
                            logger.debug(f"Found {len(search_results)} results on page {page_count}")
                            break
                    except:
                        continue
                
                # If no results found, try scrolling and waiting
                if not search_results:
                    logger.debug("No results found, trying to scroll and wait...")
                    try:
                        driver.execute_script("window.scrollTo(0, 1000);")
                        time.sleep(random.uniform(2, 5))
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".search-results-container li, .reusable-search__result-container"))
                        )
                    except TimeoutException:
                        logger.debug("Search results did not load after scroll.")
                    
                    for selector in search_results_selectors:
                        try:
                            search_results = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=5)
                            if search_results and len(search_results) > 0:
                                logger.debug(f"Found {len(search_results)} results after scroll on page {page_count}")
                                break
                        except Exception as e:
                            continue
                
                if not search_results:
                    logger.debug(f"No search results found on page {page_count}")
                    break
                
                # Extract URLs from current page
                page_urls = self.extract_profile_urls_from_search_results(driver, search_results)
                
                # Add new URLs (avoid duplicates)
                new_urls = [url for url in page_urls if url not in all_profile_urls]
                all_profile_urls.extend(new_urls)
                
                logger.debug(f"Page {page_count}: Found {len(page_urls)} URLs, {len(new_urls)} new URLs")
                logger.debug(f"Total URLs collected: {len(all_profile_urls)}/{target_urls_needed}")
                
                # Check if we have enough URLs
                if len(all_profile_urls) >= target_urls_needed:
                    logger.debug(f"Collected enough URLs ({len(all_profile_urls)}) - stopping pagination")
                    break
                
                # Try to go to next page
                next_page_found = False
                
                # First, scroll to bottom to ensure pagination buttons are visible
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Try different next button selectors
                next_button_selectors = [
                    "button[aria-label='Next']",
                    ".artdeco-pagination__button--next",
                    "a[aria-label='Next']",
                    ".artdeco-pagination__button.artdeco-pagination__button--next",
                    "button.artdeco-pagination__button.artdeco-pagination__button--next:not([disabled])"
                ]
                
                for selector in next_button_selectors:
                    try:
                        next_button = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                        if next_button and next_button.is_enabled() and next_button.is_displayed():
                            # Check if button is not disabled
                            if "disabled" not in next_button.get_attribute("class") and next_button.get_attribute("disabled") != "true":
                                logger.debug(f"Found enabled Next button with selector: {selector}")
                                
                                # Scroll to button and click
                                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                                time.sleep(1)
                                
                                try:
                                    next_button.click()
                                    logger.debug("Successfully clicked Next button")
                                except:
                                    # Try JavaScript click as backup
                                    driver.execute_script("arguments[0].click();", next_button)
                                    logger.debug("Successfully clicked Next button via JavaScript")
                                
                                # Wait for new page to load
                                time.sleep(random.uniform(3, 5))
                                
                                # Verify we moved to next page by checking URL or content change
                                new_url = driver.current_url
                                if "start=" in new_url or len(driver.find_elements(By.CSS_SELECTOR, ".search-results-container li")) > 0:
                                    next_page_found = True
                                    logger.debug(f"Successfully moved to next page: {new_url}")
                                    break
                    except Exception as e:
                        logger.debug(f"Error with next button selector {selector}: {e}")
                        continue
                
                if not next_page_found:
                    logger.debug("No more pages available or Next button not found")
                    break
            
            logger.debug(f"Pagination complete. Collected {len(all_profile_urls)} URLs across {page_count} pages")
            return all_profile_urls
            
        except Exception as e:
            logger.debug(f"Search failed: {str(e)}")
            return []
      
    def extract_full_profile_data(self, driver, profile_url):
        """Navigate to individual profile and extract complete data"""
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
        
        try:
            logger.debug(f"Navigating to profile: {profile_url}")
            driver.get(profile_url)
            time.sleep(random.uniform(1, 3))

            # Wait until the profile name or any known element appears
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "h1.text-heading-xlarge, .pv-text-details__left-panel h1, .text-heading-xlarge, h1"
                ))
            )
        except TimeoutException as e:
            logger.error(f"Timeout loading profile: {e}")
            return profile_data  # Return partial data instead of empty
        except Exception as e:
            logger.error(f"Error navigating to profile: {e}")
            return profile_data  # Return partial data instead of empty

        # Extract name from profile page
        try:
            name_selectors = ["h1"]
            for selector in name_selectors:
                name_element = self.safe_find_element(driver, By.CSS_SELECTOR, selector, timeout=5)
                if name_element:
                    name_text = self.clean_name(name_element.text)
                    if name_text:
                        profile_data["name"] = name_text
                        logger.debug(f"Found name: {name_text} with {selector} selector")
                        break
        except Exception as e:
            logger.error(f"Error extracting name: {e}")
            # Continue processing even if name extraction fails
        
        # Extract experience information
        try:
            # Scroll and wait for experience section
            driver.execute_script("window.scrollTo(0, 800);")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.artdeco-list__item"))
            )

            experience_list_selectors = ["li.artdeco-list__item"]
            experience_entries = []
            
            for selector in experience_list_selectors:
                entries = self.safe_find_elements(driver, By.CSS_SELECTOR, selector, timeout=5)
                if entries:
                    valid_entries = [e for e in entries if e.find_elements(By.CSS_SELECTOR, "a[data-field='experience_company_logo']")]
                    if valid_entries:
                        experience_entries = valid_entries
                        logger.debug(f"Found {len(valid_entries)} experience entries with selector: {selector}")
                        break
                            
            if experience_entries:
                first_entry = experience_entries[0]
                logger.debug("Processing first experience entry...")

                try:
                    sub_components = first_entry.find_elements(By.CSS_SELECTOR, ".pvs-entity__sub-components")
                    is_single_company = bool(sub_components)

                    if is_single_company:
                        logger.debug("Detected single company with sub-positions structure")
                        
                        # Extract company name
                        try:
                            company_elements = first_entry.find_elements(By.CSS_SELECTOR, ".display-flex.align-items-center.mr1.hoverable-link-text.t-bold span[aria-hidden='true']")
                            if company_elements:
                                company_name = company_elements[0].text.strip()
                                if company_name and len(company_name) > 1:
                                    profile_data["company"] = company_name
                                    logger.debug(f"Found company: {company_name}")
                        except Exception as e:
                            logger.error(f"Error extracting company name (single company): {e}")

                        # Extract company URL
                        try:
                            company_links = first_entry.find_elements(By.CSS_SELECTOR, "a[data-field='experience_company_logo']")
                            if company_links:
                                company_url = company_links[0].get_attribute("href").split('?')[0]
                                if "/company/" in company_url:
                                    profile_data["company_url"] = company_url
                                    logger.debug(f"Found company URL: {company_url}")
                                elif "search/results/all" in company_url:
                                    if profile_data.get("company"):
                                        logger.debug(f"Company URL is a search link, searching for company: {profile_data['company']}")
                                        try:
                                            company_info = self.search_company_website(driver, profile_data["company"])
                                            if company_info.get("company_url"):
                                                profile_data["company_url"] = company_info["company_url"]
                                                logger.debug(f"Found company URL via search: {profile_data['company_url']}")
                                        except Exception as e:
                                            logger.error(f"Error searching for company: {e}")
                        except Exception as e:
                            logger.error(f"Error extracting company URL (single company): {e}")

                        # Extract position
                        try:
                            sub_position_elements = first_entry.find_elements(By.CSS_SELECTOR, ".display-flex.align-items-center.mr1.t-bold span[aria-hidden='true']")
                            if sub_position_elements:
                                position = sub_position_elements[0].text.strip()
                                if position and len(position) > 1:
                                    profile_data["role"] = position
                                    logger.debug(f"Found position: {position}")
                        except Exception as e:
                            logger.error(f"Error extracting position (single company): {e}")
                            
                    else:
                        logger.debug("Detected multiple companies structure")
                        
                        # Extract position
                        try:
                            position_elements = first_entry.find_elements(By.CSS_SELECTOR, ".display-flex.align-items-center.mr1.t-bold span[aria-hidden='true']")
                            if position_elements:
                                position = position_elements[0].text.strip()
                                if position and len(position) > 1:
                                    profile_data["role"] = position
                                    logger.debug(f"Found position: {position}")
                        except Exception as e:
                            logger.error(f"Error extracting position (multiple companies): {e}")

                        # Extract company name
                        try:
                            company_name_elements = first_entry.find_elements(By.CSS_SELECTOR, ".t-14.t-normal span[aria-hidden='true']")
                            for element in company_name_elements:
                                text = element.text.strip()
                                company_name = text.split("·")[0].strip()
                                if company_name and len(company_name) > 1 and company_name != "Present":
                                    profile_data["company"] = company_name
                                    logger.debug(f"Found company: {company_name}")
                                    break
                        except Exception as e:
                            logger.error(f"Error extracting company name (multiple companies): {e}")

                        # Extract company URL
                        try:
                            company_links = first_entry.find_elements(By.CSS_SELECTOR, "a[data-field='experience_company_logo']")
                            if company_links:
                                company_url = company_links[0].get_attribute("href").split('?')[0]
                                if "/company/" in company_url:
                                    profile_data["company_url"] = company_url
                                    logger.debug(f"Found company URL: {company_url}")
                                elif "search/results/all" in company_url:
                                    if profile_data.get("company"):
                                        logger.debug(f"Company URL is a search link, searching for company: {profile_data['company']}")
                                        try:
                                            company_info = self.search_company_website(driver, profile_data["company"])
                                            if company_info.get("company_url"):
                                                profile_data["company_url"] = company_info["company_url"]
                                                logger.debug(f"Found company URL via search: {profile_data['company_url']}")
                                        except Exception as e:
                                            logger.error(f"Error searching for company: {e}")
                        except Exception as e:
                            logger.error(f"Error extracting company URL (multiple companies): {e}")
                            
                except Exception as e:
                    logger.error(f"Error processing experience entry: {e}")
                    # Continue processing even if experience extraction fails
                    
        except Exception as e:
            logger.error(f"Error extracting experience information: {e}")
            # Continue processing even if experience section fails
        
        # Extract location
        try:
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
        except Exception as e:
            logger.error(f"Error extracting location: {e}")
            # Continue processing even if location extraction fails
        
        # Company page navigation + dynamic wait - WRAPPED IN TRY-CATCH
        if profile_data.get("company_url"):
            try:
                logger.debug(f"Navigating to company page: {profile_data['company_url']}")
                driver.get(profile_data["company_url"])
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='http']"))
                )
                website_info = self.extract_company_website(driver)
                if website_info.get("company_website"):
                    profile_data["company_website"] = website_info["company_website"]
                    logger.debug(f"Found company website: {profile_data['company_website']}")
            except Exception as e:
                logger.error(f"Error navigating to company page or extracting website: {e}")
                # Continue without company website - don't fail the entire profile
                logger.debug("Continuing without company website information")

        return profile_data

    def main(self):
        """Main function to run the scraper with enhanced large-scale support"""
        driver, chrome_process = profile_login_with_email(self.email)
        if not driver:
            logger.debug("Failed to set up driver")
            return []
        
        try:  
            # Get profile URLs from search results (now with pagination)
            start = time.time()
            profile_urls = self.search_for_ctos(driver)
            
            end = time.time()
            logger.debug(f"Time taken to search with pagination: {end - start} seconds")
            
            if not profile_urls:
                logger.debug("No profiles found")
                return []
            
            logger.debug(f"\nFound {len(profile_urls)} profile URLs across multiple pages")
            
            # Enhanced processing for large requests
            valid_profiles = []
            profile_urls_index = 0
            additional_search_attempts = 0
            all_processed_urls = set()
            
            logger.debug(f"Target: {self.num_profiles} valid profiles")
            
            # Process URLs in batches for better performance
            batch_size = 5 if self.num_profiles >= 20 else 3
            processed_in_batch = 0
            
            while len(valid_profiles) < self.num_profiles:
                # Check if we have more URLs to process
                if profile_urls_index >= len(profile_urls):
                    if additional_search_attempts < self.max_additional_searches:
                        logger.debug(f"\nNeed {self.num_profiles - len(valid_profiles)} more valid profiles")
                        logger.debug(f"Attempting additional search #{additional_search_attempts + 1}")
                        
                        # For large requests, search for more profiles more aggressively
                        needed_count = (self.num_profiles - len(valid_profiles)) * 2
                        additional_urls = self.search_for_additional_profiles(driver, list(all_processed_urls), needed_count)
                        
                        if additional_urls:
                            profile_urls.extend(additional_urls)
                            logger.debug(f"Added {len(additional_urls)} new URLs to process")
                        else:
                            logger.debug("No additional URLs found")
                        
                        additional_search_attempts += 1
                    else:
                        logger.debug(f"Reached maximum additional search attempts ({self.max_additional_searches})")
                        break
                
                # If we have URLs to process
                if profile_urls_index < len(profile_urls):
                    current_url = profile_urls[profile_urls_index]
                    
                    # Skip if already processed
                    if current_url in all_processed_urls:
                        profile_urls_index += 1
                        continue
                    
                    try:
                        logger.debug(f"\nProcessing profile {profile_urls_index + 1}/{len(profile_urls)}: {current_url}")
                        logger.debug(f"Valid profiles so far: {len(valid_profiles)}/{self.num_profiles}")
                        
                        profile_data = self.extract_full_profile_data(driver, current_url)
                        all_processed_urls.add(current_url)
                        processed_in_batch += 1
                        
                        # Check if profile meets our criteria
                        if self.is_valid_profile(profile_data):
                            valid_profiles.append(profile_data)
                            logger.debug(f"✅ Valid profile found! Total valid: {len(valid_profiles)}")
                            logger.debug(f"   Name: {profile_data.get('name')}")
                            logger.debug(f"   Role: {profile_data.get('role')}")
                            logger.debug(f"   Company: {profile_data.get('company')}")
                        else:
                            logger.debug(f"❌ Profile doesn't meet criteria")
                        
                        profile_urls_index += 1
                        
                        # Add longer delays for large batches to avoid rate limiting
                        delay = random.uniform(1.0, 2.0)
                        if self.num_profiles >= 20:
                            delay = random.uniform(2.0, 4.0)
                        elif processed_in_batch >= batch_size:
                            delay = random.uniform(3.0, 6.0)  # Longer break after batch
                            processed_in_batch = 0
                            logger.debug(f"Batch complete, taking a longer break ({delay:.1f}s)")
                        
                        time.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing profile {profile_urls_index + 1} ({current_url}): {e}")
                        all_processed_urls.add(current_url)
                        profile_urls_index += 1
                        continue
                else:
                    # No more URLs and no more search attempts
                    break
            
            # Enhanced summary for large requests
            logger.debug(f"\n📊 Final Processing Summary:")
            logger.debug(f"   🎯 Target profiles: {self.num_profiles}")
            logger.debug(f"   ✅ Valid profiles found: {len(valid_profiles)}")
            logger.debug(f"   🔍 Total URLs processed: {len(all_processed_urls)}")
            logger.debug(f"   📄 Total URLs collected: {len(profile_urls)}")
            logger.debug(f"   🔄 Additional searches: {additional_search_attempts}")
            logger.debug(f"   📈 Success rate: {len(valid_profiles)}/{len(all_processed_urls)} ({len(valid_profiles)/max(len(all_processed_urls), 1)*100:.1f}%)")
            
            if len(valid_profiles) < self.num_profiles:
                shortage = self.num_profiles - len(valid_profiles)
                logger.debug(f"⚠️  Warning: {shortage} profiles short of target")
                if shortage > self.num_profiles * 0.3:  # More than 30% short
                    logger.debug("💡 Suggestions:")
                    logger.debug("   - Try a broader search query")
                    logger.debug("   - Increase buffer_multiplier")
                    logger.debug("   - Check if LinkedIn has enough results for your query")
            else:
                logger.debug(f"🎉 Successfully found all {self.num_profiles} requested valid profiles!")
            
            # Display results
            if valid_profiles:
                logger.debug("\n" + "="*60)
                logger.debug("SCRAPING RESULTS:")
                logger.debug("="*60)
                
                for i, result in enumerate(valid_profiles, 1):
                    logger.debug(f"\nProfile {i}:")
                    logger.debug(f"Name: {result.get('name', 'N/A')}")
                    logger.debug(f"Role: {result.get('role', 'N/A')}")
                    logger.debug(f"Company: {result.get('company', 'N/A')}")
                    logger.debug(f"Location: {result.get('location', 'N/A')}")
                    logger.debug(f"Profile URL: {result.get('profile_url', 'N/A')}")
                    logger.debug(f"Company URL: {result.get('company_url', 'N/A')}")
                    logger.debug(f"Company Website: {result.get('company_website', 'N/A')}")
                    logger.debug("-" * 50)
            
            return valid_profiles
        
        except KeyboardInterrupt:
            logger.debug("\nScraping interrupted by user")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in main function: {e}")
            return []
        finally:
            # Always close the browser 
            try:
                driver.quit()
                chrome_process.terminate()
                logger.debug("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
class CustomLeadDiscoveryAgent:
    name = "custom_lead_discovery"
    description = "Custom lead discovery from LinkedIn CEO/CTO search"
    input_schema = {}
    output_schema = {"leads": List[Dict]}

    async def run(self, state):
        logger.debug(f"[{datetime.datetime.now()}] Starting custom_lead_discovery")
        # Initialize scraper with credentials from .env
        LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL") 
        SEARCH_QUERY = state.get("search_query", "CTO")  # Default to CTO
        NUM_PROFILES = state.get("num_profiles", 2)

        scraper = LinkedInScraper(
            email=LINKEDIN_EMAIL,
            search_query=SEARCH_QUERY,
            num_profiles=NUM_PROFILES
        )
        results = scraper.main()
        # User's code goes here to populate 'leads' if needed; results is the list
        logger.debug(f"[{datetime.datetime.now()}] Completed custom_lead_discovery: {len(results)} leads found")
        return {"leads": results}
    
        
# if __name__ == "__main__":
#     # For testing purposes
#     import asyncio
#     state = {
#         "search_query": "AI CEO",
#         "num_profiles": 10
#     }
#     agent = CustomLeadDiscoveryAgent()
#     loop = asyncio.get_event_loop()
#     start = time.time()
#     results = loop.run_until_complete(agent.run(state))
#     end = time.time()
#     print(f"Time taken: {end - start} seconds")