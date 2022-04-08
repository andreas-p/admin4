# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License,
# see LICENSE.TXT for conditions of usage
#
# docker build -t admin4 --build-arg VERSION=3.0.0 .


FROM python:3.9.12-slim-bullseye

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
            wget python3-pip build-essential libgtk-3-dev \
            python3-requests python3-dnspython python3-ldap python3-psycopg2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    useradd -u 1000 admin4

RUN pip3 install wxPython

WORKDIR /
ARG VERSION

RUN test -n "$VERSION" && echo "\n\nBuilding Docker image from Admin4-${VERSION}\n\n" && \
    wget https://github.com/andreas-p/admin4/archive/refs/tags/${VERSION}.tar.gz && \
    tar xf ${VERSION}.tar.gz && rm ${VERSION}.tar.gz


WORKDIR /admin4-${VERSION}

RUN rm -r docker xrced

ENV PYTHONPATH=/usr/local/lib/python3.9/site-packages:/usr/lib/python3/dist-packages
CMD python3 admin4.py
