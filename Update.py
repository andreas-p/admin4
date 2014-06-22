# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import wx
import requests, sys, os, zipfile, shutil
import adm, logger
import version as admVersion
from wh import xlt, copytree
from xmlhelp import Document as XmlDocument
import time, threading

try:
  import Crypto.PublicKey.RSA, Crypto.Hash.SHA, Crypto.Signature.PKCS1_v1_5
except:
  Crypto=None

class UpdateThread(threading.Thread):
  
  def __init__(self, frame):
    self.frame=frame
    threading.Thread.__init__(self)
    
  def run(self):
    update=OnlineUpdate()
    if update.IsValid():
      adm.updateInfo=update
      if update.UpdateAvailable():
        wx.CallAfter(self.frame.OnUpdate)
    elif update.exception:
      wx.CallAfter(wx.MessageBox,
                   xlt("Connection error while trying to retrieve update information from the update server.\nCheck network connectivity and proxy settings!"), 
                   xlt("Communication error"), wx.ICON_EXCLAMATION)
       
  
def CheckAutoUpdate(frame):
  if adm.updateCheckPeriod:
    lastUpdate=adm.config.Read('LastUpdateCheck', 0)
    if not lastUpdate or lastUpdate+adm.updateCheckPeriod*24*60*60 < time.time():
      thread=UpdateThread(frame)
      thread.start()


class OnlineUpdate:
  def __init__(self):
    timeout=5
    self.info=None
    self.message=None
    self.exception=None
    
    if not Crypto:
      self.message=xlt("No Crypto lib available.")
      return
    try:
      # no need to use SSL here; we'll verify the update.xml later
      response=requests.get("http://www.admin4.org/update.xml", timeout=timeout, proxies=adm.GetProxies())
      response.raise_for_status()
      xmlText=response.text
      sigres=requests.get("http://www.admin4.org/update.sign", timeout=timeout, proxies=adm.GetProxies())
      sigres.raise_for_status()
      signature=sigres.content
      
    except Exception as ex:
      self.exception = ex
      self.message=xlt("Online update check failed.\n\nError reported:\n  %s") % str(ex)
      return

    if True: # we want to check the signature
      f=open(os.path.join(adm.loaddir, 'admin4.pubkey'))
      keyBytes=f.read()
      f.close()

      # https://www.dlitz.net/software/pycrypto/api/current/Crypto-module.html
      pubkey=Crypto.PublicKey.RSA.importKey(keyBytes)
      verifier = Crypto.Signature.PKCS1_v1_5.new(pubkey)
      hash=Crypto.Hash.SHA.new(xmlText)

      if not verifier.verify(hash, signature):
        self.message = xlt("Online update check failed:\nupdate.xml cryptographic signature not valid.")
        return
    
    self.info=XmlDocument.parse(xmlText)
    adm.config.Write('LastUpdateCheck', time.time())
  
  def IsValid(self):
    return self.info != None
  
  def UpdateAvailable(self):
    if self.info:
      status=self.info.getElementText('status')
      return status > admVersion.revDate
    return False


