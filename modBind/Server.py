# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import xlt, YesNo


from ._dns import BindConnection, DnsSupportedAlgorithms


class Server(adm.ServerNode):
  shortname=xlt("BIND Server")
  typename=xlt("BIND Server")

  def __init__(self, settings):
    adm.ServerNode.__init__(self, settings)
    self.zones=adm.config.Read(self.name, [], self, "Zones")
    self.revzones=adm.config.Read(self.name, [], self, "Revzones")
    self.stats=None
    self.knownZones=[]
    self.lastError=None
    self.bindVersion=None
    self.views={}
    self.serverStats=[]
    self.serverBoot=None
    self.viewzones={}
    
  def GetSubzones(self, node, rev=False):
    zones=[]
    if node == self:
      parentZone=None
    else:
      parentZone=".%s" % node.zonename
    
    for zone in self.knownZones:
      if not parentZone and zone.lower().endswith( ('.in-addr.arpa', '.ip6.arpa')) != rev:
        continue 
      if not parentZone or zone.endswith(parentZone):
        zones.append(zone)
        
    for zone in zones[:]:
      for z in zones:
        if zone.endswith(".%s" % z):
          zones.remove(zone)
          break
    return zones
  
  def GetZoneName(self, dns):
    if not isinstance(dns, str):
      dns=dns.to_text(True)
    found=""
    for zone in self.knownZones:
      if dns.endswith(".%s" % zone) and len(zone) > len(found):
        found=zone
    if found:
      dns=dns[:-len(found)-1]
    return dns, found
  
  
  def GetProperties(self):
    if not self.properties:
      self.properties= [
         ( xlt("Name"),self.name),
#         ( xlt("Version"), self.info['version']),
         ( xlt("Address"), self.address),
         ( xlt("Port"), self.settings["port"]),
         ( xlt("Stats Port"), self.settings.get("statsport")),
         ( xlt("Key name"), self.settings.get("keyname")),
         ( xlt("Autoconnect"), YesNo(self.settings.get('autoconnect'))),
         ]
      self.AddProperty(xlt("BIND Version"), self.bindVersion)
      self.AddProperty(xlt("Server Boot"), self.serverBoot)
      zimg=self.GetImageId("Zone")
      for viewname, zones in self.viewzones.items():
        self.AddChildrenProperty(sorted(zones), xlt("Zones in view \"%s\"") % viewname, zimg)
    return self.properties
  
  def GetLastError(self):
    return self.lastError
  
  def IsConnected(self, _deep=False):
    return self.connection != None
  
  def RefreshVolatile(self, force=False):
    if (not self.connection.HasFailed() and not self.stats) or force:
      self.stats=self.connection.ReadStatistics()
      if self.stats:
        self.views={}
        self.viewzones={}
        self.knownZones=[]
        if self.stats.tag == 'statistics': # 9.10
          statVersion=float(self.stats.attrib['version'])
        else: # <9.9
          st=self.stats.find('statistics')
          if st:
            statVersion=float(st.findtext('version'))
          else: # 9.9
            try:
              st=self.stats.find('bind').find('statistics')
              statVersion=float(st.attrib['version'])
            except:
              statVersion=0 # hope the best
          
        if statVersion >=3: # bind >= 9.10
          for view in self.stats.iter('view'):
            viewname=view.attrib['name']
            viewstat=[]
            self.views[viewname]=viewstat
            viewzone=[]
            self.viewzones[viewname]=viewzone
            for rdt in view.iter('rdtype'):
              viewstat.append( (rdt.attrib['name'], rdt.text) )
            for res in view.iter('resstat'):
              viewstat.append( (res.attrib['name'], res.text) )
            for zone in view.iter('zone'):
              if zone.attrib['rdataclass'] == 'IN':
                zonename=zone.attrib['name']
                self.knownZones.append(zonename)
                viewzone.append(zonename)
          
          self.serverBoot=self.stats.find('server').findtext('boot-time')
  
          self.serverStats=[]
          for counters in self.stats.iter('counters'):
            if counters.attrib['type'] =='nsstat':
              for counter in counters.iter('counter'):
                self.serverStats.append( (counter.attrib['name'], counter.text) )

        else:  # bind <= 9.9
          for view in self.stats.iter('view'):
            viewname=view.findtext('name')
            viewstat=[]
            self.views[viewname]=viewstat
            viewzone=[]
            self.viewzones[viewname]=viewzone
            for rdt in view.iter('rdtype'):
              viewstat.append( (rdt.findtext('name'), rdt.findtext('counter')) )
            for res in view.iter('resstat'):
              viewstat.append( (res.findtext('name'), res.findtext('counter')) )
            for zone in view.iter('zone'):
              if zone.find('rdataclass').text == 'IN':
                zonename=zone.findtext('name').split('/')[0]
                self.knownZones.append(zonename)
                viewzone.append(zonename)
          
          sv=self.stats.find('bind').find('statistics').find('server')
          self.serverBoot=sv.findtext('boot-time')
  
          self.serverStats=[]
          for sres in sv.iter('nsstat'):
            self.serverStats.append( (sres.findtext('name'), sres.findtext('counter')) )
           
        self.knownZones=sorted(set(self.knownZones))
    return self.stats
  
  def DoConnect(self):
    if not self.connection:
      self.connection = BindConnection(self)
      self.bindVersion=self.connection.GetVersion()
      if self.bindVersion == None:
        self.connection = None
        return False
      self.RefreshVolatile(True)
    return True
  
  
  def GetZone(self, zone):
    frame=adm.StartWaiting()
    try:
      z=self.connection.GetZone(zone)
    except Exception as e:
      txt=xlt("Couldn't Transfer zone data for %s: %s %s " % (zone, e.__class__.__name__, str(e)))
      adm.StopWaiting(frame, txt)
      raise adm.ServerException(self, txt)

    adm.StopWaiting(frame)
    return z

  def Send(self, updater):
    frame=adm.StartWaiting()
    try:
      result=self.connection.Send(updater)
    except Exception as e:
      txt=xlt("Couldn't send data: %s %s " % (e.__class__.__name__, str(e)))
      adm.StopWaiting(frame, txt)
      raise adm.ServerException(self, txt)

    adm.StopWaiting(frame)
    return result
    

  def RemoveZone(self, zone):
    if zone.__class__.__name__ == "RevZone":
      self.revzones.remove(zone.name)
    else:
      self.zones.remove(zone.name)
    self.writeZones()
  
  def AddZone(self, zone):
    if zone.__class__.__name__ == "RevZone":
      self.revzones.append(zone.name)
    else:
      self.zones.append(zone.name)
    self.appendChild(zone)
    self.writeZones()
    
  def writeZones(self):
    adm.config.Write(self.name, self.zones, self, "Zones")
    adm.config.Write(self.name, self.revzones, self, "RevZones")
    
      
  class Dlg(adm.ServerPropertyDialog):
    adm.ServerPropertyDialog.keyvals.extend( [ 'algorithm', 'statsport', 'keyname', 'timeout' ] )

    def __init__(self, parentWin, node):
      adm.PropertyDialog.__init__(self, parentWin, node, None)
      self['Algorithm'].Append( DnsSupportedAlgorithms )
      self.Bind("HostName HostAddress Port Password Algorithm Autoconnect StatsPort Keyname Timeout")


    def Go(self):
      if self.node:
        self.SetSettings(self.node.settings)
        self["HostName"].Disable()
      else:
        self.StatsPort=8053
      self.OnCheck()

    def Check(self):
      ok=True
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


