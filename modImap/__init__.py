# The Admin4 Project
# (c) 2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


moduleinfo={ 'name': "IMAP Server",
            'modulename': "IMAP",
            'description': "IMAP server",
            'version': "4",
            'revision': "0.8.7",
            'requiredAdmVersion': "3.0.0",
            'testedAdmVersion': "3.0.0", 
            'pages': [],
            'copyright': "(c) 2014-2022 PSE Consulting Andreas Pflug",
            'credits': "utf-7 code from https://pypi.python.org/pypi/IMAPClient",
             }


import sys
if not hasattr(sys, 'skipSetupInit'):
  from . import Server