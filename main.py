import sys
import json
import webbrowser
import threading
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QDialog, QFormLayout, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent
import pyttsx3
from playwright.sync_api import sync_playwright
import os
import re
from datetime import datetime
from typing import List, Dict
from PyQt6.QtCore import pyqtSignal, QObject
from playwright.sync_api import sync_playwright
from playwright.__main__ import main
import os
from collections import Counter

# Paths - using raw strings for Windows paths
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "csfloat_profile")

EXTENSION_PATH = os.path.join(os.path.dirname(__file__), "BetterFloat-Chrome-Web-Store")
SCRAPED_TEXT_FILE = "csfloat_newlylisted_scrap.txt"
SCRAPED_JSON_FILE = "csfloat_newlylisted_scrap.json"
API_JSON_FILE = "csfloat_newlylisted_api_data.json"
MERGED_JSON_FILE = "merged_deals.json"
CURRENT_ITEMS_FILE = MERGED_JSON_FILE    # New scraped items
CLIENT_SETTINGS_FILE = "bot_settings.json"    # User settings
SETTINGS_FILE = "bot_settings.json"





# Initialize TTS engine
tts_engine = pyttsx3.init()




def create_negative_profit_file(merged_file_path, output_file_path='profit_deals.json'):
    try:
        # Load the existing merged data from the source file
        with open(merged_file_path, 'r', encoding='utf-8') as f:
            merged_data = json.load(f)

        # Filter out negative profit items
        negative_profit_items = [
            item for item in merged_data
            if isinstance(item.get('profit'), str) and item['profit'].startswith('-$')
        ]

        # Sort the items to have the newest ones on top (if 'date' exists)
        negative_profit_items.sort(key=lambda x: x.get('date', ''), reverse=True)

        # Try to read the existing data in the output file
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = []  # If the file doesn't exist, start with an empty list

        # Append the new negative profit items to the existing data
        existing_data = negative_profit_items + existing_data

        # Write the updated data to the output file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)

        print(f"✅ {output_file_path} updated with {len(negative_profit_items)} new negative profit items.")

    except Exception as e:
        print(f"❌ Error creating or updating {output_file_path}: {e}")



def speak(text):
    """Speak text asynchronously."""
    threading.Thread(target=lambda: tts_engine.say(text) or tts_engine.runAndWait()).start()


class ScraperSignals(QObject):
    scraping_complete = pyqtSignal()
    
    
