import requests
import json
import keepa       # Use the Keepa API wrapper for python:  https://keepaapi.readthedocs.io/en/latest/api_methods.html#ref-api-methods
import dotenv
dotenv.load_dotenv()
import os

# API Key loaded from .env file
try:
    API_KEY = os.environ['KEEPA_API_KEY']
except:
    API_KEY = "YOUR_API_KEY"

print(f"API Key: {API_KEY}")

api = keepa.Keepa(API_KEY)


SEARCH_QUERY = 'Weber'  # Basically look for weber grills.
NUM_PRODUCTS_TO_FETCH = 500 # 500
PRICE_SPREAD = 5

# Define helper functions

def get_product_data(asin, domain):
    """
    Fetches product data from the Keepa API.

    Parameters:
    asin (str): The ASIN (Amazon Standard Identification Number) of the product.
    domain (str): The domain of the product (e.g., 'com', 'co.uk', 'de', etc.).

    Returns:
    dict: A dictionary containing the product data returned by the Keepa API.
          If there is an error fetching the data, None is returned.

    """
    url = f'https://api.keepa.com/product?key={API_KEY}&domain={domain}&asin={asin}'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data for {asin} from domain {domain}: {response.status_code}")
        print(response.text)
        return None

def extract_current_price(data):
    try:
        product = data['products'][0]
        new_price_history = product.get('csv', [])[1]
        if new_price_history is None or len(new_price_history) == 0:
            print(f"No price history available for ASIN: {product.get('asin', 'unknown')}")
            return None
        latest_price = new_price_history[-1]
        return latest_price / 100
    except (IndexError, KeyError, TypeError) as e:
        print(f"Error extracting current price: {e}")
        return None

def extract_product_info(data, purchase_price, sale_price, roi, sales_per_month):
    try:
        product = data['products'][0]
        return {
            'ASIN': product['asin'],
            'Purchase Price': purchase_price,
            'Sale Price': sale_price,
            'ROI': roi,
            'Sales Per Month': sales_per_month,
            'Purchase Link': f"https://www.amazon.co.uk/dp/{product['asin']}",
            'Keepa Link': f"https://keepa.com/#!product/2-{product['asin']}"
        }
    except (IndexError, KeyError) as e:
        print(f"Error extracting product info: {e}")
        return None

def compare_prices(uk_price, eu_price):
    return uk_price > (eu_price + PRICE_SPREAD)

marketplaces = {
    'UK': 2,
    'DE': 3,
    'FR': 4,
    'IT': 8,
    'ES': 9
}

def fetch_asins_from_keyword(keyword, domain=2):
    '''
    Title of the product. 
    Works on a keyword basis, meaning the product’s title must contain the specified string’s keywords, separated by white space. 
    Supports up to 50 keywords. The search is case-insensitive. Partial keyword matches are not supported.
    https://keepa.com/#!discuss/t/product-finder/5
    '''

    product_parms = {'title': keyword}
    # https://keepaapi.readthedocs.io/en/latest/api_methods.html#ref-api-methods
    # domain (str, default: 'US') – One of the following Amazon domains: RESERVED, US, GB, DE, FR, JP, CA, CN, IT, ES, IN, MX.
    products = api.product_finder(product_parms, domain='GB', wait=True)
    
    print(f"Products: {products}")
    if products:
        return products

    else:
        print(f"Error fetching data for {asin} from domain {domain}.  Giving up.")
        quit()


# Main script
print("Starting the script...")
asins = fetch_asins_from_keyword(SEARCH_QUERY)[:NUM_PRODUCTS_TO_FETCH]  # Fetches the first NUM_PRODUCTS_TO_FETCH ASINs  
print(f"Fetched {len(asins)} ASINs")
selected_products = []

# asins = ['B01IF1HJAO', 'B0020K966M']  # Testing a known good ASIN.  Uncomment this to test out an ASIN that was fitting the bill. .

for asin in asins:
    print(f"Processing ASIN: {asin}")
    uk_data = get_product_data(asin, marketplaces['UK'])
    if not uk_data:
        print(f"Failed to fetch UK data for ASIN: {asin}")
        continue

    uk_price = extract_current_price(uk_data)
    print(f"UK Price: {uk_price}")
    if not uk_price:
        print(f"Failed to extract UK price for ASIN: {asin}")
        continue

    product_info = {}
    product_info["Buy box"] = uk_price
    product_info["Sale Price"] = uk_price * 1.2
    product_info["ROI"] = (product_info["Sale Price"] - uk_price) / uk_price * 100
    product_info["Sales Per Month"] = uk_data['products'][0].get('salesRank', {}).get('current', None)
    product_info["Purchase Link"] = f"https://www.amazon.co.uk/dp/{asin}"
    product_info["Keepa Link"] = f"https://keepa.com/#!product/2-{asin}"

    for market, domain in marketplaces.items():
        if market == 'UK':
            continue

        eu_data = get_product_data(asin, domain)
        if not eu_data:
            print(f"Failed to fetch data for ASIN: {asin} in market: {market}")
            continue

        eu_price = extract_current_price(eu_data)
        if not eu_price or eu_price == -0.01:
            print(f"Failed to extract price for ASIN: {asin} in market: {market}")
            continue
        print(f"{market} Price: {eu_price}")
        if compare_prices(uk_price, eu_price):
            print(f"Found a product with a significant price difference between UK and {market}: {asin}")
            try:
                product_info["Market"][market] = eu_price
            except KeyError:
                product_info["Market"] = {market: eu_price}

    try:
        if product_info["Market"]:
            selected_products.append(product_info)
    except KeyError:
        pass


selected_products_path = f'selected_products_{SEARCH_QUERY}.json'

with open(selected_products_path, 'w') as f:
    json.dump(selected_products, f, indent=4)

print("Selected products with significant price differences:")
for product in selected_products:
    print(json.dumps(product, indent=4))
