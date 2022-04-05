# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm, wx, wx.grid as wxGrid
import logger
import time
from Validator import Validator
from wh import xlt, floatToTime, timeToFloat, Menu, shlexSplit, removeSmartQuote,\
  quoteIfNeeded
from ._dns import Rdataset, Rdata, RdataClass, rdatatype, rdataclass, rcode
from ._dns import Name, DnsName, DnsAbsName, DnsRevName, DnsRevAddress, DnsSupportedTypes, checkIpAddress
from .Server import Server

prioTypes=['MX', 'NS', 'SRV', 'TXT']
individualTypes=['A', 'AAAA', 'CNAME', 'PTR']

    
class Zone(adm.Node):
  typename=xlt("DNS Zone")
  shortname=xlt("Zone")

  def __init__(self, parentNode, name):
    super(Zone, self).__init__(parentNode, name)
    self.soa=None
    self.zonename=name
    self.zones=self.readZones()
    self.mx=None
    self.ns=None
    
   
  @staticmethod 
  def GetInstances(parentNode):
    instances=[]
      
    if parentNode.zones:
      for zone in parentNode.zones:
        instances.append(Zone(parentNode, zone))
    else:
      for zone in parentNode.GetServer().GetSubzones(parentNode):
        instances.append(Zone(parentNode, zone))
    return instances
  
  def MayHaveChildren(self):
    if self.zones:
      return True
    return self.GetServer().GetSubzones(self) != None

  def Updater(self):
    return self.GetConnection().Updater(self.zonename)
          
  def AddZone(self, zone):
    self.zones.append(zone.name)
    self.appendChild(zone)
    self.writeZones(self.zones)

  def RemoveZone(self, zone):
    self.zones.remove(zone.name)
    self.writeZones(self.zones)

  def GetProperties(self):
    if not self.properties:
      self.properties=[ (xlt("Zone not available"))]
      
      # if a first attempt to read the zone failed we don't try again
      self.zone=self.GetServer().GetZone(self.zonename)

      if self.zone:
        self.hosts4={}
        self.hosts6={}
        self.cnames={}
        self.ptrs={}
        self.others={}
        
        for name, rds in self.zone.iterate_rdatasets():
          name=name.to_text()
          if rds.rdtype == rdatatype.A:
            self.hosts4[name] = rds
          elif rds.rdtype == rdatatype.AAAA:
            self.hosts6[name] = rds
          elif rds.rdtype == rdatatype.CNAME:
            self.cnames[name] = rds
          elif rds.rdtype == rdatatype.PTR:
            self.ptrs[name] = rds
          else:
            if name == "@":
              if rds.rdtype == rdatatype.NS:
                self.ns=rds
              elif rds.rdtype == rdatatype.MX:
                self.mx=rds
              elif rds.rdtype == rdatatype.SOA:
                self.soa=rds
            if not self.others.get(name):
              self.others[name]={rds.rdtype: rds}
            else:
              self.others[name][rds.rdtype] = rds

        s0=self.soa[0]
        self.properties=[
              ( xlt(self.shortname),  self.name),
              ( xlt("Serial"),        s0.serial),
              (     "TTL",            floatToTime(self.soa.ttl, -1)),
              ( "Master Name Server", s0.mname),
              ( "Admin Mail",         s0.rname),
              ( xlt("Retry"),         floatToTime(s0.retry, -1)),
              ( "Expire",             floatToTime(s0.expire, -1)),
              ( "Refresh",            floatToTime(s0.refresh, -1)),
              ( "Default TTL",        floatToTime(s0.minimum, -1)),
              ]
        
        if self.ns:
          self.AddChildrenProperty(map(lambda x: str(x.target), self.ns), "NS Records", -1)
        if self.mx:
          self.AddChildrenProperty(map(lambda x: "%(mx)s  (priority %(prio)d)" % {'prio': x.preference, 'mx': str(x.exchange) }, self.mx), "MX Records", -1)
        if isinstance(self, RevZone):
          self.AddProperty(xlt("PTR record count"), len(self.ptrs), -1)
        else:
          self.AddProperty(xlt("Host record count"), len(self.hosts4)+len(self.hosts6), -1)
          self.AddProperty(xlt("CNAME record count"), len(self.cnames), -1)
        cnt=0
        for lst in self.others.items():
          cnt += len(lst)
        self.AddProperty(xlt("Other record count"), cnt, -1)
    return self.properties

   
  def readZones(self):
    return adm.config.Read("Zones/%s" % self.GetServer().name, [], self, self.name)

  def writeZones(self, val):
    return adm.config.Write("Zones/%s" % self.GetServer().name, val, self, self.name)


       

class RevZone(Zone):
  typename=xlt("Reverse DNS Zone")
  shortname=xlt("Reverse Zone")

  def __init__(self, parentNode, name):
    super(RevZone, self).__init__(parentNode, name)
    self.revzones=self.zones
    zp=self.zonename.split('.')
    if zp[0].find('-') >0:
      del zp[0]
      self.partialZonename='.'.join(zp)
    else:
      self.partialZonename=self.zonename
 
    
  @staticmethod 
  def GetInstances(parentNode):
    instances=[]
    if parentNode.revzones:
      for zone in parentNode.revzones:
        instances.append(RevZone(parentNode, zone))
    else:
      for zone in parentNode.GetServer().GetSubzones(parentNode, True):
        instances.append(RevZone(parentNode, zone))
    return instances