class CSFloatDataProcessor:
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        # Use absolute paths to ensure consistency
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.scraped_json_path = os.path.join(self.script_dir, 'csfloat_newlylisted_scrap.json')
        self.api_json_path = os.path.join(self.script_dir, 'extracted_csfloat_data.json')
        self.merged_path = os.path.join(self.script_dir, 'merged_deals.json')
        
        

    @staticmethod
    def clean_name(name):
        """Standardize item names by removing hidden characters and formatting."""
        if not name:
            return ""
        return name.strip().lower().replace('\u200b', '').replace('\xa0', '').replace('’', "'").replace('–', '-')
    
    @staticmethod
    def clean_float_value(float_val):
        """Convert float value to a consistent float format."""
        if float_val in [None, "N/A"]:
            return None
        try:
            return float(float_val)
        except (ValueError, TypeError):
            return None

    

   

    @staticmethod
    def load_json(file_path):
        """Load JSON data from a file, return empty list if file is missing."""
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=4, ensure_ascii=False)
            return []
        
        # Simple retry logic
        for _ in range(3):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else [data]
            except json.JSONDecodeError:
                time.sleep(0.1)
                continue
        
        return []

    def count_matching_names(self, api_data, scraped_data):
        """Find matching market_hash_names between two data sources."""
        api_names = [self.clean_name(item.get('market_hash_name', '')) for item in api_data]
        scraped_names = [self.clean_name(item.get('market_hash_name', '')) for item in scraped_data]

        api_counter = Counter(api_names)
        scraped_counter = Counter(scraped_names)

        common_names = set(api_names) & set(scraped_names)

        match_counts = {
            name: min(api_counter[name], scraped_counter[name]) for name in common_names
        }

        total_matches = sum(match_counts.values())
        return total_matches, list(common_names), match_counts

    def merge_items(self, api_data, scraped_data, matching_names):
        """Merge items from both sources based on common names."""
        merged = []
        for name in matching_names:
            api_item = next((item for item in api_data if self.clean_name(item.get('market_hash_name', '')) == name), None)
            scraped_item = next((item for item in scraped_data if self.clean_name(item.get('market_hash_name', '')) == name), None)

            if not api_item or not scraped_item:
                continue

            merged.append({
                'timestamp': self.timestamp,
                'id': api_item.get('id'),
                'market_hash_name': api_item.get('market_hash_name', '').title(),
                'wear_name': api_item.get('wear_name', '').title(),
                'price': api_item.get('price', 0) / 100,
                'base_price': api_item.get('base_price', 0) / 100,
                'predicted_price': api_item.get('predicted_price', 0) / 100,
                'float_value': self.clean_float_value(api_item.get('float_value')),
                'profit': scraped_item.get('profit'),
                'profit_percent': scraped_item.get('profit_percentage'),
                'bid_ask': scraped_item.get('bid_ask', ''),
                'url': api_item.get('url', f"https://csfloat.com/item/{api_item.get('id', '')}")
            })
        return merged

    def save_json(self, data, file_path):
        """Save data to a JSON file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ Merged data saved to '{file_path}'")
        
    def load_json_with_retry(self, file_path, max_retries=5, delay=0.5):
        """Robust JSON loading with retries and file existence checks."""
        for attempt in range(max_retries):
            try:
                if not os.path.exists(file_path):
                    print(f"File not found: {file_path} (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                
                if os.path.getsize(file_path) == 0:
                    print(f"File empty: {file_path} (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else [data]
                    
            except json.JSONDecodeError as e:
                print(f"JSON decode error in {file_path} (attempt {attempt + 1}): {str(e)}")
                time.sleep(delay)
            except Exception as e:
                print(f"Error loading {file_path}: {str(e)}")
                time.sleep(delay)
        
        print(f"Failed to load {file_path} after {max_retries} attempts")
        return []

    def find_matching_items(self):
        """Complete end-to-end processing with robust error handling."""
        
        
        # Load data with retries
        api_data = self.load_json_with_retry(self.api_json_path)
        scraped_data = self.load_json_with_retry(self.scraped_json_path)
        
        
   
        
        # Process data
        matches, common_names, match_counts = self.count_matching_names(api_data, scraped_data)
        
        
        print("✅ Total matching items:", matches)

        merged = self.merge_items(api_data, scraped_data, common_names)
        self.save_json(merged, self.merged_path)
        return merged

class ScraperThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.ensure_playwright_browsers()
        self.signals = ScraperSignals()
        self.running = True
        self.daemon = True  # This ensures the thread exits when main program exits
        
    
    def ensure_playwright_browsers(self):
        """Ensure Playwright browsers are installed before scraping"""
        try:
            # Try the sync_playwright installation method
            with sync_playwright() as p:
                pass  # This will trigger browser installation if needed
        except Exception as e:
            print(f"Warning: Could not install browsers automatically: {e}")

    def run(self):
        while self.running:
            try:
                self.run_scraping_cycle()
                print(f"✅ Scraping cycle completed at {datetime.now()}")
                self.signals.scraping_complete.emit()
            except Exception as e:
                print(f"❌ Error in scraping cycle: {e}")
            
            # Wait for 30 seconds
            for _ in range(30):
                if not self.running:
                    return
                time.sleep(1)

    def run_scraping_cycle(self):
        with sync_playwright() as p:
            # Launch browser
            base_dir = os.path.dirname(os.path.abspath(__file__))
            chromium_path = os.path.join(base_dir, "chromium", "chrome-win", "chrome.exe")
            browser = p.chromium.launch_persistent_context(
                executable_path=chromium_path,
                user_data_dir=USER_DATA_DIR, 
                headless=False,
                args=[ 
                    "--no-sandbox",
                    f"--disable-extensions-except={EXTENSION_PATH}",
                    f"--load-extension={EXTENSION_PATH}",
                ]
            )
            
            page = browser.new_page()
            
            # Setup API response capture
            api_data = None
            api_captured = False
            
            def handle_response(response):
                nonlocal api_data, api_captured
                if "api/v1/listings" in response.url and "sort_by=most_recent" in response.url:
                    try:
                        api_data = response.json()
                        api_captured = True
                        print("✅ API data captured successfully")
                    except Exception as e:
                        print(f"❌ Error processing API response: {e}")
            
            page.on("response", handle_response)
            
            # Navigate to page
            print("🌐 Loading CSFloat page...")
            page.goto("https://csfloat.com/search?sort_by=most_recent", timeout=180000)
            
            # Handle login if needed
            if not self.is_logged_in(page):
                print("🔍 Not logged in, attempting login...")
                self.handle_steam_login(page)
                page.goto("https://csfloat.com/search?sort_by=most_recent", timeout=180000)
                if not self.is_logged_in(page):
                    print("❌ Login failed. Please try again.")
                    browser.close()
                    return
            
            # Wait for content and API
            print("🔄 Waiting for content to load...")
            try:
                page.wait_for_selector('[_ngcontent-ng-c1134033550]', timeout=30000)
                
                # Additional wait for API (if not already captured)
                if not api_captured:
                    print("⏳ Waiting for API response...")
                    page.wait_for_timeout(5000)
                    
                    # Alternative method: directly fetch API if not captured
                    if not api_captured:
                        print("🔍 Attempting direct API fetch...")
                        api_response = page.goto("https://csfloat.com/api/v1/listings?sort_by=most_recent", timeout=15000)
                        if api_response:
                            api_data = api_response.json()
                            api_captured = True
            except Exception as e:
                print(f"❌ Error loading content: {e}")
            
            # Save scraped data
            
            elements = page.query_selector_all('[_ngcontent-ng-c1134033550]')
            with open(SCRAPED_TEXT_FILE, 'w', encoding='utf-8') as f:
                for el in elements:
                    f.write(el.inner_text() + "\n")
            print(f"✅ Scraped data saved to {SCRAPED_TEXT_FILE}")

            # 2. Save API data if captured
            if api_captured and api_data:
                with open(API_JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(api_data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                print(f"💾 API data saved to {API_JSON_FILE}")

                # 3. Extract fields from API data
                self.extract_fields(API_JSON_FILE, "extracted_csfloat_data.json")
                
                # 4. Convert scraped text to JSON
                self.convert_scraped_to_json()
                
                # 5. Verify both final files exist before merging
                extracted_path = os.path.join(os.path.dirname(__file__), "extracted_csfloat_data.json")
                scraped_path = os.path.join(os.path.dirname(__file__), SCRAPED_JSON_FILE)
                
                # Wait with timeout for both files
                max_wait = 5  # seconds
                start_time = time.time()
                files_ready = False
                
                while not files_ready:
                    files_ready = (os.path.exists(extracted_path) and 
                                os.path.getsize(extracted_path) > 0 and
                                os.path.exists(scraped_path) and 
                                os.path.getsize(scraped_path) > 0)
                    
                    if files_ready:
                        break
                        
                    if time.time() - start_time > max_wait:
                        print("❌ Timed out waiting for files to be ready")
                        break
                        
                    time.sleep(0.2)  # Short sleep to prevent CPU overuse
                
                if files_ready:
                    # 6. Only proceed with merging if files are ready
                    processor = CSFloatDataProcessor()
                    merged_data = processor.find_matching_items()
                    self.save_merged_data(merged_data, MERGED_JSON_FILE)
                    print(f"💾 Merged data saved to {MERGED_JSON_FILE}")
                    
                else:
                    print("⚠️ Skipping merge due to incomplete files")
            else:
                print("❌ Failed to capture API data")

            browser.close()

    def is_logged_in(self, page, timeout=15000):
        try:
            page.wait_for_selector('text="Sign in through Steam"', timeout=timeout/3)
            return False
        except:
            try:
                page.wait_for_selector('[_ngcontent-ng-c1134033550]', timeout=timeout/3)
                return True
            except:
                return False

    
    def handle_steam_login(self, page):
        print("🔐 Attempting Steam login...")

        with page.expect_navigation(timeout=300000):  # wait for redirect to Steam
            page.click('text="Sign in through Steam"')

        print("⚡ Please complete the Steam login manually within 5 minutes...")

        try:
            # Wait for redirect back to original site (e.g., csfloat.com)
            page.wait_for_url("https://csfloat.com/*", timeout=300000)
            print("✅ Steam login successful!")
        except:
            print("⏰ Login not completed in time.")

    def parse_csfloat_data(self, text: str) -> List[Dict[str, str]]:
        # Split items by "Buy Now", because each item ends with Buy Now
        items = [item.strip() for item in text.split('Buy Now') if item.strip()]
        
        parsed_items = []
        
        for item in items:
            lines = [line.strip() for line in item.split('\n') if line.strip() and line.strip() != "photo_camera"]  
          
            if len(lines) < 2:  # minimum 2 lines needed (market_hash_name and wear_name)
                continue
                
            item_data = {
                'market_hash_name': 'N/A',
                'wear_name': 'N/A',
                'float_value': 'N/A',
                'profit': 'N/A',
                'profit_percentage': 'N/A',
                'bid_ask': 'N/A'
            }
            
            # 1. Item Name (first line)
            item_data['market_hash_name'] = lines[0]
            
            # 2. Wear Condition (second line if wear terms present)
            wear_terms = ['Factory New', 'Minimal Wear', 'Field-Tested', 
                          'Well-Worn', 'Battle-Scarred', 'Base Grade', 
                          'Exotic', 'Remarkable', 'Container', 'Sticker', 'Charm']
            
            for line in lines[1:3]:  # check next two lines after item name
                if any(wear in line for wear in wear_terms):
                    item_data['wear_name'] = line
                    break
            
            # 3. Float Value (pattern 0.xxxxxx)
            for line in lines:
                float_match = re.match(r'^0\.\d+$', line)
                if float_match:
                    item_data['float_value'] = line
                    break
            
            # 4. Profit (+$x.xx or -$x.xx)
            for line in lines:
                profit_match = re.search(r'([+-]\$\d+(\.\d+)?)', line)
                if profit_match:
                    item_data['profit'] = profit_match.group(1)
                    break
            
            # 5. Profit Percentage ((xxx%) pattern)
            for line in lines:
                percent_match = re.search(r'\(\d+(\.\d+)?%\)', line)
                if percent_match:
                    item_data['profit_percentage'] = percent_match.group(0)
                    break
            
            # 6. Bid/Ask (Bid $x.xx | Ask $x.xx) or ($x.xx | $x.xx)
            for line in lines:
                bid_ask_match = re.search(r'(Bid \$\d+(\.\d{1,2})? \| Ask \$\d+(\.\d{1,2})?)', line)
                if bid_ask_match:
                    item_data['bid_ask'] = bid_ask_match.group(1)
                    break
                else:
                    dollar_pipe_match = re.search(r'(\$\d+(\.\d{1,2})? \| \$\d+(\.\d{1,2})?)', line)
                    if dollar_pipe_match:
                        item_data['bid_ask'] = dollar_pipe_match.group(1)
                        break

            parsed_items.append(item_data)
        
        return parsed_items

    def convert_scraped_to_json(self):
        """Convert scraped text to JSON with proper file handling."""
        try:
            scraped_text_path = os.path.join(os.path.dirname(__file__), SCRAPED_TEXT_FILE)
            scraped_json_path = os.path.join(os.path.dirname(__file__), SCRAPED_JSON_FILE)
            
            # Wait for text file to exist and have content
            for _ in range(10):
                if os.path.exists(scraped_text_path) and os.path.getsize(scraped_text_path) > 0:
                    break
                time.sleep(0.5)
            
            with open(scraped_text_path, 'r', encoding='utf-8') as f:
                text_data = f.read()

            parsed_data = self.parse_csfloat_data(text_data)

            # Write to temporary file first
            temp_path = scraped_json_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename
            os.replace(temp_path, scraped_json_path)

            print(f"\n✅ Successfully converted scraped data to JSON")
            print(f"📁 Output saved to {scraped_json_path}")
            print(f"Parsed {len(parsed_data)} items")
                
        except Exception as e:
            print(f"❌ Error converting scraped data: {str(e)}")
            raise  # Re-raise to see full traceback


    def extract_fields(self, input_file, output_file):
        """
        Extracts specific fields from CSFloat API data and saves to a new JSON file.
        Adds a URL formed from the item 'id'.
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            extracted_data = []
            for item in data.get('data', []):
                item_id = item.get('id')
                if not item_id:
                    continue

                item_url = f"https://csfloat.com/item/{item_id}"
                
                extracted_item = {
                    "id": item_id,
                    "price": item.get('price'),
                    "market_hash_name": item.get('item', {}).get('item_name'),
                    "wear_name": item.get('item', {}).get('wear_name'),
                    "base_price": item.get('reference', {}).get('base_price'),
                    "predicted_price": item.get('reference', {}).get('predicted_price'),
                    "float_value": item.get('item', {}).get('float_value'),
                    "url": item_url
                }
                
                if all(extracted_item.values()):
                    extracted_data.append(extracted_item)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            print(f"✅ Successfully extracted {len(extracted_data)} items to {output_file}")
            return True
            
        except FileNotFoundError:
            print(f"❌ Error: Input file '{input_file}' not found")
            return False
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON in file '{input_file}'")
            return False
        except Exception as e:
            print(f"❌ An unexpected error occurred: {str(e)}")
            return False

    @staticmethod
    def load_json(file_path):
        """Robust JSON loading with file locking"""
        import fcntl
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not os.path.exists(file_path):
                    return []
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Try to get a shared lock (non-blocking)
                    try:
                        fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    except (IOError, BlockingIOError):
                        if attempt == max_retries - 1:
                            print(f"Could not lock file {file_path} after {max_retries} attempts")
                            return []
                        time.sleep(0.5)
                        continue
                        
                    try:
                        data = json.load(f)
                        return data if isinstance(data, list) else [data]
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            except json.JSONDecodeError as e:
                if attempt == max_retries - 1:
                    print(f"Failed to decode {file_path} after {max_retries} attempts")
                    return []
                time.sleep(0.5)
            except Exception as e:
                print(f"Unexpected error loading {file_path}: {str(e)}")
                return []
            
    def save_merged_data(self, data, output_path):
        """Save merged data to JSON file with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                print(f"💾 Merged data saved to {output_path}")

                # ✅ Call the function here after successful save
                create_negative_profit_file(output_path)


                return
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"❌ Failed to save {output_path} after {max_retries} attempts: {e}")
                time.sleep(0.5)

    def load_json(self, filepath):
        """Load JSON data from file with retries."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if filepath == CLIENT_SETTINGS_FILE and not os.path.exists(filepath):
                    with open(filepath, 'w') as f:
                        json.dump({
                            'min_price': 10.0,
                            'max_price': 5000.0,
                            'min_profit': 0.00005,
                            'platform_fee': 0.00
                        }, f, indent=4)
                    return {
                        'min_price': 10.0,
                        'max_price': 5000.0,
                        'min_profit': 0.00005,
                        'platform_fee': 0.00
                    }
                
                with open(filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                
                if attempt == max_retries - 1:
                    return []
                time.sleep(0.5)

    def save_json(self, data, filepath):
        """Save JSON data to file with retries."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"❌ Failed to save {filepath} after {max_retries} attempts: {e}")
                time.sleep(0.5)

    
    
    

    def stop(self):
        self.running = False

class DealCard(QFrame):
    def __init__(self, deal):
        super().__init__()
        self.deal = deal
        self.init_ui()

    def init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            background-color: #222; 
            color: white; 
            border-radius: 10px; 
            padding: 10px;
            margin: 5px;
            height:20%;
            font-size: 16px;
        """)
        layout = QVBoxLayout()

        name = QLabel(f"Item Name : {self.deal.get('market_hash_name', 'Unknown')}")
        name.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(name)

        wear = QLabel(f"Wear Name : {self.deal.get('wear_name', 'Unknown')}")
        layout.addWidget(wear)

        # Base price and predicted price
        base_price = self.deal.get('base_price', 0)
        predicted_price = self.deal.get('predicted_price', 0)
        
        base_price_label = QLabel(f"Base Price : ${base_price:.2f}   Predicted Price: ${predicted_price:.2f}")
        layout.addWidget(base_price_label)

        # Current price
        try:
            price = float(self.deal.get('price', 0))
            price_label = QLabel(f"Price : ${price:.2f}")
        except (ValueError, TypeError):
            price_label = QLabel("Price : N/A")
        layout.addWidget(price_label)

        # Original profit display
        original_profit = self.deal.get('profit', '$0')
        profit_percent= self.deal.get('profit_percent')
        original_profit_label = QLabel(f"BetterFloats Profit : {original_profit} {profit_percent}")
        layout.addWidget(original_profit_label)

        # Profit after fees calculation and display
        try:
            # Load platform fee from settings
            settings = self.load_settings()
            platform_fee = float(settings.get('platform_fee', 0.00))
            
            # Calculate profit after fee
            profit_str = original_profit.replace('$', '').replace(',', '').replace('+', '').replace('-','')
            profit_value = float(profit_str)
            profit_after_fee = profit_value - platform_fee
            
            # Format display
            if profit_after_fee >= 0:
                profit_display = f"+${profit_after_fee:.2f}"
                profit_color = "#4CAF50"  # Green
            else:
                profit_display = f"-${abs(profit_after_fee):.2f}"
                profit_color = "#4CAF50"  # Red
                
            
            profit_label = QLabel(f"Profit After Minus Plateform Fee : <span style='color:{profit_color}'>{profit_display}</span>")
            profit_label.setTextFormat(Qt.TextFormat.RichText)
            
            
            layout.addWidget(profit_label)
         
            
        except (ValueError, TypeError) as e:
            print(f"Error calculating profit: {e}")
            profit_label = QLabel("Profit After Fees : N/A")
            layout.addWidget(profit_label)
        
        bid_ask = QLabel(f"{self.deal.get('bid_ask', 'Unknown')}")
        layout.addWidget(bid_ask)
        
        # Float value
        try:
            float_value = float(self.deal.get('float_value', 0))
            float_label = QLabel(f"Float Value : {float_value:.6f}")
        except (ValueError, TypeError):
            float_label = QLabel("Float : N/A")
        layout.addWidget(float_label)
        
        timestamp = QLabel(f"Listed Time : {datetime.fromisoformat(self.deal['timestamp']).strftime('%H:%M:%S')}")
        timestamp.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(timestamp)
        
        buy_button = QPushButton("Buy Now")
        buy_button.setStyleSheet("""
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            padding: 8px;
            border-radius: 5px;
        """)
        buy_button.clicked.connect(self.open_link)
        layout.addWidget(buy_button)

        self.setLayout(layout)

    def load_settings(self):
        """Helper method to load settings from file"""
        try:
            if not os.path.exists(SETTINGS_FILE):
                return {'platform_fee': 0.00}
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'platform_fee': 0.00}

    def open_link(self):
        url = self.deal.get('url')
        if url:
            webbrowser.open(url)
      
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Settings")
        self.setStyleSheet("""
            background-color: #222;
            color: white;
            margin-top: 20px;
        """)
        self.resize(400, 300)

        layout = QFormLayout()

        # Load current settings
        self.settings = self.load_settings()

        # Create editable fields
        self.min_price_edit = QLineEdit(str(self.settings.get('min_price', 0.0)))
        self.max_price_edit = QLineEdit(str(self.settings.get('max_price', 5000.0)))
        self.min_profit_edit = QLineEdit(str(self.settings.get('min_profit', 0.00005)))
        self.platform_fee_edit = QLineEdit(str(self.settings.get('platform_fee', 0.00)))

        # Style the input fields
        input_style = """
            background-color: #333;
            color: white;
            padding: 8px;
            margin-top: 20px;
            border: 1px solid #444;
            border-radius: 4px;
        """
        self.min_price_edit.setStyleSheet(input_style)
        self.max_price_edit.setStyleSheet(input_style)
        self.min_profit_edit.setStyleSheet(input_style)
        self.platform_fee_edit.setStyleSheet(input_style)

        layout.addRow("Min Price:", self.min_price_edit)
        layout.addRow("Max Price:", self.max_price_edit)
        layout.addRow("Min Profit:", self.min_profit_edit)
        layout.addRow("Platform Fee:", self.platform_fee_edit)

        # Save button
        save_button = QPushButton("Save Settings")
        save_button.setStyleSheet("""
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            margin-top: 30px;
            padding: 10px;
            border-radius: 5px;
        """)
        save_button.clicked.connect(self.save_settings)
        layout.addRow(save_button)

        self.setLayout(layout)

    def load_settings(self):
        try:
            if not os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump({
                        'min_price': 10.0,
                        'max_price': 5000.0,
                        'min_profit': 0.00005,
                        'platform_fee': 0.00
                    }, f, indent=4)
                return {
                    'min_price': 10.0,
                    'max_price': 5000.0,
                    'min_profit': 0.00005,
                    'platform_fee': 0.00
                }
            else:
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'min_price': 0.0,
                'max_price': 5000.0,
                'min_profit': 0.00005,
                'platform_fee': 0.00
            }

    def save_settings(self):
        try:
            updated_settings = {
                "min_price": float(self.min_price_edit.text()),
                "max_price": float(self.max_price_edit.text()),
                "min_profit": float(self.min_profit_edit.text()),
                "platform_fee": float(self.platform_fee_edit.text())
            }
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(updated_settings, f, indent=4)
            self.accept()
        except ValueError:
            print("Error: Please enter valid numbers for all settings")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.last_seen_id = None
        self.scraper_thread = None
        self.previous_deal_ids = set()  # Initialize empty set for tracking deals
        self.is_first_load = True  # Add this flag

        # Window setup
        self.setWindowTitle("CS:GO Deal Finder")
        self.resize(900, 600)
        self.setStyleSheet("background-color: #111; color: white;")

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Menu bar
        menu_bar = QHBoxLayout()
        menu_bar.setSpacing(10)
        
        # Settings button
        settings_button = QPushButton("Settings (Ctrl+S)")
        settings_button.setStyleSheet("""
            QPushButton {
                background-color: #5b4caf;  /* Purple primary color */
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6a5acd;  /* Lighter purple on hover */
            }
        """)
        settings_button.clicked.connect(self.open_settings_dialog)
        menu_bar.addWidget(settings_button)
        
        self.conditions_button = QPushButton("Apply Conditions")
        self.conditions_button.setStyleSheet("""
            QPushButton {
                background-color: #808080;  /* Orange */
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color:  #A9A9A9;  /* Darker orange */
            }
        """)
        self.conditions_button.clicked.connect(self.toggle_conditions)
        menu_bar.addWidget(self.conditions_button)

        # Start/Stop button
        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;  /* Green */
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;  /* Darker green */
            }
        """)
        self.start_stop_button.clicked.connect(self.toggle_scraper)
        menu_bar.addWidget(self.start_stop_button)
        

        
        menu_bar.addStretch()
        main_layout.addLayout(menu_bar)

        # Content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # Left scroll area (all deals)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setSpacing(10)
        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #333;
                border-radius: 5px;
                
            }
        """)

        # Right panel (newest deal)
        self.newest_deal_frame = QFrame()
        self.newest_deal_frame.setFixedWidth(400)
        self.newest_deal_frame.setStyleSheet("""
            background-color: #222;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 10px;
        """)
        self.newest_deal_layout = QVBoxLayout()
        self.newest_deal_layout.setSpacing(10)
        self.newest_deal_frame.setLayout(self.newest_deal_layout)
        
        # Improved "no deals" message
        self.no_deals_container = QWidget()
        no_deals_layout = QVBoxLayout()
        no_deals_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.no_deals_label = QLabel("""
            <div style='text-align:center;'>
                <p style='font-size:24px; color:#666;'>🔍 No deals found</p>
                <p style='font-size:14px; color:#444;'>
                    Waiting for new deals that match your criteria...
                </p>
            </div>
        """)
        self.no_deals_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        no_deals_layout.addWidget(self.no_deals_label)
        self.no_deals_container.setLayout(no_deals_layout)
        
        self.scroll_layout.addWidget(self.no_deals_container)
        self.no_deals_container.hide()

        content_layout.addWidget(self.scroll_area, stretch=3)
        content_layout.addWidget(self.newest_deal_frame, stretch=1)
        main_layout.addLayout(content_layout, stretch=1)

        self.setLayout(main_layout)

        # Start auto-refresh
        self.start_updater()
        # Start the scraper thread
        self.start_scraper()
        
        # Force initial refresh
        QTimer.singleShot(100, self.refresh_deals)
        
        if self.scraper_thread:
            
            self.scraper_thread.signals.scraping_complete.connect(self.refresh_deals)

    def refresh_deals(self, apply_conditions=False):
        try:
            # Check if file exists and is not empty
            if not os.path.exists('profit_deals.json') or os.path.getsize('profit_deals.json') == 0:
                self.no_deals_container.show()
                return
                
            with open('profit_deals.json', 'r', encoding='utf-8') as f:
                deals = json.load(f)
            
            if not isinstance(deals, list):
                print("Error: profit_deals.json does not contain a list")
                self.no_deals_container.show()
                return
                
            if apply_conditions and self.conditions_button.text() == "Remove Conditions":
                self.apply_conditions()
            else:
                self.update_deals_display(deals)
                
        except json.JSONDecodeError:
            print("Error: Could not decode profit_deals.json")
            self.no_deals_container.show()
        except Exception as e:
            print(f"Error refreshing deals: {e}")
            self.no_deals_container.show()

    def update_deals_display(self, deals):
        # Clear old widgets
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget and widget != self.no_deals_container:
                widget.setParent(None)

        if deals:
            self.no_deals_container.hide()
            
            # Track new deals
            new_deals_for_sound = []
            current_ids = {deal['id'] for deal in deals}
            
            if hasattr(self, 'previous_deal_ids'):
                new_deals_for_sound = [deal for deal in deals 
                                    if deal['id'] not in self.previous_deal_ids]
            
            self.previous_deal_ids = current_ids

            # Add all deals to UI (sorted by timestamp descending)
            for deal in sorted(deals, key=lambda x: x.get('timestamp', ''), reverse=True):
                card = DealCard(deal)
                self.scroll_layout.addWidget(card)

            # Show newest deal if available
            if new_deals_for_sound:
                newest_deal = max(new_deals_for_sound, key=lambda x: x.get('timestamp', ''))
                self.show_newest_deal(newest_deal)
                if not self.is_first_load:
                    speak(f"New deal found: {newest_deal.get('market_hash_name', 'Unknown')}")
            
            self.is_first_load = False
        else:
            self.no_deals_container.show()
            for i in reversed(range(self.newest_deal_layout.count())):
                widget = self.newest_deal_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
                        
    def toggle_scraper(self):
        if hasattr(self.scraper_thread, 'running') and self.scraper_thread.running:
            # Stop the current scraper
            self.scraper_thread.stop()
            self.start_stop_button.setText("Start")
            self.start_stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50; /* green */
                    color: white;
                    padding: 8px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;  /* Darker green */
                }
            """)
            print("Scraper stopped")
        else:
            # Create a new scraper thread if needed
            if not hasattr(self.scraper_thread, 'running') or not self.scraper_thread.is_alive():
                self.scraper_thread = ScraperThread()
                #self.scraper_thread.signals.scraping_complete.connect(self.refresh_deals)

            # Start the scraper
            self.scraper_thread.running = True
            if not self.scraper_thread.is_alive():
                self.scraper_thread.start()
            self.start_stop_button.setText("Stop")
            self.start_stop_button.setStyleSheet("""
            QPushButton {
                    background-color: #f44336; /* green */
                    color: white;
                    padding: 8px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d32f2f;  /* Darker green */
                }
            """)
            print("Scraper started")
            
    def toggle_conditions(self):
        # Toggle between applying and removing conditions
        if self.conditions_button.text() == "Apply Conditions":
            self.apply_conditions()
            self.conditions_button.setText("Remove Conditions")
            self.conditions_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;  /* Blue */
                    color: white;
                    padding: 8px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0b7dda;  /* Darker blue */
                }
            """)
        else:
            self.refresh_deals()  # Refresh without conditions
            self.conditions_button.setText("Apply Conditions")
            self.conditions_button.setStyleSheet("""
            QPushButton {
                background-color: #808080;  /* Orange */
                color: white;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color:  #A9A9A9;  /* Darker orange */
            }
        """)
    def apply_conditions(self):
        try:
            # Load current settings
            with open('bot_settings.json', 'r') as f:
                settings = json.load(f)
            
            # Load all deals
            with open('profit_deals.json', 'r', encoding='utf-8') as f:
                all_deals = json.load(f)
            
            # Apply filtering conditions
            filtered_deals = []
            for deal in all_deals:
                try:
                    # Remove $ and - signs for calculation but keep original for display
                    original_profit = deal.get('profit', '$0')
                    profit_str = original_profit.replace('$', '').replace('-', '').replace(',', '')
                    profit = float(profit_str)
                    
                    # Get price (ensure it's float)
                    price = float(deal.get('price', 0))
                    
                    # Apply platform fee (subtract from profit)
                    profit_after_fee = profit - float(settings.get('platform_fee', 0))
                    
                    # Check all conditions
                    min_price = float(settings.get('min_price', 0))
                    max_price = float(settings.get('max_price', float('inf')))
                    min_profit = float(settings.get('min_profit', 0))
                    
                    if (price >= min_price and 
                        price <= max_price and 
                        profit_after_fee >= min_profit):
                        # Keep original profit string in the deal
                        filtered_deals.append(deal)
                        
                except (ValueError, TypeError) as e:
                    print(f"Error processing deal {deal.get('id')}: {e}")
                    continue
            
            # Update UI with filtered deals
            self.update_deals_display(filtered_deals)
            
        except Exception as e:
            print(f"Error applying conditions: {e}")
            self.no_deals_container.show()
            
            
    def start_scraper(self):
        if not hasattr(self, 'scraper_thread') or self.scraper_thread is None:
            self.scraper_thread = ScraperThread()
            #elf.scraper_thread.signals.scraping_complete.connect(self.refresh_deals)
            self.scraper_thread.running = False
        self.start_stop_button.setText("Start")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts manually"""
        # Ctrl+S for settings
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_S:
            self.open_settings_dialog()
        # F5 for refresh
        elif event.key() == Qt.Key.Key_F5:
            pass
            #self.refresh_deals()
        else:
            super().keyPressEvent(event)

    
    def show_newest_deal(self, deal):
        # Clear previous newest deal
        for i in reversed(range(self.newest_deal_layout.count())):
            widget = self.newest_deal_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Create a container frame with enhanced styling
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #333;
                border: 3px solid #5b4caf;
                border-radius: 12px;
                padding: 5px;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        
        # Create the deal card
        card = DealCard(deal)
        card.setStyleSheet("""
            background-color: transparent;
            color: white;
            border: none;
            padding: 0;
            font-size: 16px;
            
        """)
        
        # Add the card to the container
        container_layout.addWidget(card)
        
        # Add some decorative elements
        header = QLabel("✨ HOT DEAL ✨")
        header.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-weight: bold;
                font-size: 16px;
                qproperty-alignment: AlignCenter;
                padding-bottom: 8px;
                border-bottom: 1px solid #4CAF50;
                margin-bottom: 55px;
            }
        """)
        
        footer = QLabel("Check this deal!")
        footer.setStyleSheet("""
            QLabel {
                color: #aaa;
                font-size: 12px;
                qproperty-alignment: AlignCenter;
                padding-top: 2px;
                border-top: 1px solid #4CAF50;
                margin-top: 55px;
            }
        """)
        
        container_layout.insertWidget(0, header)
        container_layout.addWidget(footer)
        
        # Add the container to the layout
        self.newest_deal_layout.addWidget(container)
    
    def start_updater(self):
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.refresh_deals(
            self.conditions_button.text() == "Remove Conditions"
        ))
        self.timer.start(5000)  # 5 seconds
        
    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        """Clean up when window is closed"""
        if self.scraper_thread:
            self.scraper_thread.stop()
            self.scraper_thread.join()
        super().closeEvent(event)

if __name__ == "__main__":
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Initialize Qt application first
    app = QApplication(sys.argv)
    
    # Set dark theme style
    app.setStyleSheet("""
        QWidget {
            font-family: Arial;
        }
        QPushButton:hover {
            background-color: #555;
        }
    """)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Initialize processor (this should likely be part of your MainWindow)
    processor = CSFloatDataProcessor()
    
    sys.exit(app.exec())