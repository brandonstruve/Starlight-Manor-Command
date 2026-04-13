import os.path
import csv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes and Paths
SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']
CREDENTIALS_PATH = r"C:\Starlight Manor Command\config\credentials\credentials.json"
TOKEN_PATH = r"C:\Starlight Manor Command\config\credentials\token.json"
OUTPUT_CSV = "google_contacts_with_ids.csv"

def extract_google_ids():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    service = build('people', 'v1', credentials=creds)

    print("🔄 Connecting to Google People API...")
    
    # Expanded personFields to include phoneNumbers and addresses
    results = service.people().connections().list(
        resourceName='people/me',
        pageSize=1000,
        personFields='names,birthdays,emailAddresses,phoneNumbers,addresses'
    ).execute()
    
    connections = results.get('connections', [])

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Google_ID', 'Full_Name', 'Birthday', 'Email', 'Phone', 'Address'])

        for person in connections:
            resource_name = person.get('resourceName')
            
            # Name
            names = person.get('names', [])
            full_name = names[0].get('displayName') if names else "Unknown"
            
            # Birthday (YYYY-MM-DD)
            birthdays = person.get('birthdays', [])
            bday_str = ""
            if birthdays:
                date = birthdays[0].get('date')
                if date:
                    y = date.get('year', 1900)
                    m = date.get('month', 1)
                    d = date.get('day', 1)
                    bday_str = f"{y}-{m:02d}-{d:02d}"
            
            # Primary Email
            emails = person.get('emailAddresses', [])
            primary_email = emails[0].get('value') if emails else ""

            # Primary Phone
            phones = person.get('phoneNumbers', [])
            primary_phone = phones[0].get('canonicalForm') or phones[0].get('value') if phones else ""

            # Primary Formatted Address
            addresses = person.get('addresses', [])
            formatted_address = addresses[0].get('formattedValue', '').replace('\n', ', ') if addresses else ""

            writer.writerow([resource_name, full_name, bday_str, primary_email, primary_phone, formatted_address])

    print(f"✅ Success! Created {OUTPUT_CSV} with {len(connections)} enriched records.")

if __name__ == '__main__':
    extract_google_ids()