#=======================================================================
# Menus
#=======================================================================

class UnregisterZone:
  name="Unregister Zone"
  help="Unregister DNS zone"
  @staticmethod
  def CheckAvailableOn(node):
    if not isinstance(node, (Zone, RevZone)):
      return False
    return node.GetServer().stats == None

  @staticmethod
  def OnExecute(_parentWin, node):
    node.parentNode.RemoveZone(node)
    node.parentNode.Refresh()
    return True
  

class RegisterZone:
  name="Register Zone"
  help="Register DNS zone"

  @staticmethod
  def CheckAvailableOn(node):
    if isinstance(node, RevZone):
      return False
    if not isinstance(node, (Zone, Server)):
      return False
    return node.GetServer().stats == None

  @staticmethod
  def OnExecute(parentWin, parentNode):
    if isinstance(parentNode, Zone):
      txt=xlt("Sub zone name")
    else:
      txt=xlt("Zone name")
    dlg=wx.TextEntryDialog(parentWin, txt, xlt("Register new Zone"))
    if dlg.ShowModal() == wx.ID_OK:
      dlg.Hide()
      parentWin.SetFocus()
      if isinstance(parentNode, Zone):
        name="%s.%s" % (dlg.GetValue(), parentNode.name)
      else:
        name=dlg.GetValue()
      zone=Zone(parentNode, name)
      if zone.name not in parentNode.zones:
        parentNode.AddZone(zone)
        return True
    return False
    
class RegisterRevZone:
  name="Register Reverse Zone"
  help="Register Reverse DNS zone"

  @staticmethod
  def CheckAvailableOn(node):
    if not isinstance(node, (RevZone, Server)):
      return False
    return node.GetServer().stats == None

  @staticmethod
  def OnExecute(parentWin, parentNode):
    if isinstance(parentNode, Zone):
      txt=xlt("Reverse subzone")
    else:
      txt=xlt("Reverse Zone IP Network")
    dlg=wx.TextEntryDialog(parentWin, txt, xlt("Register new Reverse Zone"))
    if dlg.ShowModal() == wx.ID_OK:
      dlg.Hide()
      parentWin.SetFocus()
      if isinstance(parentNode, Zone):
        name="%s.%s" % (dlg.GetValue(), parentNode.name)
      else:
        name=dlg.GetValue()
        v6parts=name.split(':')
        
        if len(v6parts) > 1: #ipv6
          if name.count('::'):
            raise Exception("IPV6 network may not contain ::")

          mask=0
          strip=64-len(v6parts)*8
          v6end=v6parts[-1]
          if v6end != '':
            masks=name.split('/')
            if len(masks) > 0: # has mask
              name=masks[0] + ":"
              mask=int(masks[1])
              if mask % 4:
                raise Exception("mask must be multiple of 4")
              strip=64-mask/2
            else:
              name += ":"
          else:
            strip += 8
        else:
          dc=name.count('.')
          strip=0
          while dc < 3:
            strip += 2
            dc += 1
            name += ".0"
        name=DnsRevName(name).to_text(True)
        name = name[strip:]
      
      zone=RevZone(parentNode, name)
      if zone.name not in parentNode.revzones:
        parentNode.AddZone(zone)
        return True
    return False

class IncrementSerial:
  name=("Increment Serial")
  help=xlt("Increment SOA serial number")
  
  @staticmethod
  def OnExecute(_parentWin, node):
    now=time.localtime(time.time())
    new=((now.tm_year*100 + now.tm_mon)*100 + now.tm_mday) *100
    if node.soa[0].serial < new:
      node.soa[0].serial = new
    else:
      node.soa[0].serial += 1

    updater=node.Updater()
    updater.replace("@", node.soa)

    msg=node.GetServer().Send(updater)
    if msg.rcode() == rcode.NOERROR:
      wx.MessageBox(xlt("Incremented SOA serial number to %d") % node.soa[0].serial, xlt("New SOA serial number"))
    else:
      adm.SetStatus(xlt("DNS update failed: %s") % rcode.to_text(msg.rcode()))
      
    return True
  
  
class CleanDanglingPtr:
  name=xlt("Clean dangling PTR")
  help=xlt("Clean dangling PTR records that have non-existent targets")
    
  @staticmethod
  def OnExecute(parentWin, node):
    candidates=[]

    for name in node.ptrs.keys():
      try:
        address=DnsRevAddress(DnsAbsName(name, node.partialZonename))
        target=node.ptrs[name][0].target
        if checkIpAddress(address) == 4:
          rdtype=rdatatype.A
        else:
          rdtype=rdatatype.AAAA
        rrset=node.GetConnection().Query(target, rdtype)
        if not rrset:
          candidates.append("%s %s" % (name, target))
      except:
        candidates.append("%s <invalid>" % name)

    if candidates:
      dlg=wx.MultiChoiceDialog(parentWin, xlt("Select PTR records to clean"), xlt("%d dangling PTR records") % len(candidates), candidates)
      cleaned=[]
      if not dlg.ShowModal() == wx.ID_OK:
        return False
      for i in dlg.GetSelections():
        name=candidates[i].split(' ')[0]
        cleaned.append(name)
        updater=node.Updater()
        updater.delete(DnsAbsName(name, node.partialZonename), rdatatype.PTR)
        msg=node.GetServer().Send(updater)
        if msg.rcode() == rcode.NOERROR:
          del node.ptrs[name]
        else:
          parentWin.SetStatus(xlt("DNS update failed: %s") % rcode.to_text(msg.rcode()))
          return False
        parentWin.SetStatus(xlt("%d dangling PTR records cleaned (%s)") % (len(cleaned), ", ".join(cleaned)))
      return True
    
    else:
      wx.MessageBox(xlt("No dangling PTR record."), xlt("DNS Cleanup"))
    

    return True

