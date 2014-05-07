# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import version
import wx
import logger

app = wx.App()

import adm
import sys,os
import xmlres
import config
import getopt
import frame
from wh import StringType, SetLoaddir

logger.loglevel=logger.LOGLEVEL.DEBUG
IGNORE_MODULES=['xrced', 'dist', 'build', 'lib', 'include', 'mpl-data', 'tcl']

def getRevision(revStr, modRevision, modDate):
  s=revStr.split()
  if len(s) > 5:
    revision=int(s[2])
    if revision > modRevision:
      modRevision=revision
      modDate=s[3]
  return modRevision, modDate

    

def loadModules(modlist=None):
  adm.mainRevision=0
  adm.mainDate=version.revDate
  
  ignorePaths = [ os.path.abspath(fn) for fn in [sys.argv[0], __file__]]
  names=os.listdir(adm.loaddir)

  for modid in names:
    if modid.startswith('.'):
      continue
    path=os.path.join(adm.loaddir, modid)

    if path in ignorePaths:
      continue
    loadModule(modid, path, modlist)


def loadModule(modid, path, modlist=None):
    if os.path.isdir(path):
      if modid.startswith('_'):
        return
      if modid in IGNORE_MODULES:
        return
      if not os.path.exists(os.path.join(path, "__init__.py")) and not os.path.exists(os.path.join(path, "__init__.pyc")):
        logger.debug("No python module: %s", modid)
        return
      adm.availableModules.append(modid)
      if modlist and modid not in modlist:
        logger.debug("Module %s ignored", modid)
        return

      mod=__import__(modid)
      if not mod:
        return
      try:
        __import__("%s._requires" % modid)
        requires=getattr(mod, "_requires")
        if not requires.GetPrerequisites():
          logger.debug("Module %s Prerequisites not met", modid)
          return
      except:
        pass
      
      modname=mod.moduleinfo['name']
      adm.modules[modid] = mod
      mod.moduleinfo['class'] = modid
      if not mod.moduleinfo.get('serverclass'):
        if not hasattr(mod, "Server"):
          logger.debug("Module %s has no Server import" % modid)
          return
        if not hasattr(mod.Server, "Server"):
          logger.debug("Module %s.Server has no Server class" % modid)
          return
        mod.moduleinfo['serverclass'] = mod.Server.Server

      logger.debug("Loading Module %s '%s'", modid, modname)
      if hasattr(mod, "Preferences"):
        mod.moduleinfo['preferences'] = mod.Preferences

      modRevision=mod.moduleinfo.get('revision', 0)
      modDate=None

      if hasattr(mod, "revision"):
        modRevision, modDate = getRevision(mod.revision, modRevision, modDate)

      nodelist={}
      menulist=[]

      for nodefile in os.listdir(path):
        if nodefile.startswith("_") or not nodefile.endswith(".py"):
          continue
        nodemodname=nodefile[:-3]
        nodemod="%s.%s" % (modid, nodemodname)

        try:
          node=getattr(mod, nodemodname)
        except:
          try:
            __import__(nodemod)
            node=getattr(mod, nodemodname)
          except Exception as e:
            logger.debug("No Module member: %s - %s", nodemodname, e)
            continue

        # get menuinfo
        if hasattr(node, "menuinfo"):
          menulist.extend(node.menuinfo)
        if hasattr(node, "pageinfo"):
          pages=mod.moduleinfo.get('pages')
          if pages:
            pages.extend(node.pageinfo)
          else:
            mod.moduleinfo['pages'] = node.pageinfo

        # check revisions
        if hasattr(node, "revision"):
          modRevision, modDate = getRevision(node.revision, modRevision, modDate)


        if not hasattr(node, "nodeinfo"):
          logger.debug("No nodeinfo in %s", nodefile)
          continue
        nodeinfo=node.nodeinfo

        # get nodeinfo
        if not isinstance(nodeinfo, list):
          nodeinfo=[nodeinfo]
        for ni in nodeinfo:
          nodename=ni['class'].__name__
          nodelist[nodename]=ni
          ni['children']=[]
          logger.debug("Loading node %s.%s", modid, nodename)

      for nodename, nodeinfo in nodelist.items():
        childlist=[]
        # assign childs to nodeinfo
        for node, ni in nodelist.items():
          parents=ni.get('parents')
          if not isinstance(parents, list):
            parents=[parents]
          for p in parents:
            if p and not isinstance(p, StringType):
              p=p.__name__
            if p == nodename:
              s=ni.get('sort')
              if s:
                child="%s:%s" % (str(s), ni['class'].__name__)
              else:
                child=ni['class'].__name__
              childlist.append(child)

        childlist.sort()
        for child in childlist:
          cn=child[child.find(':')+1:]
          nodeinfo['children'].append(cn)

      mod.moduleinfo['nodes']=nodelist

      # sort and remember module menuinfo
      menus=[]
      for mi in menulist:
        cls=mi['class']
        if hasattr(cls, "OnExecute"):
          cls.OnExecute._classname_=cls.__name__
        else:
          logger.debug("Menu %s has no OnExecute", str(cls))
          continue
        nodeclasses=mi.get('nodeclasses')
        if nodeclasses:
          if isinstance(nodeclasses, str):
            nodeclasses=nodeclasses.split(' ')
          elif not isinstance(nodeclasses, list):
            nodeclasses=[nodeclasses]
          ncs=[]
          for nc in nodeclasses:
            if isinstance(nc, StringType):
              nl=nodelist.get(nc)
              if nl:
                nc=nl['class']
              else:
                logger.debug("Menu %s references unknown class %s", str(mi['class']), nc)
            ncs.append(nc)
          mi['nodeclasses'] = ncs
        menus.append(mi)
      mod.moduleinfo['menus']=sorted(menus, key=lambda mi: mi.get('sort'))
      tools=[]
      for mi in mod.moduleinfo['menus']:
        if hasattr(mi['class'], 'toolbitmap'):
          tools.append(mi)
      mod.moduleinfo['tools']=tools
      
      # sort pages
      pages=mod.moduleinfo.get('pages')
      if pages:
        mod.moduleinfo['pages'] = sorted(pages, key=lambda pageClass: pageClass.order)
    
      mod.moduleinfo['revision']=modRevision
      mod.moduleinfo['date']=modDate
      logger.debug("Module %s revision %s, date %s", modid, modRevision, modDate)


    elif path.endswith((".py", '.pyc')):
      if modid.startswith('__'):
        return
      mod=__import__(modid[:modid.rfind('.')])
      if hasattr(mod, "revision"):
        adm.mainRevision, adm.mainDate=getRevision(mod.revision, adm.mainRevision, adm.mainDate)

  
