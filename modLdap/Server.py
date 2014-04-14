# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import adm
import re

from wh import xlt, YesNo
from . import AttrVal

from _ldap import LdapServer, ldap

standardSystemAttributes="structuralObjectClass hasSubordinates creatorsName modifiersName createTimestamp modifyTimestamp"
standardSystemClasses="subschema$ subentry$ openldaprootdse$ olc.*"
standardTimeout=5


class Server(adm.ServerNode):
  shortname=xlt("LDAP Server")
  typename=xlt("LDAP Server")
  wantIconUpdate=True

  def __init__(self, settings):
    adm.ServerNode.__init__(self, settings)
    if not self.user:
      self.needPassword=False
    self.dn= settings['ldapbase']
    self.attributes={}

    self.timeout=settings.get('querytimeout', standardTimeout)
    self.systemAttrs=settings.get('systemattributes', standardSystemAttributes).split()
    self.systemClasses=settings.get('systemclasses', standardSystemClasses).split()

  def GetProperties(self):
    if not self.properties:
      self.version=3

    if self.user:
      user=self.user
    else:
      user=xlt("anonymous")
    self.properties= [
       ( xlt("Name"),self.name),
       ( xlt("Version"), self.version),
       ( xlt("Address"), self.address),
       ( xlt("Ldap Base"), self.dn),
       ( xlt("Security"), self.settings['security']),
       ( xlt("Port"), self.settings["port"]),
       ( xlt("User"), user),
       ( xlt("Connected"), YesNo(self.IsConnected())),
       ( xlt("Autoconnect"), YesNo(self.settings.get('autoconnect'))),
       ]

    if self.connection.base:
      for name, val in self.connection.base.items():
        self.AddChildrenProperty(val, name, -1)

    if self.registrationChanged:
      self.properties.append( (xlt("Registration"), xlt("Registration changed"), adm.images['attention']) )

    return self.properties

  def GetLastError(self):
    if self.connection:
      return self.connection.lastError


  def SearchSub(self, filter="(objectClass=*)", attrs=["*"]):
    return self.connection.SearchSub(self.dn, filter, attrs)


  def SearchSubConverted(self, filter="(objectClass=*)", attrs=["*"]):
    out=[]
    for dn, info in self.SearchSub(filter, attrs):
      do={}
      for key in info:
        do[key.decode('utf8').lower()] = map(lambda x: x.decode('utf8'), info[key])
      out.append( (dn, do) )
    return out

  def IsConnected(self, deep=False):
    if not self.connection:
      return False
    if not self.connection.ldap:
      return False
    if deep:
      pass
    return True

  def DoConnect(self):
    self.connection=LdapServer(self)
    return self.IsConnected()


  def Split_DN(self, dnstr):
    dn_s=ldap.dn.explode_dn(dnstr.encode('utf8'))
    dn=[]
    for rdn in dn_s:
      dn.append(rdn.decode('utf8'))
    return dn

  def CreateAttrVal(self, name, value=None):
    schema=self.GetAttributeSchema(name)
    if schema:
      if name == schema.oid:
        name=None
      return AttrVal(name, schema, value)
    return None

  def GetAttributeSchema(self, name):
    # site-packages/ldap/schema/models.py
    return self.connection.GetSchema(ldap.schema.AttributeType, name)

  def GetSyntaxSchema(self, name):
    # site-packages/ldap/schema/models.py
    return self.connection.GetSchema(ldap.schema.LDAPSyntax, name)

  def GetName(self, oid):
    a=self.GetAttributeSchema(oid)
    if a:
      return a.names[0]
    return None

  def GetOid(self, name):
    return self.connection.GetOid(ldap.schema.AttributeType, name)

  def GetStructuralObjectOid(self):
    if not hasattr(self, "structuralObjectOid"):
      self.structuralObjectOid=self.GetOid('structuralObjectClass')
    return self.structuralObjectOid

  def GetHasSubordinatesOid(self):
    if not hasattr(self, "hasSubordinatesOid"):
      self.hasSubordinatesOid=self.GetOid('hasSubordinates')
    return self.hasSubordinatesOid

  def GetObjectClassOid(self):
    if not hasattr(self, "objectClassOid"):
      self.objectClassOid=self.GetOid('objectClass')
    return self.objectClassOid

  def GetTopObjectClassOid(self, name):
    sup=self.GetClassSchema(name)
    if not sup:
      return None
    cls=sup
    while sup.sup:
      cls=sup
      sup=self.GetClassSchema(sup.sup[0])
    return cls.oid

  def GetClassOid(self, name):
    return self.connection.GetOid(ldap.schema.ObjectClass, name)


  def GetSystemAttrOids(self):
    if not hasattr(self, "systemAttrOids"):
      self.systemAttrOids=[]
      for attr in self.systemAttrs:
        self.systemAttrOids.append(self.GetOid(attr))
    return self.systemAttrOids


  def GetAttrOrder(self):
    if not hasattr(self, "attrOrder"):
      self.attrOrder=[]
      for n in ["uid", "ou", "cn", "sn", "givenName", "gecos", "description",
              "uidNumber", "gidNumber", "loginShell", "homeDirectory"]:
        self.attrOrder.append(self.GetOid(n))
    return self.attrOrder


  def AllClassOids(self):
    classes=self.connection.execute(self.connection.subschema.listall, ldap.schema.ObjectClass)
    return classes

  def AllObjectClasses(self):
    if not hasattr(self, "objectClasses"):
      self.objectClasses={}

      for oid in self.AllClassOids():
        cls=self.GetClassSchema(oid)
        cls.name=cls.names[0].lower()
        isSysCls=False
        for pattern in self.systemClasses:
          if re.match(pattern, cls.name):
            isSysCls=True
            break
        if isSysCls:
          continue

        self.objectClasses[oid]=cls

        if not hasattr(cls, "children"):
          cls.children=[]
        for supoid in cls.sup:
          sup=self.GetClassSchema(supoid)
          if  hasattr(sup, "children"):
            sup.children.append(cls)
          else:
            sup.children=[cls]
    return self.objectClasses


  def GetClassSchema(self, name):
    return self.connection.GetSchema(ldap.schema.ObjectClass, name)

  def GetClassSchemaMustMayOids(self, nameslist):
    """
    GetClassSchemaMustMayOids(classNamesList)

    returns two lists of oids of required and optional attributs; may list includes must attributes
    """
    if not nameslist:
      return [], []

    def addMustMay(name):
      cls=self.GetClassSchema(name)
      if cls:
        for must in cls.must:
          oid = self.GetOid(must)
          if oid not in mustHave:
            mustHave.append(oid)
        for may in cls.may:
          oid = self.GetOid(may)
          if oid not in mayHave:
            mayHave.append(oid)
        for name in cls.sup:
          addMustMay(name)


    mustHave=[]
    mayHave=[]

    for name in nameslist:
      addMustMay(name)
    mayHave.extend(mustHave)

    return mustHave, mayHave




  class Dlg(adm.ServerPropertyDialog):

    adm.ServerPropertyDialog.keyvals.extend( [ "LdapBase", "QueryTimeout", "SystemClasses", "SystemAttributes" ] )

    def __init__(self, parentWin, node):
      adm.PropertyDialog.__init__(self, parentWin, node, None)
      self['Security'].Append( { 'tls': "TLS", 'ssl': "SSL", 'none': xlt("None") } )
      self.Bind("HostName HostAddress Port User Password LdapBase Autoconnect QueryTimeout SystemClasses SystemAttributes")
      self.Bind("Remember", wx.EVT_CHECKBOX, self.OnCheckRemember)
      self.Bind("Security", wx.EVT_COMBOBOX, self.OnChangeSecurity)

    def OnCheckRemember(self, evt=None):
      self["User"].Enable(self.Remember)
      self["Password"].Enable(self.Remember)
      self.OnCheck()

    def Go(self):
      if self.node:
        self.SetSettings(self.node.settings)
        self.OnCheckRemember()
        self["HostName"].Disable()
      else:
        self.Security="tls"
      self.OnChangeSecurity()

    def OnChangeSecurity(self, evt=None):
      if not self.Port or self.Port in (636,389):
        if self.Security == "ssl":
          self.Port=636
        else:
          self.Port=389
      self.OnCheck()


    def OnGetBaseDN(self):
      #ldapsearch -x -h pse3 -b "" -s BASE +
      pass


    def Check(self):
      ok=True
      if not self.node:
        ok=self.CheckValid(ok, self.Hostname, xlt("Host name cannot be empty"))
        ok=self.CheckValid(ok, not adm.config.existsServer(self, self.HostName), xlt("Host name already in use"))
      ok=self.CheckValid(ok, self.HostAddress, xlt("Host address cannot be empty"))
      ok=self.CheckValid(ok, self.Port, xlt("Port cannot be 0"))
      ok=self.CheckValid(ok, self.LdapBase, xlt("Ldap Base cannot be empty"))
      return ok

    def Save(self):
      if self.GetChanged():
        if self.Remember:
          _password=self.Password
        else:
          _password=None
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

nodeinfo=[ { 'class': Server, 'collection': xlt("LDAP Server") } ]


class ServerConfig(adm.PropertyDialog):
  name=xlt("Server Configuration")
  help=xlt("Edit ldap Server Configuration")

  def Go(self):
    pass


  @staticmethod
  def CheckEnabled(unused_node):
    return True # TODO check if available


  @staticmethod
  def OnExecute(parentWin, node):
    dlg=ServerConfig(parentWin, node)
    return dlg.GoModal()



menuinfo=[
        {"class": ServerConfig, "nodeclasses": Server, 'sort': 40},
        ]
