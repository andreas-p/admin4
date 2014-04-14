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
  
  

      
  class Preferences(adm.NotebookPanel):
    name="BIND"
  
    def Go(self):
      pass
    
    def Save(self):
      return True
      
  moduleinfo={ 'name': xlt("BIND DNS Server"),
              'modulename': "BIND",
              'description': xlt("BIND9 DNS server"),
              'version': "9.9.0",
              'supports': "BIND V9.6 ... V9.9",
              'serverclass': Server.Server,
#              'pages': [StatisticsPage, ConnectionPage, SqlPage],
#              'preferences': Preferences,
              'copyright': "(c) 2014 PSE Consulting Andreas Pflug",
              'credits': "dnspython from http://www.dnspython.org",
       }