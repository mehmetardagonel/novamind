# Gmail API Setup Instructions

## Issue
The Gmail API is not enabled for your Google Cloud project. You're seeing this error:
```
Gmail API has not been used in project 437464220214 before or it is disabled
```

## Solution: Enable Gmail API

### Step 1: Go to Google Cloud Console
Visit this direct link to enable the Gmail API for your project:
https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=437464220214

### Step 2: Click "Enable" Button
- You'll see a page titled "Gmail API"
- Click the blue "ENABLE" button

### Step 3: Wait a Few Minutes
- After enabling, wait 2-3 minutes for the changes to propagate
- Then refresh your Novamind.AI application

### Step 4: Test the Application
- Go back to http://localhost:5173
- Try accessing the Inbox or AI Assistant
- Emails should now load properly

## Alternative Method (If Direct Link Doesn't Work)

1. Go to https://console.cloud.google.com/
2. Select your project (ID: 437464220214)
3. Click on "APIs & Services" → "Library"
4. Search for "Gmail API"
5. Click on it and press "Enable"

## Note
You only need to do this once. The Gmail API will remain enabled for this project.
