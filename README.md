# Gmail Service -> Slack


This program will monitor a Google Apps gmail inbox and when it receives a new email, it will send you a notification on slack.

Forked from brooksc/gmail2slack and modified to use service account and run in docker container

We use this to push shared email accounts to slack.

Installation

1. `git clone https://github.com/gabeos/gmailservice2slack.git`
2. `docker build -t gmailservice2slack .`
3. Set environment variables as appropriate in docker-compose.yml | fig.yml
3. docker-compose up -d

## Configuration

### Create a Gmail Service Account & API Key
Next you'll need a Gmail service account and API Key

1. Obtain a google API key by visiting https://console.developers.google.com/project, create a project
2. Once created, select the project and enable the Gmail API
3. Under Oauth Select Create New Client ID
4. Select 'Service Account', click 'P12' for Key Type, and click 'Create Client ID'
5. Save the generated key (you only get it once) 
6. Decode the generated key (password is 'notasecret') : `openssl pkcs12 -in <downloaded key.p12> -nocerts -nodes >client.key`
7. Make sure the key is saved as 'client.key' in the cloned directory, or modify the docker-compose.yml to fix the mount

### Get a Slack API Key

Next, get a Slack API key.

1. Visit https://api.slack.com/
2. Sign in if you need to
3. Click Get Token

### Environment Variables for Docker

#### Necessary

* CLIENT_EMAIL: Listed on the google admin page when you created the service account as 'Email Address: ##...###-xxxxxxxx...xxx@developer.gserviceaccount.com'
* EMAIL: Email address of the account you're trying to access, e.g. 'mary@cs.whatever.com'
* SLACK_API_KEY: Slack API Key

and at least one of:

* SLACK_USER_ID: Slack user ID
* SLACK_USER: name of slack user to authenticate with, i.e. user that own API key

Note: SLACK_USER_ID takes precedence.

#### Optional

* GMAIL_LABEL: If you only want to post messages with a certain label, specify if here. Defaults to 'INBOX'
* DEBUG: Must be set to 'True' to enable debug output
* LOOP: Time between checking for new mail. Defaults to 60 seconds. Setting loop to `0` will make the program exit after a single run.
* SLACK_FROM: Name to use for slack post


