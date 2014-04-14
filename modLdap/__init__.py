# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import sys
if not hasattr(sys, 'skipSetupInit'):
  import wx
  import adm
  from wh import xlt, strToIsoDate, isoDateToStr
  import logger


  class ldapSyntax:
  # http://www.alvestrand.no/objectid/1.3.6.1.4.1.1466.115.121.1.html
    # http://www.zytrax.com/books/ldap/apa/types.html
    BINARY=       "1.3.6.1.4.1.1466.115.121.1.5"
    BOOLEAN=      "1.3.6.1.4.1.1466.115.121.1.7"
    DIRECTORYSTR= "1.3.6.1.4.1.1466.115.121.1.15"
    GENERALTIME=  "1.3.6.1.4.1.1466.115.121.1.24"
    IA5STRING=    "1.3.6.1.4.1.1466.115.121.1.26"
    INTEGER=      "1.3.6.1.4.1.1466.115.121.1.27"
    JPEG=         "1.3.6.1.4.1.1466.115.121.1.28"
    OID=          "1.3.6.1.4.1.1466.115.121.1.38"
    OCTETSTRING=  "1.3.6.1.4.1.1466.115.121.1.40"
    msExchMailboxSecurityDescriptor="1.2.840.113556.1.4.907"
  
    EmptyAllowed=[IA5STRING, OCTETSTRING]
  
  class AttrVal:
    def __init__(self, name, schema=None, value=None):
      if isinstance(name, AttrVal):
        self.name=name.name
        self.schema=name.schema
        self.value=name.value[:]
      else:
        self.schema=schema
        if name == None:
          self.name=self.schema.names[0]
        else:
          self.name=name
        self.value=value
      self.empty = (self.value == None)
      self.items={}
  
    def GetValue(self):
      if self.IsSingleValue():
        if self.IsInteger():
          return int(self.value[0])
        elif self.IsBoolean():
          return self.value[0][0] in "tTyY1"
        elif self.IsBinary():
          return self.value[0]
        else:
          try:
            val=self.value[0].decode('utf8')
          except Exception as _e:
            if self.schema:
              syntax=self.schema.syntax
            else:
              syntax=None
            logger.debug("Not decoding %s (Syntax %s): %s", self.name, syntax, self.value[0])
            val=self.value[0]
          if self.IsTime() and val.endswith('Z'):
            return strToIsoDate(val)
          return val
      else:
        if self.IsBinary():
          return self.value;
        elif self.IsTime():
            return map(lambda x: strToIsoDate(x), self.value)
        return map(lambda x: x.decode('utf8'), self.value)
  
    def SetValue(self, value):
      self.empty=(value == None)
      if self.IsInteger():
        if value == None:
          self.value=['0']
        elif self.IsSingleValue():
          self.value=[str(value)]
        else:
          self.value=map(str, value)
      else:
        if value == None or value == []:
          self.value=['']
        elif self.IsSingleValue():
          if self.IsTime():
            self.value=[isoDateToStr(value)]
          elif self.IsBoolean():
            if value:
              self.value=["TRUE"]
            else:
              self.value=["FALSE"]
          else:
            self.value=[value.encode('utf8')]
        else:
          self.value=map(lambda x: x.encode('utf8'), value)
      if not self.value or not len(self.value[0]):
        self.empty=True
  
    def AppendValue(self, value):
      self.value.append(value.encode('utf8'))
  
    def RemoveValue(self, value):
      try:
        self.value.remove(value.encode('utf8'))
      except:
        return False
      return True
  
  
    def GetOid(self):
      if self.schema:
        return self.schema.oid
  
    def GetMaxLen(self):
      if self.schema:
        return self.schema.syntax_len
  
    def IsOctet(self):
      if self.schema:
        return self.schema.syntax == ldapSyntax.OCTETSTRING
  
    def IsBinary(self):
      if self.schema:
        return self.schema.syntax in [ldapSyntax.JPEG, ldapSyntax.BINARY, ldapSyntax.OCTETSTRING, ldapSyntax.msExchMailboxSecurityDescriptor]
  
    def IsTime(self):
      if self.schema:
        return self.schema.syntax == ldapSyntax.GENERALTIME
  
    def IsInteger(self):
      if self.schema:
        return self.schema.syntax == ldapSyntax.INTEGER
  
    def IsBoolean(self):
      if self.schema:
        return self.schema.syntax == ldapSyntax.BOOLEAN
  
    def IsSingleValue(self):
      if self.schema:
        return self.schema.single_value
  
    def __str__(self):
      return "%s: %s" % (self.name, self.value)
  
  
  
  class Preferences(adm.NotebookPanel):
    name="LDAP"
  
    def Go(self):
      pass
  
    def Save(self):
      return True
  
    @staticmethod
    def Init():
      pass
  
  import Server
  moduleinfo={ 'name': xlt("LDAP Server"),
              'modulename': "LDAP",
              'description': "LDAP 3.0 server",
              'version': "1.0",
  						'serverclass': Server.Server,
  						'pages': [],
  #						'preferences': Preferences,
              'copyright': "(c) 2013-2014 PSE Consulting Andreas Pflug",
              'credits': "python-ldap from http://www.python-ldap.org using OpenLdap 2.4 (http://www.openldap.org)",
  						 }
