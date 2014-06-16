# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

import adm
import logger
import sys, os, zipfile, shutil
import wx.html
import requests
try:
  import Crypto.PublicKey.RSA, Crypto.Hash.SHA, Crypto.Signature.PKCS1_v1_5
except:
  Crypto=None
from wh import xlt, copytree, modPath, localizePath
from xmlhelp import Document as XmlDocument
import version as admVersion

class PasswordDlg(adm.Dialog):
  def __init__(self, parentWin, msg, caption):
    adm.Dialog.__init__(self, parentWin)
    self.SetTitle(caption)
    self.staticPassword=msg

  def Save(self):
    return True

class AboutDlg(adm.Dialog):
  def __init__(self, parent):
    super(AboutDlg, self).__init__(parent)
    stdFont=self.GetFont()
    pt=stdFont.GetPointSize()
    family=stdFont.GetFamily()
    bigFont=wx.Font(pt*2 , family, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    mediumFont=wx.Font(pt*1.4, family, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    self['Admin'].SetFont(bigFont)
    self['Version'].SetFont(mediumFont)

    self.Admin="Admin4"
    self.Version=xlt("Version %s") % admVersion.version

    if not adm.IsPackaged():
        self.Revision = xlt("(%s)\nunknown changes") % admVersion.revDate 
        rev=xlt("unknown")
    elif admVersion.revLocalChange:
      if admVersion.revDirty:
        self.Revision = xlt("(+ %s)\nLocally changed/uncommitted") % admVersion.modDate 
        rev=xlt("locally changed %s") % admVersion.modDate
      else:
        self.Revision = xlt("(+ %s)\nLocally committed") % admVersion.revDate 
        rev="+ %s" % admVersion.revDate
    elif admVersion.revOriginChange:
      self.Revision = "(+ %s)" % admVersion.revDate
      rev="+ %s" % admVersion.revDate 
    else:
      if admVersion.tagDate:
        self.Revision = "(%s)" % admVersion.tagDate
      rev=admVersion.tagDate 
    self.Description = admVersion.description
    copyrights=[admVersion.copyright]
    licenses=[xlt("%s\nFor details see LICENSE.TXT") % admVersion.license]

    lv=self['Modules']
    lv.AddColumn(xlt("Module"), "PostgreSQL")
    lv.AddColumn(xlt("Ver."), "2.4.5")
    lv.AddColumn(xlt("Rev."), "2014-01-01++")
    lv.AddColumn(xlt("Description"), 30)
    
    vals=["Core", admVersion.version, rev, xlt("Admin4 core framework")]
    lv.AppendItem(adm.images.GetId("Admin4Small"), vals)

    wxver=wx.version().split(' ')
    v=wxver[0].split('.')
    vals=["wxWidgets", '.'.join(v[:3]), '.'.join(v[3:]), "wxWidgets %s" % ' '.join(wxver[1:])]
    lv.AppendItem(adm.images.GetId("wxWidgets"), vals)

    for modid, mod in adm.modules.items():
      vals=[]
      mi=mod.moduleinfo
      modulename=mi.get('modulename', modid)
      vals.append(modulename)
      vals.append(mi.get('version'))
      rev=mi.get('revision')
      if rev:
        vals.append(rev)
      else:
        vals.append("")
      vals.append(mi.get('description'))
      serverclass=mi['serverclass'].__name__.split('.')[-1]
      icon=adm.images.GetId(os.path.join(modid, serverclass))
      lv.AppendItem(icon, vals)
      credits=mi.get('credits')
      if credits:
        copyrights.append(credits)
      license=mi.get("license")
      if license:
        licenses.append("%s: %s" % (modulename, license))
    self.Copyright = "\n\n".join(copyrights).replace("(c)", unichr(169))
    
    licenses.append("Additional licenses from libraries used may apply.")
    self.License="\n\n".join(licenses)
  

class PreferencesDlg(adm.CheckedDialog):
  def __init__(self, parentWin):
    adm.Dialog.__init__(self, parentWin)
    self.panels=[]

    notebook=self['Notebook']
    for panelclass in adm.getAllPreferencePanelClasses():
        panel=panelclass(self, notebook)
        self.panels.append(panel)
        notebook.AddPage(panel, panel.name)

  def Go(self):
    for panel in self.panels:
      panel.Go()
      panel.SetUnchanged()

  def GetChanged(self):
    for panel in self.panels:
      if panel.GetChanged():
        return True
    return False

  def Check(self):
    for panel in self.panels:
      if hasattr(panel, "Check"):
        if not panel.Check():
          return False
    return True

  def Save(self):
    for panel in self.panels:
      if not panel.Save():
        return False
    return True


class HintDlg(adm.Dialog):

  @staticmethod
  def WantHint(hint, module):
    return adm.config.GetWantHint(hint, module)
  
  def __init__(self, parentWin, hint, hintModule, title, args):
    adm.Dialog.__init__(self, parentWin)
    self.hint=hint
    self.hintModule=hintModule
    self.title=title
    if args:
      self.args=args
    else:
      self.args={}
    args['appName'] = adm.appTitle
    
  def AddExtraControls(self, res):
    self.browser=wx.html.HtmlWindow(self)
    res.AttachUnknownControl("HtmlWindow", self.browser)
    

  def Go(self):
    f=open(localizePath(modPath(os.path.join("hints", "%s.html" % self.hint), self.hintModule)))
    html=f.read()
    f.close()
    for tag, value in self.args.items():
      html=html.replace("$%s" % tag.upper(), value.encode('utf-8'))
      
    self.browser.SetPage(html.decode('utf-8'))
    if not self.title:
      self.title=self.browser.GetOpenedPageTitle()
    if self.title:
      self.SetTitle(self.title)
    else:
      self.SetTitle(xlt("%s hint") % adm.appTitle)
    
  def Execute(self):
    adm.config.SetWantHint(self.hint, self.hintModule, not self.NeverShowAgain)
    return True
  


class UpdateDlg(adm.Dialog):
  def __init__(self, parentWin):
    adm.Dialog.__init__(self, parentWin)
    self.SetTitle(xlt("Update %s modules") % adm.appTitle)

    self.onlineUpdateInfo=None
    self.onlineTimeout=5

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
      self.Check()
  
  def OnCheckUpdate(self, evt):
    self.onlineUpdateInfo=None
    try:
      # no need use SSL here; we'll verify the update.xml later
      response=requests.get("http://www.admin4.org/update.xml", timeout=self.onlineTimeout, proxies=adm.GetProxies())
      response.raise_for_status()
      xmlText=response.text
      sigres=requests.get("http://www.admin4.org/update.sign", timeout=self.onlineTimeout, proxies=adm.GetProxies())
      sigres.raise_for_status()
      signature=sigres.content
      
    except Exception as ex:
      print ex
      self.ModuleInfo=xlt("Online update check failed.\n\nError reported:\n  %s") % str(ex)
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
        self.ModuleInfo = xlt("Online update check failed:\nupdate.xml cryptographic signature not valid.")
        return
    
    self.onlineUpdateInfo=XmlDocument.parse(xmlText)
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
 
  
  
class Preferences(adm.NotebookPanel):
  name="General"
  
  def Go(self):
    self.ConfirmDeletes=adm.confirmDeletes
    self.MonthlyChecks=adm.monthlyChecks
    self.Proxy=adm.proxy

  def Save(self):
    adm.confirmDeletes=self.ConfirmDeletes
    adm.monthyChecks=self.MonthlyChecks
    adm.proxy=self.Proxy
    adm.config.Write("ConfirmDeletes", adm.confirmDeletes)
    adm.config.Write("MonthlyChecks", adm.monthlyChecks)
    adm.config.Write("Proxy", adm.proxy)
    return True

  @staticmethod
  def Init():
    adm.confirmDeletes=adm.config.Read("ConfirmDeletes", True)
    adm.monthlyChecks=adm.config.Read("MonthlyChecks", True)
    adm.proxy=adm.config.Read("Proxy")


  