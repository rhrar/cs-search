from flask import Flask, render_template, request, send_file
import requests
import pandas as pd
from io import StringIO, BytesIO
import json
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Store the last search results in memory
last_search_results = None

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    global last_search_results
    api_key = os.getenv('RARIBLE_API_KEY')
    if not api_key:
        return render_template('error.html', error="API key not found in environment variables")
        
    search_text = request.form.get('search_text')
    search_field = request.form.get('search_field', 'NAME')  # Default to NAME if not specified
    
    url = "https://api.rarible.org/v0.1/items/search"
    headers = {
        "X-API-KEY": api_key,
        "accept": "application/json",
        "content-type": "application/json"
    }
    
    payload = {
        "size": 50,  # Limit to 50 items for better performance
        "filter": {
            "deleted": False,
            "fullText": {
                "fields": [search_field],
                "text": f'"{search_text}"'
            }
        },
        "traitSort": {
            "order": "ASC",
            "type": "TEXT",
            "key": search_field
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Convert response to DataFrame
        data = response.json()
        print("API Response:", json.dumps(data, indent=2))  # Debug print
        
        if not isinstance(data, dict):
            return render_template('error.html', error="Invalid API response format")
            
        items = data.get('items', [])
        if not isinstance(items, list):
            return render_template('error.html', error="Items not found in response")
        
        # Extract relevant fields for display
        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
                
            try:
                # Extract collection data
                collection_data = item.get('collection', '')
                collection_id = collection_data if isinstance(collection_data, str) else ''
                
                # Make additional API call to get collection details
                if collection_id:
                    collection_url = f"https://api.rarible.org/v0.1/collections/{collection_id}"
                    try:
                        collection_response = requests.get(collection_url, headers=headers)
                        collection_info = collection_response.json()
                        collection_name = collection_info.get('name', '')
                    except:
                        collection_name = ''
                else:
                    collection_name = ''
                
                # Extract meta data
                meta = item.get('meta', {})
                if isinstance(meta, dict):
                    item_name = meta.get('name', '')
                    item_description = meta.get('description', '')
                else:
                    item_name = ''
                    item_description = ''
                
                # Extract and format dates
                minted_at = item.get('mintedAt', '')
                updated_at = item.get('lastUpdatedAt', '') or item.get('dbUpdatedAt', '') or item.get('updatedAt', '')
                
                # Extract ID (could be in different formats)
                item_id = str(item.get('id', '') or item.get('_id', '') or item.get('itemId', ''))
                
                row = {
                    'ID': item_id,
                    'Item Name': str(item_name),
                    'Item Description': str(item_description),
                    'Verified': bool(item.get('verified', False)),
                    'Blacklisted': bool(item.get('blacklisted', False)),
                    'Deleted': bool(item.get('deleted', False)),
                    'Blockchain': str(item.get('blockchain', '')),
                    'Hide': bool(item.get('hide', False)),
                    'Minted At': str(minted_at),
                    'Suspicious': bool(item.get('suspicious', False)),
                    'Collection ID': str(collection_id),
                    'Collection Name': str(collection_name),
                    'Updated Date': str(updated_at)
                }
                rows.append(row)
            except Exception as e:
                print(f"Error processing item: {e}")  # Debug print
                continue
        
        if not rows:
            return render_template('error.html', error="No valid items found in response")
            
        df = pd.DataFrame(rows)
        last_search_results = df  # Store results for CSV download
        
        # Convert DataFrame to HTML table
        table_html = df.to_html(classes='table table-striped', index=False)
        return render_template('results.html', table=table_html)
    
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug print
        return render_template('error.html', error=str(e))

@app.route('/download_csv')
def download_csv():
    global last_search_results
    if last_search_results is None:
        return "No search results available", 404
        
    # Create a buffer
    buffer = BytesIO()
    # Write DataFrame to CSV
    last_search_results.to_csv(buffer, index=False, encoding='utf-8')
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'rarible_search_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 