from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
# Since the updating is completed for google sheet, change scope to read only
# SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


# Google sheet ID
SPREADSHEET_ID = '1dL2V0_ne4j-y0_ZVU4Mm4B_C_O0qoGpd34yHzs99U3s'

TITLE_LIST = ['Video ID',
              'Video URL',
              'Video Title',
              'Video Language',
              'Description']

class RefugeeResponseDescriptionRecord():
    video_id = ''
    video_title = ''
    video_url = ''
    description = ''
    video_language = ''

    def __init__(self, id, url, description,language, title = ''):
        self.video_id = id
        self.video_url = url
        self.description = description
        self.video_title = title
        self.video_language = language

class RefugeeResponseSheetWriter():
    spreadsheet_id = ''
    sheet_service = None
    creds = None
    titled = False

    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        if os.path.exists('token.pickle'):
            try:
                token = open('token.pickle', 'rb')
                self.creds = pickle.load(token)
            except Exception as e:
                print("Failed to get credentials, try user log in")
                
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    './.credential/credentials.json', SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)

        service = build('sheets', 'v4', credentials=self.creds)
        self.sheet_service = service.spreadsheets()

        if self.title_exist():
            self.titled = True

    def clear_old_records(self, range_str):
        body = {}
        clear_response = self.sheet_service.values().clear(
            spreadsheetId=self.spreadsheet_id,
            range=range_str,
            body=body).execute()

    def add_title_line(self):
        values = [
            TITLE_LIST
        ]
        body = {
            "majorDimension": "ROWS",
            'values': values
        }
        range = "Sheet1!A:A"
        response = self.sheet_service.values().append(
            spreadsheetId=self.spreadsheet_id, range=range,
            valueInputOption="USER_ENTERED", body=body).execute()
        self.titled = True
        print("title range: {0}".format(response.get('tableRange')))

    def title_exist(self):
        range = "Sheet1!A1"
        result = self.sheet_service.values().get(
            spreadsheetId=self.spreadsheet_id, range=range).execute()
        values = result.get('values', [])
        if not values:
            return False
        else:
            title_value = values[0][0]
            if TITLE_LIST[0] in title_value:
                return True
            else:
                raise Exception("Invalid google sheet format found!")
        return False


    def write_description_record(self, description_record):
        if not self.titled:
            self.add_title_line()

        values = [
            [
                description_record.video_id,
                description_record.video_url,
                description_record.video_title,
                description_record.video_language,
                description_record.description
            ]
        ]
        body = {
            "majorDimension": "ROWS",
            'values': values
        }
        range = "Sheet1!A:A"

        response = self.sheet_service.values().append(
            spreadsheetId=self.spreadsheet_id, range=range,
            valueInputOption="USER_ENTERED", body=body).execute()
