import requests
import sys

def list_dns_records(api_token, zone_id):
    url = f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records'

    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

    page = 1
    per_page = 100

    while True:
        try:
            params = {
                'page': page,
                'per_page': per_page
            }
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")
                sys.exit(1)

            data = response.json()
            if 'result' not in data or not isinstance(data['result'], list):
                print(f"Error: Unexpected response structure: {data}")
                sys.exit(1)

            records = data['result']
            if not records:
                break

            for record in records:
                print(f"Type: {record.get('type')}, Name: {record.get('name')}, Content: {record.get('content')}, ID: {record.get('id')}, TTL: {record.get('ttl')}, proxied: {record.get('proxied')}")

            if len(records) < per_page:
                break

            page += 1
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python list_dns_records.py <api_token> <zone_id>")
    else:
        api_token = sys.argv[1]
        zone_id = sys.argv[2]
        list_dns_records(api_token, zone_id)
