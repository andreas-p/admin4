# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

moduleinfo={ 'name': "BIND DNS Server",
            'modulename': "BIND",
            'description': "BIND9 DNS server",
            'version': "9.9",
            'revision': "0.98.4",
            'requiredAdmVersion': "2.1.4", 
            'testedAdmVersion': "2.1.5", 
            'supports': "BIND V9.6 ... V9.9",
            'copyright': "(c) 2014 PSE Consulting Andreas Pflug",
            'credits': "dnspython from http://www.dnspython.org",
     }

import sys
if not hasattr(sys, 'skipSetupInit'):
  import Server
      
