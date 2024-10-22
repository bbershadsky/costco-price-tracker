import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import logging
import time
import urllib3
import http.client as http_client

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Enable HTTP debugging if needed
# http_client.HTTPConnection.debuglevel = 1

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# URL of the product page
URL = 'https://www.costco.ca/northfork-meats-elk-ground-meat-454-g-1-lb-x-10-pack.product.100571433.html'

# Function to fetch the webpage content
def fetch_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                      ' Chrome/94.0.4606.61 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        logger.debug('Successfully fetched the page content.')
        return response.text
    except Exception as e:
        logger.error(f'Error fetching the page: {e}')
        return None

# Function to parse the adobeProductData variable from JavaScript
def parse_adobe_product_data(soup):
    try:
        # Find all script tags
        scripts = soup.find_all('script')
        adobe_data_script = None

        # Search for the script containing 'var adobeProductData ='
        for script in scripts:
            if script.string and 'var adobeProductData =' in script.string:
                adobe_data_script = script.string
                break

        if not adobe_data_script:
            logger.error('Could not find the adobeProductData script.')
            return None

        # Extract 'priceTotal' value using regex
        price_match = re.search(r'priceTotal:\s*initialize\(([^)]+)\)', adobe_data_script)
        if price_match:
            price_str = price_match.group(1)
            # Remove quotes if present
            price_str = price_str.strip('\'"')
            price = float(price_str)
            logger.debug(f'Extracted price: {price}')
        else:
            logger.error('Could not extract priceTotal.')
            return None

        # Extract SKU
        sku_match = re.search(r'SKU:\s*initialize\(([^)]+)\)', adobe_data_script)
        if sku_match:
            sku = sku_match.group(1)
            sku = sku.strip('\'"')
            logger.debug(f'Extracted SKU: {sku}')
        else:
            logger.error('Could not extract SKU.')
            return None

        # Return a dictionary with the data
        adobe_product_data = {'priceTotal': price, 'SKU': sku}
        return adobe_product_data

    except Exception as e:
        logger.error(f'Error parsing adobeProductData: {e}')
        return None

# Function to extract the price from adobeProductData
def extract_price_from_adobe_data(adobe_data):
    try:
        price = adobe_data.get('priceTotal')
        product_id = adobe_data.get('SKU')
        logger.debug(f'Extracted price: {price}, Product ID: {product_id}')
        return price, product_id
    except Exception as e:
        logger.error(f'Error extracting price and product ID: {e}')
        return None, None

# Function to compare current price with previous price in the database
def compare_prices(product_id, current_price):
    conn = sqlite3.connect('prices.db')
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_prices (
            product_id TEXT PRIMARY KEY,
            price REAL,
            timestamp INTEGER
        )
    ''')
    conn.commit()

    # Fetch previous price
    cursor.execute('SELECT price FROM product_prices WHERE product_id = ?', (product_id,))
    row = cursor.fetchone()

    if row:
        previous_price = row[0]
        logger.debug(f'Previous price: {previous_price}')
        if current_price < previous_price:
            print('The product is on sale!')
        elif current_price == previous_price:
            print('The price has not changed.')
        else:
            print('The price has increased.')
    else:
        print('No previous price data to compare.')

    # Update the database with the current price
    current_timestamp = int(time.time())
    cursor.execute('''
        INSERT OR REPLACE INTO product_prices (product_id, price, timestamp)
        VALUES (?, ?, ?)
    ''', (product_id, current_price, current_timestamp))
    conn.commit()
    conn.close()
    logger.debug('Database updated with current price.')

# Main script execution
def main():
    html_content = fetch_page(URL)
    if not html_content:
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    # Parse the adobeProductData from the script
    adobe_product_data = parse_adobe_product_data(soup)
    if not adobe_product_data:
        return

    current_price, product_id = extract_price_from_adobe_data(adobe_product_data)
    if current_price is None or product_id is None:
        return

    compare_prices(product_id, current_price)

if __name__ == '__main__':
    main()