#=======================================================================
#  Page Menus
#=======================================================================


class PageEditRecord:
  name=("Edit")
  help=xlt("Edit Record")
  
  @staticmethod
  def CheckEnabled(page):
    ids=page.control.GetSelection()
    return len(ids) == 1
    
  @staticmethod
  def OnExecute(parentWin, page):
    idx=page.control.GetSelection()[0]
    while idx >= 0:
      name=page.GetName(idx)
      if name:
        break
      idx -= 1
    rdtype=page.GetDataType(idx)
    dlg=page.EditDialog(rdtype)(parentWin, page.lastNode, name, rdtype)
    dlg.page=page
    if dlg.GoModal():
      page.Display(None, False)
   
 
class PageNewRecord:
  name=xlt("New")
  help=xlt("New Record")
  
  @staticmethod
  def OnExecute(parentWin, page):
    rdtype=rdatatype.from_text(page.GetDnsType())
    dlg=page.EditDialog(None)(parentWin, page.lastNode, "", rdtype)
    dlg.page=page
    if dlg.GoModal():
      page.Display(None, False)
   

class PageNewAskRecord:
  name=xlt("New")
  help=xlt("New Record")
  
  @staticmethod
  def OnExecute(parentWin, page):
    rdtype=None
    rtypes=[]
    for ptype in prioTypes:
      rtypes.append("%s - %s" % (ptype, DnsSupportedTypes[ptype]))
    for ptype in sorted(DnsSupportedTypes.keys()):
      if ptype not in prioTypes and ptype not in individualTypes:
        rtypes.append("%s - %s" % (ptype, DnsSupportedTypes[ptype]))
      
    dlg=wx.SingleChoiceDialog(parentWin, xlt("record type"), "Select record type", rtypes)
    if dlg.ShowModal() == wx.ID_OK:
      rdtype=rdatatype.from_text(dlg.GetStringSelection().split(' ')[0])
      dlg=page.EditDialog(rdtype)(parentWin, page.lastNode, "", rdtype)
      dlg.page=page
      if dlg.GoModal():
        page.Display(None, False)

class PageDeleteRecord:
  name=("Delete")
  help=xlt("Delete Records")
  
  @staticmethod
  def CheckEnabled(page):
    ids=page.control.GetSelection()
    return len(ids) >0
    
  @staticmethod
  def OnExecute(parentWin, page):
    ids=page.control.GetSelection()
    names=[]
    types=[]
    for idx in ids:
      while idx >= 0:
        name=page.control.GetItemText(idx, 0)
        if name:
          types.append(page.control.GetItemText(idx, 1))
          break
        idx -= 1
      names.append(name)

    if len(names) > 3:
      msg=xlt("Delete multiple %s records?") % page.GetDnsType()
    else:
      msg=xlt("Delete %s?") % ", ".join(map(lambda x:'"%s"'%x , names))
    if adm.ConfirmDelete(msg, xlt("Deleting Records")):
      if page.Delete(parentWin, names, types):
        page.Display(None, False)


class PageDeleteHostRecord:
  name=("Delete")
  help=xlt("Delete Records")
  
  @staticmethod
  def CheckEnabled(page):
    ids=page.control.GetSelection()
    return len(ids) >0
    
  @staticmethod
  def OnExecute(parentWin, page):
    ids=page.control.GetSelection()
    names=[]
    for idx in ids:
      while idx >= 0:
        name=page.control.GetItemText(idx, 0)
        if name:
          break
        idx -= 1
      names.append(name)
    names=list(set(names))
    if len(names) > 3:
      msg=xlt("Delete multiple %s records?") % page.GetDnsType()
    else:
      msg=xlt("Delete %s?") % ", ".join(map(lambda x:'"%s"'%x , names))
    if adm.ConfirmDelete(msg, xlt("Deleting %s Records" % page.GetDnsType())):
      if page.Delete(parentWin, names, None):
        page.Display(None, False)


#=======================================================================
# Dialogs
#=======================================================================

