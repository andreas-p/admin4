# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License,
# see LICENSE.TXT for conditions of usage
#


FROM python:3.11.4-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
            wget python3-pip build-essential libgtk-3-dev python3-wxgtk4.0 \
            python3-requests python3-dnspython python3-ldap python3-psycopg2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    useradd -u 1000 admin4

COPY admin4/ /admin4/

WORKDIR /admin4
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages:/usr/lib/python3/dist-packages
CMD python3 admin4.py
