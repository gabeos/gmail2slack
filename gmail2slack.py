#!/usr/bin/python
# -*- coding: utf-8 -*-

import pickle
import time
import traceback

import httplib2
import arrow
from oauth2client import tools
from oauth2client.client import SignedJWTAssertionCredentials
from oauth2client.file import Storage
from apiclient.discovery import build

from slacker import Slacker
import os
import sys
import argparse
from oauth2client.client import AccessTokenRefreshError

from yaml import load

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


class Gmail2Slack:

    def __init__(self, config, slack):
        self.slack = slack
        self.config = config

        # Check https://developers.google.com/admin-sdk/directory/v1/guides/authorizing for all available scopes

        OAUTH_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
        
        # Location of the credentials storage file

        # Start the OAuth flow to retrieve credentials
        credentials = SignedJWTAssertionCredentials(self.config['CLIENT_EMAIL'], self.config['CLIENT_KEY'], 
                OAUTH_SCOPE, sub=self.config['EMAIL'])
        http = credentials.authorize(httplib2.Http())
        
        # Build the Gmail service from discovery
        self.gmail_service = build('gmail', 'v1', http=http)
        self.user_id = 'me'
        self.label_name = self.config['GMAIL_LABEL']

        try:
            self.state = pickle.load(open(self.config['G2S_PICKLE'], 'rb'))
        except IOError:
            self.state = dict()
            self.state['timestamp'] = arrow.utcnow().timestamp

    def save_state(self):
        # Save timestamp so we don't process the same files again
        if self.config['DEBUG']:
            print 'DEBUG[ACT]: Saving State'
        self.state['timestamp'] = arrow.utcnow().timestamp
        pickle.dump(self.state, open(self.config['G2S_PICKLE'], 'wb'))

    def getLabelIdByName(self, name):
        if self.config['DEBUG']:
            print 'DEBUG[ACT]: Getting Label ID by Name'
        response = self.gmail_service.users().labels().list(userId=self.user_id).execute()
        if 'labels' in response:
            for label in response['labels']:
                if label['name'] == name:
                    return label['id']
        return None

    def gmail2slack(self):
        if self.config['DEBUG']:
            print 'DEBUG[ACT]: Gmail2Slack'

        try:
            label_id = self.getLabelIdByName(self.label_name)
            if not label_id:
                if self.config['DEBUG']:
                    print "DEBUG[STATE]: Couldn't find Label ID"
                raise Exception('target label name not found')
            response = self.gmail_service.users().messages().list(userId=self.user_id, labelIds=label_id).execute()
        except Error as err:
            if self.config['DEBUG']:
                print 'DEBUG[STATE]: Error = %s' % err
                print "DEBUG[STATE]: Error Content:\n%s" % err.content
            return

        message_ids = []
        if 'messages' in response:
            if self.config['DEBUG']:
                print 'DEBUG[STATE]: Found {0} messages in response'.format(len(response['messages']))
            message_ids.extend(response['messages'])
        for msg_id in message_ids:
            message = self.gmail_service.users().messages().get(userId=self.user_id, id=msg_id['id']).execute()
            headers = dict()
            for header in message['payload']['headers']:
                headers[header['name']] = header['value']

            try:  # due to issue @ https://github.com/crsmithdev/arrow/issues/176
                from_ts = arrow.get(headers['Date'], 'ddd, D MMM YYYY HH:mm:ss ZZ').timestamp
            except:
                continue

            if from_ts < self.state['timestamp']:
                break
            from_date = arrow.get(from_ts).to('US/Pacific').format('YYYY-MM-DD HH:mm:ss ZZ')
            say = '''New Email
>From: %s
>Date: %s
>Subject: %s
>
>%s''' % (headers['From'], from_date, headers['Subject'], message['snippet'])
            if self.config['DEBUG']:
                print 'DEBUG[STATE]: Message constructed.'
                print 'DEBUG[VAR]: Message: {0}'.format(say)
                print 'DEBUG[VAR]: Channel: {0}'.format(os.getenv('SLACK_CHANNEL', self.config['SLACK_USER_ID']))
                print 'DEBUG[VAR]: Slack From: {0}'.format(self.config['SLACK_FROM'])
            self.slack.post(os.getenv('SLACK_CHANNEL', self.config['SLACK_USER_ID']), say, self.config['SLACK_FROM'])
            if self.config['DEBUG']:
                print 'DEBUG[STATE]: Message Sent'
        self.save_state()


class Slack:

    def __init__(self, apikey):
        self.slack = Slacker(apikey)

    def get_name_id(self, name):
        users = self.slack.users.list()
        user_id = None
        for member in users.body['members']:
            if member['name'] == name:
                user_id = member['id']
                break
        return user_id

    def post(
        self,
        channel,
        message,
        slack_from,
        ):
        self.slack.chat.post_message(channel, message, username=slack_from)


def main():

    config = {
        'STORAGE_PATH': '/usr/src/app',
        'LOOP': os.getenv('LOOP', 60),
        'GMAIL_LABEL': os.getenv('GMAIL_LABEL', 'INBOX'),
        'SLACK_FROM': os.getenv('SLACK_FROM', 'gmail2slack'),
        'EMAIL': os.getenv('EMAIL'),
        'CLIENT_EMAIL' : os.getenv('CLIENT_EMAIL')
        }
    config['DEBUG'] = 'DEBUG' in os.environ and os.environ['DEBUG'] == 'True'
    config['G2S_PICKLE'] = os.path.join(config['STORAGE_PATH'], 'g2s.pickle')
    
    with open(os.path.join(config['STORAGE_PATH'], 'client.key')) as f:
        config['CLIENT_KEY'] = f.read()

    if not 'SLACK_API_KEY' in os.environ:
        sys.exit('Must declare SLACK_API_KEY through environment')
    config['SLACK_API_KEY'] = os.getenv('SLACK_API_KEY')
    if config['DEBUG']:
        print 'DEBUG[VAR]: SLACK_API_KEY = {0}'.format(config['SLACK_API_KEY'])
    slack = Slack(config['SLACK_API_KEY'])

    # build config from environment
    if 'SLACK_USER_ID' in os.environ:
        config['SLACK_USER_ID'] = os.getenv('SLACK_USER_ID')
    elif 'SLACK_USER' in os.environ:
        config['SLACK_USER_ID'] = slack.get_name_id(os.getenv('SLACK_USER'))
    else:
        sys.exit('Must specify either SLACK_USER_ID or SLACK_USER through environment')

    if not config['SLACK_USER_ID']:
        sys.exit('Could not find slack id for user %s' % config['slack_user'])

    if config['DEBUG']:
        print 'DEBUG[CFG]: {0}'.format(repr(config))

    g2s = Gmail2Slack(config, slack)
    if config['LOOP'] > 0:
        delay = config['LOOP']
    else:
        delay = 0
    while True:
        try:
            g2s.gmail2slack()
        except:
            traceback.print_exc()
        if delay:
            time.sleep(delay)
        else:
            break


if __name__ == '__main__':
    main()