class Record(adm.CheckedDialog):
  def Check(self):
    ok=True
    if not self.rds:
      ok=self.CheckValid(ok, self.Recordname, xlt(("Enter %s") % self.RecordNameStatic))
      if self.rdtype == rdatatype.CNAME:
        foundSame=self.node.cnames.get(self.Recordname)
        foundOther=self.node.hosts4.get(self.Recordname)
        if not foundOther:
          foundOther=self.node.hosts6.get(self.Recordname)
        if not foundOther:
          foundOther=self.node.ptrs.get(self.Recordname)
        if not foundOther:
          # SIG, NXT and KEY allowed
          foundOther=self.node.others.get(self.Recordname)
            
        ok=self.CheckValid(ok, not foundOther, xlt("CNAME collides with existing record"))
      else:
        foundSame=self.node.others.get(self.Recordname, {}).get(self.rdtype)
        # SIG, NXT and KEY: CNAME allowed
        foundCname=self.node.cnames.get(self.Recordname)
        ok=self.CheckValid(ok, not foundCname, xlt("Record collides with existing CNAME record"))
      ok=self.CheckValid(ok, not foundSame, xlt("Record of same type and name already exists"))
        
    ok=self.CheckValid(ok, timeToFloat(self.TTL), xlt("Please enter valid TTL value"))
    return ok
  
  
class SingleValRecords(Record):
  def __init__(self, wnd, node, name="", rdtype=None):
    adm.CheckedDialog.__init__(self, wnd, node)
    self.rdtype=rdtype
    self.RecordName=name
    self.Bind("Recordname Value TTL")
    
  def _getRds(self):
    ttl=86400
    self.rds=None
    self['Recordname'].Disable()
    rdsl=self.page.GetRdata(self.RecordName, self.rdtype)
    if isinstance(rdsl, list):
      for rds in rdsl:
        if rds.rdtype == self.rdtype:
          self.rds=rds
          ttl=rds.ttl
          break
    else:
      rds=self.rds=rdsl
      ttl=rds.ttl
    if not self.rds:
      rds=None
      logger.debug("rds not found")
    return ttl, rds

  def _save(self, rds):
    updater=self.node.Updater()
    if self.rdtype == rdatatype.SOA:
      updater.replace(self.RecordName, rds)
    elif self.rdtype == rdatatype.NS:
      targets=[]
      for rd in self.rds:
        targets.append(rd.target)
      for rd in rds:
        if rd.target in targets:
          targets.remove(rd.target)
      for target in targets:
        updater.delete(self.RecordName, self.rdtype, target.to_text())
      updater.add(self.RecordName, rds)
    else:
      if self.rds:
        updater.delete(self.Recordname, self.rdtype)
      updater.add(self.Recordname, rds)
    msg=self.node.GetServer().Send(updater)
    if msg.rcode() == rcode.NOERROR:
      self.page.SetRdata(self.RecordName, self.rdtype, rds)
      self.page.Display(None, False)
      return True
    else:
      self.SetStatus(xlt("DNS update failed: %s") % rcode.to_text(msg.rcode()))
      return False

  def Check(self):
    ok=Record.Check(self)
    ok=self.CheckValid(ok, self.Value.strip(), xlt(("Enter %s") % self.ValueStatic))
    return ok

  
  def Go(self):
    if self.RecordName:
      ttl, rds=self._getRds()
      vlist=[]
      for rd in self.rds:
        value=eval("rd.%s" % rd.__slots__[0])
        if isinstance(value, list):
          value=" ".join(map(quoteIfNeeded, value))
        vlist.append(str(value))
      self.value="\n".join(vlist)
    else:
      ttl=86400
      rds=Rdataset(ttl, rdataclass.IN, self.rdtype)
      self.rds=None
    
    typestr=rdatatype.to_text(self.rdtype)
    self.SetTitle(DnsSupportedTypes[typestr])
    self.RecordNameStatic = typestr
    self.ValueStatic=rds[0].__slots__[0].capitalize()
    self.dataclass=type(eval("rds[0].%s" % rds[0].__slots__[0]))
    if self.dataclass == int:
      validatorClass=Validator.Get("uint")
      if validatorClass:
        self['Value'].validator=validatorClass(self['Value'], "uint")
    elif self.dataclass == Name:
      self.dataclass = DnsName
    self.TTL=floatToTime(ttl, -1)


  def Save(self):
    ttl=int(timeToFloat(self.TTL))
    rds=None
    for value in self.Value.splitlines():
      value=value.strip()
      if not value:
        continue
      if self.dataclass == list:
        value=removeSmartQuote(value)
        data=shlexSplit(value, ' ')
      else:
        data=self.dataclass(value)
      if not rds:
        rds=Rdataset(ttl, rdataclass.IN, self.rdtype, data)
      else:
        rds.add(Rdata(rds, data), ttl)
    return self._save(rds)
   
    
class SingleValRecord(SingleValRecords):
  pass



