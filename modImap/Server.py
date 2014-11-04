# The Admin4 Project
# (c) 2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
from wh import xlt, YesNo
from _imap import ImapServer

class Server(adm.ServerNode):
  shortname=xlt("IMAP4 Server")
  typename=xlt("IMAP4 Server")
#  findObjectIncremental=False


  def __init__(self, settings):
    adm.ServerNode.__init__(self, settings)
    self.userList=[]

  def IsConnected(self, _deep=False):
    return self.connection != None


  def Disconnect(self):
    if self.connection:
      self.connection.logout()
      self.connection=None
      
          
  def DoConnect(self):
    if not self.connection:
      self.connection=ImapServer.Create(self)
      self.connection.Login(self.user, self.password)
    return self.connection

  
  def GetLastError(self):
    if self.connection and not self.connection.ok():
      return self.connection.lastError
    return None
  

  def GetProperties(self):
    if not self.properties:
      sec=self.settings['security']
      if sec.startswith('SSL'):
        pass
      elif sec.startswith('TLS'):
        if self.connection.tls:  sec="TLS"
        else:                    sec=xlt("unsecured connection")
        
      self.annotations=self.connection.GetAnnotations('')
        
      self.properties= [
         ( xlt("Name"),self.name),
         ( xlt("Protocol"), self.connection.PROTOCOL_VERSION),
         ( xlt("Address"), self.address),
         ( xlt("Security"), sec),
         ( xlt("Port"), self.settings["port"]),
         ( xlt("User"), self.user),
         ( xlt("Connected"), YesNo(self.IsConnected())),
         ( xlt("Autoconnect"), YesNo(self.settings.get('autoconnect'))),
         ]
      self.AddProperty("Server", self.connection.id.get('name'))
      self.AddProperty("Version", self.connection.id.get('version'))
      fs=self.annotations.Get('/freespace')
      if fs != None:
        self.AddSizeProperty(xlt("Free space"), float(fs)*1024)
              
#      if self.IsConnected():
#        self.AddChildrenProperty(list(self.connection.capabilities), xlt("Capabilities"), -1)
    return self.properties

  
  class Dlg(adm.ServerPropertyDialog):
    def __init__(self, parentWin, node):
      adm.PropertyDialog.__init__(self, parentWin, node, None)
      self['Security'].Append( { ' ': xlt("No security"), 'TLS-req': xlt("TLS required"), 'TLS-pref': xlt("TLS if available"), 'SSL': xlt("SSL") } )
      self.Bind("HostName HostAddress Port User Password Autoconnect")
      self.Bind("Security", self.OnChangeSecurity)

    def OnChangeSecurity(self, evt):
      if self.security == "SSL":
        self.port=993
      else:
        self.port=143
      
      self.Check()

    def Go(self):
      if self.node:
        self.SetSettings(self.node.settings)
        self["HostName"].Disable()
      else:
        self.Security="TLS-req"
      self.OnCheck()

    def Check(self):
      ok=True
      if not self.node:
        ok=self.CheckValid(ok, self.Hostname, xlt("Host name cannot be empty"))
        ok=self.CheckValid(ok, not adm.config.existsServer(self, self.HostName), xlt("Host name already in use"))
      ok=self.CheckValid(ok, self.HostAddress, xlt("Host address cannot be empty"))
      ok=self.CheckValid(ok, self.Port, xlt("Port cannot be 0"))
      return ok

    def Save(self):
      if self.GetChanged():
        settings=self.GetSettings()
        adm.config.storeServerSettings(self, settings)
        if self.node:
          self.node.settings=settings
          self.node.registrationChanged=True
        else:
          adm.RegisterServer(settings)
      return True
  
  @staticmethod
  def Register(parentWin):
    adm.DisplayDialog(Server.Dlg, parentWin, None)

  def Edit(self, parentWin):
    adm.DisplayDialog(Server.Dlg, parentWin, self)

nodeinfo=[ { 'class': Server, 'collection': xlt("IMAP4 Server") } ]
 
  