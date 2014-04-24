# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import wx
import adm
import re, ast
import wx.propgrid as wxpg

import logger
from wh import xlt, YesNo
from . import AttrVal, ConvertResult

from _ldap import LdapServer, ldap

standardSystemAttributes="structuralObjectClass hasSubordinates creatorsName modifiersName createTimestamp modifyTimestamp"
standardSystemClasses="subschema$ subentry$ openldaprootdse$ olc.*"
standardTimeout=5


class Server(adm.ServerNode):
  shortname=xlt("LDAP Server")
  typename=xlt("LDAP Server")
  wantIconUpdate=True
  panelClassDefault={
  #  'useraccount': "UserAccount:UserAccountItw Personal Contact Groups ShadowAccount SambaAccount",
    'UserAccount': "UserAccount SambaAccount ShadowAccount Personal Contact Groups",
    'Group': "Group SambaGroupMapping",
    'SambaDomain': "SambaDomain",
    }    
  def __init__(self, settings):
    adm.ServerNode.__init__(self, settings)
    if not self.user:
      self.needPassword=False
    self.dn= settings['ldapbase']
    self.attributes={}
    self.adminLdapDn=None
    self.config={}

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
    if self.adminLdapDn:
      self.properties.append( (xlt("Admin Config DN"), self.adminLdapDn))
    if self.registrationChanged:
      self.properties.append( (xlt("Registration"), xlt("Registration changed"), adm.images['attention']) )

    return self.properties

  def GetLastError(self):
    if self.connection:
      return self.connection.lastError


  def SearchSub(self, filter="(objectClass=*)", attrs=["*"]):
    return self.connection.SearchSub(self.dn, filter, attrs)


  
  def SearchSubConverted(self, filter="(objectClass=*)", attrs=["*"]):
    res=self.SearchSub(filter, attrs)
    return ConvertResult(res)

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

    if self.IsConnected():
      cfg=ServerConfigData(self)
      self.config = cfg.Read()
      return True
    return False


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

  def GetIdGeneratorStyle(self):
    return self.config.get('idGeneratorStyle', 1)
  
  def GetSambaUnixIdPoolDN(self):
    return self.config.get('sambaUnixIdPoolDN') 

  def GetPanelClasses(self, pcn):
    panelClasses=self.config.get('panelClasses', {})
    pcl=panelClasses.get(pcn, self.panelClassDefault.get(pcn))
    if pcl:
      return str(pcl)
    return None


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


class ServerConfigData:
  attrib='audio'
  
  def __init__(self, server):
    self.server=server

  def rdn(self):
    return self.server.GetPreference("AdminLdapRdn")

  def Init(self):
    vals=AttrVal.CreateList( {'objectClass': 'inetorgPerson', 
                            'sn': "Admin4 Configuration Data",
                            'description': "Configuration data of Admin4; do not edit manually.", 
                            self.attrib: "{}" } )
    dn="cn=%s,%s" % (self.rdn(), self.server.dn)
    rc= self.server.GetConnection().Add(dn, vals)
    if rc:
      self.server.adminLdapDn=dn
    return rc

  def Read(self):
    adm=self.server.connection.SearchOne(self.server.dn, "cn=%s" % self.rdn())
    config={}
    if adm:
      self.server.adminLdapDn=adm[0][0]
      val=adm[0][1][self.attrib]
      try:
        config=ast.literal_eval(val[0])
      except:
        logger.debug("Couldn't pythonize '%s[0]'", val)
    return config
      
  def Update(self, value):    
    dn=self.server.adminLdapDn
    rc=self.GetConnection().Modify(dn, [AttrVal(self.attrib, None, value)])
    return rc

  
class ServerInstrument:
  name=xlt("Instrument server")
  help=xlt("Instrument server for site specific administration")
  
  @staticmethod
  def CheckAvailableOn(node):
    return isinstance(node, Server) and not node.adminLdapDn
  
  @staticmethod
  def OnExecute(_parentWin, server):
    cfg=ServerConfigData(server)
    return cfg.Init()
      
    return True


class ServerConfig(adm.Dialog):
  name=xlt("Server Configuration")
  help=xlt("Edit LDAP Server Configuration")

  def AddExtraControls(self, res):
    self.grid=wxpg.PropertyGrid(self)
    self.grid.SetMarginColour(wx.Colour(255,255,255))
    res.AttachUnknownControl("ValueGrid", self.grid)
    
    
  def Go(self):
    self.grid.Freeze()
    for key in Server.panelClassDefault:
      val=self.node.GetPanelClasses(key)
      property=wxpg.StringProperty(key, key, val)
#      bmp=self.GetBitmap(key)
#      if bmp:
#        self.grid.SetPropertyImage(property, bmp)  crashes?!?
      self.grid.Append(property)
    self.grid.Thaw()
    self.IdGeneratorStyle =  self.node.GetIdGeneratorStyle()
    self.sambaUnixIdPoolDN = self.node.GetSambaUnixIdPoolDN() 

  
  def GetChanged(self):
    return True
    
    
  def Check(self):
    if self.grid.IsEditorFocused():
      self.grid.CommitChangesFromEditor()
    return True
  
  def Save(self):
    pc={}
    for name in Server.panelClassDefault:
      property=self.grid.GetProperty(name)
      val=property.GetValue()
      if val:
        pc[name] = val 
    config={}
    config['panelClasses'] = pc
    config['idGeneratorStyle'] = self.IdGeneratorStyle
    config['sambaUnixIdPoolDN'] = self.sambaUnixIdPoolDN
    
    cfg=ServerConfigData(self.node)
    rc=cfg.Update(str(config))
    if rc:
      self.node.config=config
    return rc

  @staticmethod
  def CheckEnabled(node):
    return node.adminLdapDn != None


  @staticmethod
  def OnExecute(parentWin, node):
    dlg=ServerConfig(parentWin, node)
    return dlg.GoModal()


menuinfo=[
        {"class": ServerConfig, "nodeclasses": Server, 'sort': 40},
        {"class": ServerInstrument, "nodeclasses": Server, 'sort': 1},
        ]