class MultiValRecords(SingleValRecords):
  def __init__(self, wnd, node, name="", rdtype=None):
    adm.CheckedDialog.__init__(self, wnd, node)
    self.rdtype=rdtype
    self.RecordName=name
    self.Bind("Recordname TTL")

  def AddExtraControls(self, res):
    self.grid=wxGrid.Grid(self)
    res.AttachUnknownControl("ValueGrid", self.grid)
    self.grid.Bind(wxGrid.EVT_GRID_CELL_CHANGED, self.OnCellChange)
    self.grid.Bind(wxGrid.EVT_GRID_EDITOR_SHOWN, self.OnEditorShown)
    self.grid.Bind(wxGrid.EVT_GRID_CELL_RIGHT_CLICK, self.OnRightClick)


  def OnEditorShown(self, evt):
    self.changed=True
    self.OnCheck(evt)
    
  def GetChanged(self):
    return self.changed
  
  def OnCellChange(self, evt):
    if evt.GetRow() == self.grid.GetNumberRows()-1:
      self.grid.AppendRows(1)
    self.changed=True
    return self.OnCheck(evt)

  
  def OnRightClick(self, evt):
    self.cmRow=evt.GetRow()
    cm=Menu(self)
    cm.Add(self.OnDelete, xlt("Delete"), xlt("Delete line"))
    cm.Popup(evt)
    
    
  def OnDelete(self, evt):
    self.changed=True
    self.grid.DeleteRows(self.cmRow, 1)
    self.OnCheck(evt)
  
  
  def Go(self):
    if self.RecordName:
      ttl, rds=self._getRds()
      self.changed=False
    else:
      ttl=86400
      self.rds=None
      self.changed=True
      cls=RdataClass(rdataclass.IN, self.rdtype)
      rds=Rdataset(ttl, rdataclass.IN, self.rdtype)

    typestr=rdatatype.to_text(self.rdtype)
    self.SetTitle(DnsSupportedTypes[typestr])
    self.RecordNameStatic = typestr

    self.slots=rds[0].__slots__
    self.slotvals=[]
    for slot in self.slots:
      self.slotvals.append(eval("rds[0].%s" % slot))
      
    self.grid.CreateGrid(1, len(self.slots))
    self.grid.SetRowLabelSize(0)
    for col in range(len(self.slots)):
      self.grid.SetColLabelValue(col, self.slots[col].capitalize())
      self.grid.AutoSizeColLabelSize(col)
      colsize=self.grid.GetColSize(col)
      if isinstance(self.slotvals[col], int):
        minwidth, _h=self.grid.GetTextExtent("99999")
        self.grid.SetColFormatNumber(col)
      else:
        minwidth, _h=self.grid.GetTextExtent("TheSampleTarget.admin.org")
      MARGIN=8
      minwidth += MARGIN
      if colsize < minwidth:
        self.grid.SetColSize(col, minwidth)
    
    if self.RecordName:
      row=0
      for _rd in self.rds:
        for col in range(len(self.slots)):
          val=eval("_rd.%s" % self.slots[col])
          if isinstance(val, list):
            val=" ".join(val)
          self.grid.SetCellValue(row, col, str(val))
        self.grid.AppendRows(1)
        row += 1
    self.TTL=floatToTime(ttl, -1)

    self.Show()
    self.grid.AutoSizeColumns()

    maxwidth, _h=self.grid.GetSize()
    width=0
    cn=self.grid.GetNumberCols()-1
    for col in range(cn+1):
      width += self.grid.GetColSize(col)
    if width < maxwidth:
      self.grid.SetColSize(cn, self.grid.GetColSize(cn) + maxwidth-width)



  def Check(self):
    ok=Record.Check(self)
    ok=self.CheckValid(ok, self.grid.GetNumberRows()>1, xlt("At least one record line required"))
    for row in range(self.grid.GetNumberRows()-1):
      if not ok:
        break
      vals=[]
      for col in range(self.grid.GetNumberCols()):
        val=self.grid.GetCellValue(row, col).strip()
        if val:
          vals.append(val)
      ok=self.CheckValid(ok, len(vals) == len(self.slotvals), xlt("Enter all values in row %d" % (row+1)))
    return ok
  
  
  def Save(self):
    self.grid.SaveEditControlValue()
    ttl=int(timeToFloat(self.TTL))
    rds=None
    
    for row in range(self.grid.GetNumberRows()-1):
      vals=[]
      for col in range(self.grid.GetNumberCols()):
        val=self.grid.GetCellValue(row, col).strip()
        coltype=type(self.slotvals[col])
        if coltype == Name:
          vals.append(DnsName(val))
        elif coltype == list:
          vals.append(val.split(' '))
        else:
          vals.append(coltype(val))
        
      if not rds:
        rds=Rdataset(ttl, rdataclass.IN, self.rdtype, *tuple(vals))
      else:
        rds.add(Rdata(rds, *tuple(vals)), ttl)

    return self._save(rds)


