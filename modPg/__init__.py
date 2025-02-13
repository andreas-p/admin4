# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


moduleinfo={ 'name': "PostgreSQL Server",
            'modulename': "PostgreSQL",
            'description': "PostgreSQL database server",
            'version': "17.0",
            'revision': "0.9.1",
            'requiredAdmVersion': "3.0.0",
            'testedAdmVersion': "3.0.0",
            'supports': "PostgreSQL 8.1 ... 17 (pre-9.1 with restrictions)",
            'copyright': "(c) 2013-2025 PSE Consulting Andreas Pflug",
            'credits': "psycopg2 from http://initd.org/psycopg using libpq (http://www.postgresql.org)",
     }

import sys
if not hasattr(sys, 'skipSetupInit'):
  import adm
  import wx
  from wh import xlt, floatToTime
  from LoggingDialog import LogPanel
  
  
  class SqlPage:
    name="SQL"
    order=800

    def __init__(self, notebook):
      from ._sqledit import SqlEditor
      self.control=SqlEditor(notebook)
      self.control.SetMarginWidth(1, 2)
      self.notebook=notebook
      self.lastNode=None
    
    def GetControl(self):
      return self.control
  
    def Display(self, node, _detached):
      if hasattr(node, "GetSql"):
        sql=node.GetSql().strip().replace("\n\r", "\n").replace("\r\n", "\n")
      else:
        sql=xlt("No SQL query available.")
      self.control.SetReadOnly(False)
      self.control.SetValue(sql)
      self.control.SetReadOnly(True)
      self.control.SetSelection(0,0)
        
  moduleinfo['pages'] = [SqlPage]

      
  class Preferences(adm.PreferencePanel):
    name="PostgreSQL"
    configDefaults={ 'AdminNamespace':  "Admin4",
                    'SettingCategorySort': "Reporting Query" }

  from . import Server