class UpdateDlg(adm.Dialog):
  def __init__(self, parentWin):
    adm.Dialog.__init__(self, parentWin)
    self.SetTitle(xlt("Update %s modules") % adm.appTitle)

    self.onlineUpdateInfo=None

    self.Bind("Source")
    self.Bind("Search", self.OnSearch)
    self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnCheck)
    if Crypto:
      self.Bind("CheckUpdate", self.OnCheckUpdate)
    else:
      self['CheckUpdate'].Disable()
    
  def Go(self):
    if not os.access(adm.loaddir, os.W_OK):
      self.EnableControls("Target Search Ok", False)
      self.ModuleInfo=xlt("Update not possible:\nProgram directory cannot be written.")
      self['Ok'].Disable()
    else:
      self.DoCheckUpdate()
      self.Check()
  
       
  def OnCheckUpdate(self, evt):
    self.ModuleInfo=xlt("Checking...")
    wx.Yield()
    adm.updateInfo=OnlineUpdate()
    self.DoCheckUpdate()
  
  def DoCheckUpdate(self):
    if adm.updateInfo:
      self.onlineUpdateInfo = adm.updateInfo.info
      if not adm.updateInfo.IsValid():
        self.ModuleInfo=adm.updateInfo.message
    self.OnCheck()

   
  def OnSearch(self, evt):
    dlg=wx.FileDialog(self, xlt("Select Update dir or zip"), wildcard="Module ZIP (*.zip)|*.zip|Module (*.py)|*.py", style=wx.FD_CHANGE_DIR|wx.FD_FILE_MUST_EXIST|wx.FD_OPEN)
    if dlg.ShowModal() == wx.ID_OK:
      path=dlg.GetPath()
      if path.endswith('.py'):
        path = os.path.dirname(path)
      self.Source=path
      self.OnCheck()

    
  def Check(self):
    if self['Notebook'].GetSelection():
      modSrc=None
      canInstall=True
      self.ModuleInfo = xlt("Please select module update ZIP file or directory.")
  
      fnp=os.path.basename(self.Source).split('-')
      self.modid=fnp[0]
      if os.path.isdir(self.Source):
        initMod=os.path.join(self.Source, "__init__.py")
        if not os.path.exists(initMod):
          initMod=os.path.join(self.Source, "__version.py")
        if os.path.exists(initMod):
          try:
            f=open(initMod, "r")
            modSrc=f.read()
            f.close
          except:
            self.ModuleInfo = xlt("Module file %s cannot be opened.") % initMod
            return False
        else: # core
          self.ModuleInfo = xlt("%s is no module.") % self.Source
          return False
      elif self.Source.lower().endswith(".zip") and os.path.exists(self.Source) and zipfile.is_zipfile(self.Source):
        if len(fnp) < 2:
          self.Module = xlt("%s is no update zip.") % self.Source
          return False
        try:
          zip=zipfile.ZipFile(self.Source)
          names=zip.namelist()
          zipDir=names[0]
          if self.modid.lower() != "admin4":
            if zipDir.split('-')[0] != self.modid:
              self.ModuleInfo=xlt("Update zip %s doesn't contain module directory %s.") % ( self.Source, self.modid)
              return False
            
          for f in names:
            if not f.startswith(zipDir):
              self.ModuleInfo=xlt("Update zip %s contains additional non-module data: %s") % (self.Source, f)
              return False
            
          initMod="%s__init__.py" % zipDir
          if not initMod in names:
            initMod="%s__version.py" % zipDir
          if initMod in names:
            f=zip.open(initMod)
            modSrc=f.read()
            zip.close()
          
        except Exception as _e:
          self.ModuleInfo=xlt("Error while reading moduleinfo from zip %s") % self.Source
          return False
  
      if modSrc:
        moduleinfo=None
        version=None
        tagDate=revDate=modDate=None
        revLocalChange=revOriginChange=revDirty=False
        requiredAdmVersion="2.1.0"
        
        try:
          sys.skipSetupInit=True
          exec modSrc
          del sys.skipSetupInit
        except Exception as _e:
          self.ModuleInfo=xlt("Error executing version code in %s") % self.Source
          del sys.skipSetupInit
          return False
  
        if moduleinfo:
          try:
            self.modname=moduleinfo['modulename']
            revision= moduleinfo.get('revision')
            msg=[ xlt("Module %s : %s") % (self.modname, moduleinfo['description']), "" ]
            
            if revision:
              delta=""
              installed=adm.modules.get(self.modid)
              if installed:
                instrev=installed.moduleinfo.get('revision')
                if instrev:
                  if instrev == revision:
                    delta = xlt(" - already installed")
                  elif instrev > revision:
                    delta=xlt(" - %s already installed" % instrev)
                else:
                  delta=xlt(" - can't check installed")
  
                msg.append(xlt("Version %s Revision %s%s") % (moduleinfo['version'], revision, delta))
            else:
              msg.append(xlt("Version %s Revision unknown") % moduleinfo['version'])
  
            rqVer=moduleinfo['requiredAdmVersion']
            msg.append("")
            if rqVer > admVersion.version:
              msg.append(xlt("Module requires Admin4 Core version %s") % rqVer)
              canInstall=False
            else:
              testedVer=moduleinfo.get('testedAdmVersion')
              if testedVer and testedVer < admVersion.version:
                msg.append(xlt("not verified with this Admin4 Core version"))
          except Exception as _e:
            logger.exception("Format error of %s moduleinfo", self.Source)
            return False
          
          self.ModuleInfo="\n".join(msg)
          return canInstall
        elif version:
          if revLocalChange:
            if revDirty:
              rev=modDate
            else:
              rev=revDate
          elif revOriginChange:
            rev=revDate 
          else:
            rev=tagDate 
          self.modname="Core"
          msg=[ xlt("%s Core") % adm.appTitle, xlt("Version %s (%s)") % (version, rev), "" ]
          if version < admVersion.version:
            canInstall=False
            msg.append(xlt("Update version older than current Core version %s") % admVersion.version)
          elif version == admVersion.version:
            msg.append(xlt("Update has same same version as current Core"))
          elif requiredAdmVersion > admVersion.version:
            msg.append(xlt("Full install of %s %s or newer required") % (adm.appTitle, requiredAdmVersion))
            canInstall=False
          if revDirty:
            msg.append(xlt("uncommitted data present!"))
          self.ModuleInfo="\n".join(msg)
          return canInstall
  
      return False
    else: # Notebook.GetSelection=0, online update
      if not Crypto:
        self.ModuleInfo=xlt("No crypto functions available;\nonline update not possible.")
        return False
      
      if self.onlineUpdateInfo:
        msg=[]
        canUpdate=True
        haveUpdate=False
        self.hasCoreUpdate=False
        try:
          el=self.onlineUpdateInfo.getElement('updateUrl')
          self.updateUrl=el.getText().strip()
          self.updateZipHash=el.getAttribute('sha1')
          el=self.onlineUpdateInfo.getElement('minorUpdateUrl')
          self.minorUpdateUrl=el.getText().strip()
          self.minorUpdateZipHash=el.getAttribute('sha1')
          status=self.onlineUpdateInfo.getElementText('status')

          msg.append(xlt("Update info as of %s:") % status)
          #msg.append("")
          alerts=self.onlineUpdateInfo.getElements('alert')
          if alerts:
            alert=alerts[0].getText()
            if alert.strip():
              msg.append(alert)
          modules=self.onlineUpdateInfo.getElements('module')
          
          for module in modules:
            name=module.getAttribute('name')
            version=module.getAttribute('version')
            if name == "Core":
              info = { 'app': adm.appTitle, 'old': admVersion.version, 'new': version }
              if admVersion.version < version:
                msg.append(xlt("  Core: %(old)s can be updated to %(new)s") % info)
                haveUpdate=True
                self.hasCoreUpdate=True
              elif admVersion.version == version and status > admVersion.revDate:
                msg.append(xlt("  Core: %(new)s minor update.") % info)
                haveUpdate=True
            elif name == "Lib":
              if admVersion.libVersion < version:
                msg=[msg[0], xlt("There is a newer %(app)s Core version %(new)s available.\nHowever, the current version %(old)s can't update online.\nPlease download and install a full package manually.") % info]
                if not adm.IsPackaged():
                  msg.append(xlt("In addition, the library requirements have changed;\ncheck the new documentation."))
                self.ModuleInfo = "\n".join(msg)
                return False
            else:
              mod=adm.modules.get(name)
              rev=mod.moduleinfo.get('revision')
              if rev:
                info= { 'name': mod.moduleinfo['modulename'], 'old': rev, 'new': version }
                if rev < version:
                  if self.hasCoreUpdate:
                    msg.append(xlt("  %(name)s: %(old)s upgrade to %(new)s") % info)
                  else:
                    msg.append(xlt("Current %(name)s module revision %(old)s can be updated to  %(new)s.") % info)
                    haveUpdate=True
                elif rev > version:
                  if self.hasCoreUpdate:
                    msg.append(xlt("  %(name)s: %(old)s DOWNGRADE to %(new)s, please check") % info)
              
        except Exception as ex:
          print ex
          msg=[xlt("Online update information invalid.")]
          return False
        if haveUpdate and canUpdate:
          msg.insert(1, xlt("An update is available."))
        else:
          msg.append(xlt("No update available."))
        
        self.ModuleInfo = "\n".join(msg)
        return haveUpdate and canUpdate
      else:
        self.ModuleInfo = ""
        return False
  
  
  def DoInstall(self, tmpDir, source):
    if not os.path.isdir(source):
      try:
        zip=zipfile.ZipFile(source)
        zipDir=zip.namelist()[0]
        zip.extractall(tmpDir)
        zip.close()
      except Exception as _e:
        self.ModuleInfo = xlt("Error extracting\n%s") % self.Source
        logger.exception("Error extracting %s", self.Source)
        return False

      source = os.path.join(tmpDir, zipDir)

    if self.modname == "Core":
      destination=adm.loaddir
    else:
      destination=os.path.join(adm.loaddir, self.modid)
      
    copytree(source, destination)
    try: shutil.rmtree(tmpDir)
    except: pass
    return True
  
  def prepareTmp(self):
    tmpDir=os.path.join(adm.loaddir, "_update")
    
    try: shutil.rmtree(tmpDir)
    except: pass
    try: os.mkdir(tmpDir)
    except: pass
    return tmpDir
  
  def DoDownload(self, tmpDir, url, hash):
      self.ModuleInfo = xlt("Downloading...\n\n%s") % url
      try:
        response=requests.get(url, timeout=self.onlineTimeout*5, proxies=adm.GetProxies())
        response.raise_for_status()
      except Exception as ex:
        self.ModuleInfo = xlt("The download failed:\n%s\n\n%s") % (str(ex), self.updateUrl)
        return None
      
      content=response.content
      hash=Crypto.Hash.SHA.new(content)
      if hash.hexdigest() != hash:
        self.ModuleInfo = xlt("The download failed:\nSHA1 checksum invalid.\n\n%s") % self.updateUrl
        self['Ok'].Disable()
        return None
      
      source=os.path.join(tmpDir, "Admin4-OnlineUpdate-Src.zip")
      f=open(source, "w")
      f.write(content)
      f.close()
      return source
    
    
  def Execute(self):
    tmpDir=self.prepareTmp()
    if self['Notebook'].GetSelection():
      self.ModuleInfo = xlt("Installing...")
      self.DoInstall(tmpDir, self.Source)
      updateInfo=xlt("Installed new module %s") % self.modname      
    else:
      self.modname = "Core"
      if self.hasCoreUpdate and self.updateUrl != self.minorUpdateUrl:
        source=self.DoDownload(tmpDir, self.updateUrl, self.updateZipHash)
        if not source:
          return False
        self.ModuleInfo = xlt("Updating...")
        if not self.DoInstall(tmpDir, source):
          return False

        tmpDir=self.prepareTmp()
        
      source=self.DoDownload(tmpDir, self.minorUpdateUrl, self.minorUpdateZipHash)
      if not source:
        return False
      self.ModuleInfo = xlt("Updating...")
      self.DoInstall(tmpDir, source)
      updateInfo=xlt("Update installed")     
    
    dlg=wx.MessageDialog(self, xlt("New program files require restart.\nExit now?"), 
                         updateInfo,
                         wx.YES_NO|wx.NO_DEFAULT)
    if dlg.ShowModal() == wx.ID_YES:
      sys.exit()
    return True