class HostRecord(adm.CheckedDialog):
  def __init__(self, wnd, node, name="", unused=None):
    adm.CheckedDialog.__init__(self, wnd, node)
    self.Hostname=name
    self.Bind("Hostname IpAddress TTL TTL6 CreatePtr")
  
  def Go(self):
    ttl=86400
    ttl6=None
    if self.Hostname:
      self.isNew=False
      hasPtr=False
      query=self.node.GetConnection().Query
      name="%s.%s." % (self.Hostname, self.node.zonename)

      h4=self.node.hosts4.get(self.Hostname)
      h6=self.node.hosts6.get(self.Hostname)
      adr=[]
      
      def _handleAddress(h, hasPtr):
          adr.append(h.address)
          if not hasPtr:
            rrs=query(DnsRevName(h.address), rdatatype.PTR)
            if rrs and rrs[0].target.to_text() == name:
              return True
          return hasPtr

      if h4:
        ttl=h4.ttl
        for h in h4:
          hasPtr=_handleAddress(h, hasPtr)
      if h6:
        ttl6=h6.ttl
        for h in h6:
          hasPtr=_handleAddress(h, hasPtr)

      self['Hostname'].Disable()
      self.IpAddress="\n".join(adr)
      self.CreatePtr=hasPtr
    else:
      self.isNew=True
    self.TTL=floatToTime(ttl, -1)
    if ttl6 and ttl6 != ttl:
      self.TTL6=floatToTime(ttl6, -1)
    self.SetUnchanged()
  
  def Save(self):
    ttl4=int(timeToFloat(self.TTL))
    if self.ttl6:
      ttl6=int(timeToFloat(self.TTL6))
    else:
      ttl6=ttl4
    name=str(self.Hostname)
    updater=self.node.Updater()
    if self.node.hosts4.get(name):
      updater.delete(name, "A")
    if self.node.hosts4.get(name):
      updater.delete(name, "AAAA")
    
    h4=None
    h6=None
    addresses=self.IpAddress.splitlines()
    for address in addresses:
      address=address.strip()
      if not address:
        continue
      if checkIpAddress(address) == 4:
        if h4:
          h4.add(Rdata(h4, address), ttl4)
        else:
          h4=Rdataset(ttl4, rdataclass.IN, rdatatype.A, address)
      else:
        if h6:
          h6.add(Rdata(h6, address), ttl6)
        else:
          h6=Rdataset(ttl6, rdataclass.IN, rdatatype.AAAA, address)
      
    if h4:
      updater.add(name, h4)
    if h6:
      updater.add(name, h6)
    msg=self.node.GetServer().Send(updater)
    if msg.rcode() != rcode.NOERROR:
      self.SetStatus(xlt("DNS update failed: %s") % rcode.to_text(msg.rcode()))
      return False
    self.node.hosts4[name] = h4
    self.node.hosts6[name] = h6
    
    
    prevAddresses=self['IpAddress'].unchangedValue.splitlines()
    if self.CreatePtr:
      dnsName=DnsAbsName(name, self.node.zonename)

      for address in addresses:
        if address in prevAddresses:
          prevAddresses.remove(address)
        ptr, zone=self.node.GetServer().GetZoneName(DnsRevName(address))
        if zone:
          if zone.endswith("in-addr.arpa"):
            ttl=ttl4
          else:
            ttl=ttl6
          updater=self.node.GetConnection().Updater(zone)
          updater.delete(ptr, 'PTR')
          
          updater.add(ptr, Rdataset(ttl, rdataclass.IN, rdatatype.PTR, dnsName))
          _msg=self.node.GetServer().Send(updater)
      for address in prevAddresses:
        ptr, zone=self.node.GetServer().GetZoneName(DnsRevName(address))
        if zone:
          updater=self.node.GetConnection().Updater(zone)
          updater.delete(ptr, 'PTR')
          _msg=self.node.GetServer().Send(updater)
    return True
  
  def Check(self):
    ok=True
    ips=self.IpAddress.splitlines()
    ok=self.CheckValid(ok, self.Hostname, xlt("Please enter Host Name"))
    if self.isNew:
      ok=self.CheckValid(ok, not self.node.hosts4.get(self.Hostname) and not self.node.hosts6.get(self.Hostname), xlt("Host record already exists"))
    ok=self.CheckValid(ok, len(ips)>0, xlt("Please enter IP Address"))
    for ip in ips:
      ip=ip.strip()
      ok = self.CheckValid(ok, checkIpAddress(ip), xlt("Please enter valid IP Address"))
    ok=self.CheckValid(ok, timeToFloat(self.ttl), xlt("Please enter valid TTL"))
    if self.ttl6:
      ok=self.CheckValid(ok, timeToFloat(self.ttl6), xlt("Please enter valid AAAA TTL"))
    return ok


#=======================================================================
# Pages
#=======================================================================
  
def filledIp(ip):
  if ip.count(':'):
    parts=[]
    xp=ip.split(':')
    for n in xp:
      if n:
        parts.append(("0000"+n)[-4:])
      else:
        for _i in range(8-len(xp)):
          parts.append("0000")
    return ":".join(parts)
  else:
    n=ip.split('.')
    try:
      return "%02x.%02x.%02x.%02x" % (int(n[0]), int(n[1]), int(n[2]), int(n[3]))
    except:
      return ip


class zonePage(adm.NotebookPage):
  menus=[PageNewRecord, PageEditRecord, PageDeleteRecord]

  @staticmethod
  def EditDialog(rdtype):
    cls=RdataClass(rdataclass.IN, rdtype)
    if len(cls.__slots__) > 1:
      return MultiValRecords
    else:
      return SingleValRecords

  def prepare(self, node):
    if node:
      self.lastNode=node
    else:
      node=self.lastNode
    node.GetProperties()
    self.control.ClearAll()
    if not node.zone:
      self.control.AddColumn("", -1)
      self.control.AppendItem(0, xlt("Zone not available"))
      return False
    return True 
  
  def storeLastItem(self):
    self.lastHost=self.control.GetFocusText()
 
  def restoreLastItem(self):
    self.control.SetSelectFocus(self.lastHost)
    
  def OnItemDoubleClick(self, _evt):
    PageEditRecord.OnExecute(self.control, self)

  def GetName(self, idx):
    return self.control.GetItemText(idx, 0)

  def GetRdata(self, name, rdtype):
    return self.lastNode.others.get(name, {}).get(rdtype)
  
  def SetRdata(self, name, rdtype, data):
    rds=self.lastNode.others.get(name, {})
    if rds:
      rds[rdtype] = data
    else:
      self.lastNode.others[name] = {rdtype: data}

  def Delete(self, _parentWin, names, types):
    node=self.lastNode
    updater=node.Updater()
    for i in range(len(names)):
      if isinstance(types, list):
        rtype=types[i]
      else:
        rtype=types
      updater.delete(names[i], rtype)

    msg=node.GetServer().Send(updater)
    if msg.rcode() != rcode.NOERROR:
      self.SetStatus(xlt("DNS delete failed: %s") % rcode.to_text(msg.rcode()))
      return False
    for i in range(len(names)):
      name=names[i]
      if isinstance(types, list):
        rdtype=rdatatype.from_text(types[i])
        rdsl=node.others.get(name)
        if rdsl:
          if rdtype in rdsl:
            del rdsl[rdtype]
      elif types == rdatatype.CNAME:
        if node.cnames.get(name):
          del node.cnames[name]
      elif types == rdatatype.PTR:  
        if node.ptrs.get(name):
          del node.ptrs[name]
    return True
    

