FROM python:2.7-onbuild
MAINTAINER Gabriel Schubiner <g@gabeos.cc>

VOLUME /usr/src/app
CMD python2 /usr/src/app/gmail2slack.py