def LoggerExceptionHook(exType, args, tb):
  sys.__excepthook__(exType, args, tb)
  logger.sysexception(exType, args, tb)


def main(argv):
  adm.app = app
  adm.loaddir=os.path.dirname(os.path.abspath(argv[0]))
  SetLoaddir(adm.loaddir)


  _dn, an=os.path.split(argv[0])
  dot=an.rfind('.')
  if dot > 0:
    adm.appname=an[0:dot]
  else:
    adm.appname=an

  sys.excepthook=LoggerExceptionHook
  if wx.VERSION < (2,9):
    logger.debug("Using old wxPython version %s", wx.version())
  modules=[]

  opts, args = getopt.getopt(argv[1:], "m:n:", ["modules=", "name="])
  for opt in opts:
    if opt[0] in ['-m', '--modules']:
      modules = map(lambda x: "mod%s" % x.capitalize(), opt[1].split(','))
    elif opt[0] in ['-n', '--name']:
      adm.appname=opt[1]
  
  app.SetAppName(adm.appname)
  adm.config=config.Config(adm.appname)
  frame.LoggingDialog.Init()

  adm.appTitle=adm.config.Read("Title", adm.appname.title())
  if wx.VERSION > (2,9):
    app.SetAppDisplayName(adm.appTitle)
    from version import vendor, vendorDisplay
    app.SetVendorName(vendor)
    app.SetVendorDisplayName(vendorDisplay)

  
  if not modules:
    modules=adm.config.Read("Modules", [])
  if not modules:
    dot=adm.appname.find('-')
    if dot>0:
      modules=["mod" + adm.appname[:dot].capitalize()]

  loadModules(modules)
  xmlres.init(adm.loaddir)

  adm.mainframe=frame.DetailFrame(None, adm.appTitle, args)
  app.SetTopWindow(adm.mainframe)

  for panelclass in adm.getAllPreferencePanelClasses():
    if hasattr(panelclass, "Init"):
      panelclass.Init()

  adm.mainframe.Show()

  app.MainLoop()