class StatisticsPage(adm.NotebookPage):
  name=xlt("NS Statistics")
  order=10
  
  def Display(self, node, _detached=False):
    self.lastNode=node
    ctl=self.control
    node.RefreshVolatile(True)
    self.control.ClearAll()
    if node.serverStats:
      ctl.AddColumn(xlt("Statistics"), 30)
      ctl.AddColumn(xlt("Value"), 20)
      for name, value in node.serverStats:
        ctl.AppendItem(-1, [name, value])
    else:
      self.control.AddColumn("", -1)
      self.control.AppendItem(-1, [xlt("No statistics available")])


class ViewStatsPage(adm.NotebookPage):
  name=xlt("View Statistics")
  order=12
  def Display(self, node, _detached=False):
    self.lastNode=node
    ctl=self.control
    node.RefreshVolatile(True)
    self.control.ClearAll()
    if node.serverStats:
      ctl.AddColumn(xlt("Statistics"), 20)

      for viewname, _viewstat in node.views.items():
        ctl.AddColumn(viewname, 10)

      for row in range(len(node.views[viewname])):      
        vals=[]
        for _viewname, viewstat in node.views.items():
          name,value=viewstat[row]
          if not vals:
            vals.append(name)
          vals.append(value)
        ctl.AppendItem(-1, vals)
    else:
      self.control.AddColumn("", -1)
      self.control.AppendItem(-1, [xlt("No statistics available")])

pageinfo=[StatisticsPage, ViewStatsPage]
nodeinfo=[ { 'class': Server, 'pages': "StatisticsPage ViewStatsPage" } ]
