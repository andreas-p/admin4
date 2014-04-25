# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import sys
if not hasattr(sys, 'skipSetupInit'):

  import Server
  import adm
  import wx
  from wh import xlt
 
      
  moduleinfo={ 'name': xlt("BIND DNS Server"),
              'modulename': "BIND",
              'description': xlt("BIND9 DNS server"),
              'version': "9.9",
              'revision': "0.98",
              'supports': "BIND V9.6 ... V9.9",
              'serverclass': Server.Server,
              'copyright': "(c) 2014 PSE Consulting Andreas Pflug",
              'credits': "dnspython from http://www.dnspython.org",
       }