class HostsPage(zonePage):
  name=xlt("A/AAAA Hosts")
  order=1
  sorting=0
  menus=[PageNewRecord, PageEditRecord, PageDeleteHostRecord]

  @staticmethod
  def EditDialog(_rdtype):
    return HostRecord

  def GetDnsType(self):
    return xlt("A")
  
  def GetDataType(self, idx):
    ip=self.control.GetItemText(idx, 1)
    if checkIpAddress(ip) == 4:
      return rdatatype.A
    else:
      return rdatatype.AAAA
  
  def Delete(self, _parentWin, names, _types):
    node=self.lastNode
    updater=node.Updater()
    for name in names:
      if name in node.hosts4:
        updater.delete(name, "A")
      if name in node.hosts6:
        updater.delete(name, "AAAA")
    msg=node.GetServer().Send(updater)
    if msg.rcode() != rcode.NOERROR:
      adm.SetStatus(xlt("DNS delete failed: %s") % rcode.to_text(msg.rcode()))
      return False
    for name in names:
      if name in node.hosts4:
        del node.hosts4[name]
      if name in node.hosts6:
        del node.hosts6[name]
    return True


  def SortedByHost(self):
    hostnames=list(self.lastNode.hosts4.keys())
    hostnames.extend(list(self.lastNode.hosts6.keys()))
    hostnames = sorted(set(hostnames), key=lambda n: n.lower())

    self.control.DeleteAllItems()
    for name in hostnames:
      h4=self.lastNode.hosts4.get(name)
      h6=self.lastNode.hosts6.get(name)
      
      icon=self.lastNode.GetImageId('host')

      if h4:
        ttl=floatToTime(h4.ttl, -1)
        for h in h4:
          self.control.AppendItem(icon, [name, h.address, ttl])
          icon=0
          name=""
          ttl=""
      if h6:
        ttl=floatToTime(h6.ttl, -1)
        for h in h6:
          self.control.AppendItem(icon, [name, h.address, ttl])
          icon=0
          name=""
          ttl=""

  def SortedByIp(self):
    ip4=[]
    for name, h4 in self.lastNode.hosts4.items():
      if h4:
        for h in h4:
          ip4.append( (name, h.address, h4.ttl, 4))
    ip6=[]
    for name, h6 in self.lastNode.hosts6.items():
      if h6:
        for h in h6:
          ip6.append( (name, h.address, h6.ttl, 6))

                        
    ips =      sorted(ip4, key=lambda x: filledIp(x[1]))
    ips.extend(sorted(ip6, key=lambda x: filledIp(x[1])))

    self.control.DeleteAllItems()

    last=None    
    for name, addr, ttl, protocol in ips:
      icon=self.lastNode.GetImageId('ipaddr%d' % protocol)
      if last==name:
        self.control.AppendItem(0, ["", addr, ""])
      else:
        last=name
        self.control.AppendItem(icon, [name, addr, floatToTime(ttl, -1)])
      

  def Display(self, node, _detached=False):
    if not node or node != self.lastNode:
      self.storeLastItem()
      
      if not self.prepare(node):
        return
      
      self.control.AddColumn(xlt("Name"), 30)
      self.control.AddColumn(xlt("Address"), 20)
      self.control.AddColumn(xlt("TTL"), 10)
      self.RestoreListcols()

    self.OnColClick()
    self.restoreLastItem()
        

  def OnColClick(self, evt=None):
    if not self.lastNode.soa:
      return
    
    if evt:
      col=evt.GetColumn()
      if col in [0,1]:
        if col != self.sorting:
          HostsPage.sorting=col
        else:
          return
      else:
        return
        
    if self.sorting:
      self.SortedByIp()
    else:
      self.SortedByHost()


  
