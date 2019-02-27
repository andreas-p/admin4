from python:2.7.15-stretch

RUN apt-get update && \
    apt-get install -y \
        git unzip aptitude \
        python-requests python-crypto python-dnspython python-ldap python-psycopg2 python-wxgtk3.0

VOLUME ["/opt/src"]
WORKDIR /opt/src/admin4

CMD ["python /opt/src/admin4/admin4.py"]
