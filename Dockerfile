# The Admin4 Project
# (c) 2013-2019 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage
#
# docker build -t admin4 --build-arg VERSION=2.2.2 .


FROM python:2.7.15-slim-stretch

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
            wget unzip \
            python-requests python-crypto python-wxgtk3.0 \ 
            python-dnspython python-ldap python-psycopg2 


ARG VERSION
RUN test -n "$VERSION" && echo "\n\nBuilding Docker image from Admin4-${VERSION}-Src\n\n"

WORKDIR /
RUN wget https://netcologne.dl.sourceforge.net/project/admin4/V${VERSION}/Admin4-${VERSION}-Src.zip && \
    unzip Admin4*.zip ; mv Admin4*-Src admin4 ; rm Admin4*.zip


VOLUME /admin4
CMD /admin4/admin4.py