class CNAMEsPage(zonePage):
  name=xlt("CNAMEs")
  order=2
  
  @staticmethod
  def EditDialog(_rdtype):
    return SingleValRecord

  def GetDnsType(self):
    return "CNAME"
  def GetDataType(self, unused):
    return rdatatype.CNAME

  def GetRdata(self, name, _rdtype):
    return self.lastNode.cnames.get(name)

  def SetRdata(self, name, _rdtype, data):
    self.lastNode.cnames[name] = data
    
  def Delete(self, parentWin, names, _types):
    return zonePage.Delete(self, parentWin, names, rdatatype.CNAME)
  
  def Display(self, node, _detached):
    if not node or node != self.lastNode:
      if not self.prepare(node):
        return

      self.storeLastItem()
            
      node=self.lastNode
      self.control.AddColumn(xlt("Name"), 30)
      self.control.AddColumn(xlt("Target"), 30)
      self.control.AddColumn(xlt("TTL"), 5)
      self.RestoreListcols()

      icon=node.GetImageId('cname')
      for cname in sorted(node.cnames.keys()):
        rds=node.cnames[cname]
        self.control.AppendItem(icon, [cname, rds[0].target, floatToTime(rds.ttl, -1)])

      self.restoreLastItem()

       
      
class PTRsPage(zonePage):
  name=xlt("PTR")
  order=1
  menus=[PageNewRecord, PageEditRecord, PageDeleteRecord]

  @staticmethod
  def EditDialog(_rdtype):
    return SingleValRecord

  def GetDnsType(self):
    return "PTR"
  def GetDataType(self, unused):
    return rdatatype.PTR
  
  def GetName(self, idx):
    name=self.control.GetItemText(idx, 0)
    addr=(DnsRevName(name).to_text())[:-len(self.lastNode.partialZonename)-2]
    return addr
  
  def GetRdata(self, name, _rdtype):
    return self.lastNode.ptrs.get(name)
  
  def SetRdata(self, name, _rdtype, data):
    self.lastNode.ptrs[name] = data
  
  def Delete(self, parentWin, names, _types):
    ptrs=[]
    for n in names:
      try:
        ptrs.append(str(DnsRevName(n))[:-2-len(self.lastNode.partialZonename)])
      except:
        ptrs.append(n.split(' ')[0])
    
    return zonePage.Delete(self, parentWin, ptrs, rdatatype.PTR)
  
  def Display(self, node, _detached):
    if not node or node != self.lastNode:
      self.storeLastItem()
      
      if not self.prepare(node):
        return
      node=self.lastNode
      self.control.AddColumn(xlt("Address"), 10)
      self.control.AddColumn(xlt("Target"), 30)
      self.control.AddColumn(xlt("TTL"), 5)
      self.RestoreListcols()

      icon=node.GetImageId('ptr')
      
      ips=[]
      for ptr in node.ptrs.keys():
        rds=node.ptrs[ptr]
        name=DnsAbsName(ptr, node.partialZonename)
        try:
          adr=DnsRevAddress(name)
        except:
          adr="%s <invalid>" % ptr
        ips.append( (adr, rds[0].target, floatToTime(rds.ttl, -1)))

      for ip in sorted(ips, key=(lambda x: filledIp(x[0]))):
        self.control.AppendItem(icon, list(ip))
      
      self.restoreLastItem()


class OTHERsPage(zonePage):
  name=xlt("Others")
  order=5
  menus=[PageNewAskRecord, PageEditRecord, PageDeleteRecord]

  def GetDnsType(self):
    return "WHAT"
  
  def GetDataType(self, idx):
    while idx >= 0:
      txt=self.control.GetItemText(idx, 1)
      if txt:
        return rdatatype.from_text(txt)
      idx -= 1
    return None

  
  def Display(self, node, _detached):
    if not node or node != self.lastNode:
      self.storeLastItem()
      if not self.prepare(node):
        return
      node=self.lastNode
      self.control.AddColumn(xlt("Name"), 10)
      self.control.AddColumn(xlt("Type"), 5)
      self.control.AddColumn(xlt("Values"), 40)
      self.control.AddColumn(xlt("TTL"), 5)
      self.RestoreListcols()

      for other in sorted(node.others.keys()):
        rdss=node.others[other]
        for rds in rdss.values():
          icon=node.GetImageId('other')
          dnstype=rdatatype.to_text(rds.rdtype)
          name=other
          for rd in rds:
            values=[]
            for slot in rd.__slots__:
              value=eval("rd.%s" % slot)
              if isinstance(value, list):
                if len(value) > 1:
                  logger.debug("Value list dimensions > 1: %s", str(value))
                value=" ".join(value)
                
              values.append("%s=%s" % (slot, value))
            self.control.AppendItem(icon, [name, dnstype, ", ".join(values), floatToTime(rds.ttl, -1)])
            icon=0
            name=""
            dnstype=""
      self.restoreLastItem()

pageinfo=[HostsPage, CNAMEsPage, PTRsPage, OTHERsPage]
nodeinfo= [ 
           { "class": Zone, "parents": ["Server", "Zone"], "sort": 10, "pages": "HostsPage CNAMEsPage OTHERsPage" },
           { "class": RevZone, "parents": ["Server", "RevZone"], "sort": 20, "pages": "PTRsPage" },
           ]

menuinfo=[ { 'class': IncrementSerial, 'nodeclasses': [Zone, RevZone], 'sort': 10 },
           { 'class': CleanDanglingPtr, 'nodeclasses': RevZone, 'sort': 30 },
           { 'class': RegisterZone, 'sort': 80 },
           { 'class': RegisterRevZone, 'sort': 81 },
           { 'class': UnregisterZone, 'sort': 82 }
           ]

