# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


filePatterns=['.png', '.ico', '.xrc', '.py']
ignoredirs=['xrced', 'build', 'dist', '_update']
ignoredfiles=['admin4.py', 'createBundle.py']
moreFiles=["LICENSE.TXT", 'CHANGELOG']

requiredMods=['wx.lib.ogl', 'xml']
appEntry='admin4.py'
packages=['wx']
includes=[]
addModules=[]
excludes=['lib2to3', 'hotshot', 'distutils', 'ctypes', 'unittest']
buildDir=".build"
appName="Admin4"
versionTag=None
requiredAdmVersion="2.1.2"
checkGit=True

if __name__ == '__main__':
  import sys, os
  import platform
  import shutil
  import version
  
  platform=platform.system()
  
  if len(sys.argv) > 1 and sys.argv[1] in ['srcUpdate', 'py2exe', 'py2app']:
    installer=sys.argv[1]
  else:
    if platform == "Windows":
      installer='py2exe'
      distDir="../Admin4-%s-Win"
    else:
      if platform == "Darwin":
        installer='py2app'
        distDir="../Admin4-%s-Mac"
      else:
        print "Platform %s not supported" % platform
        sys.exit(1)
    sys.argv.insert(1, installer)

  if installer == "srcUpdate":
    distDir='../Admin4-%s-Src'

  while '--addModule' in sys.argv:
    i=sys.argv.index('--addModule')
    del sys.argv[i]
    addModules.append(sys.argv[i])
    del sys.argv[i]
  if '--distDir' in sys.argv:
    i=sys.argv.index('--distDir')
    del sys.argv[i]
    distDir=sys.argv[i]
    del sys.argv[i]
  if '--skipGit' in sys.argv:
    i=sys.argv.index('--skipGit')
    del sys.argv[i]
    checkGit=False
    
  def cleanWxDir(dir):
    remainder=0
    for fn in os.listdir(dir):
      path=os.path.join(dir, fn)
      if os.path.isdir(path):
        r=cleanWxDir(path)
        if path.endswith(requiredDirs):
          remainder += 1
        else:
          if not r:
            shutil.rmtree(path)
        remainder += r
      elif path.endswith( ('.pyc', 'pyo')):
        os.unlink(path)
    return remainder
        
  def searchFiles(dir, stripdirlen):
    lst=[]
    filenames=[]
    for fn in os.listdir(dir):
      if fn.startswith('.'):
        continue
      path=os.path.join(dir, fn)
      if os.path.isdir(path):
        lst.extend(searchFiles(path))
      else:
        ext=path[path.rfind('.'):].lower()
        if ext in filePatterns:
          filenames.append(path)
    
    if filenames:
      lst.append( (dir[stripdirlen:], filenames) )
    return lst

  def readVersion():
    version=None
    try:
      f=open('__version.py')
      verSrc=f.read()
      f.close()
      exec verSrc
    except:
      pass
    return version
  

  def writeVersion():
    # https://pythonhosted.org/GitPython/0.3.2/index.html
    # https://pythonhosted.org/GitPython/0.1/index.html
    global versionTag
    
    if checkGit:
      try: 
        import git, time
        if git.__version__ < "0.3":
          print "\nWARNING: GIT too old, must be >0.3\n\n"
          return False
      except:
        print "\nWARNING: No GIT installed\n\n"
        return False
  
      repo=git.Repo(os.path.dirname(os.path.abspath(sys.argv[0])))
      tags={}
      for t in repo.tags:
        tags[str(t.commit)] = t
  
      lastOriginCommit=repo.commit('origin/master')
      lastCommit=repo.commit('master')
      
      def findTag(c):
        if str(c) in tags:
          return tags[str(c)]
        if c.parents:
          for c in c.parents:
            tag=findTag(c)
            if tag:
              return tag
        return None
      tag=findTag(lastCommit)
      if tag:
        versionTag=tag.name
        f=open("__version.py", "w")
        f.write("# Automatically created from GIT by createBundle.\n# Do not edit manually!\n\n")
        f.write("version='%s'\n" % tag.name)
        f.write("requiredAdmVersion='%s'\n" & requiredAdmVersion)
        f.write("tagDate='%s'\n" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tag.commit.committed_date)))
        f.write("revDate='%s'\n" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(lastOriginCommit.committed_date)))
        f.write("modDate='%s'\n" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(lastCommit.committed_date)))
        if repo.is_dirty() or str(lastCommit) != str(lastOriginCommit):
          f.write("revLocalChange=True\n")
        else:
          f.write("revLocalChange=False\n")
        if str(lastOriginCommit) != str(tag.commit):
          f.write("revOriginChange=True\n")
        else:
          f.write("revOriginChange=False\n")
        if repo.is_dirty():
          versionTag="tmp"
          f.write("revDirty=True\n")
        else:
          f.write("revDirty=False\n")
        f.close()
        
        return repo.is_dirty()
      else:
        print "No tags found"
        return True    

    versionTag=readVersion()
    if versionTag != None:
      print "\nWARNING: using existing __version.py file."
      return False
    else:
      print "\nWARNING: No __version file!"
      sys.exit()
    

  # Start of code
  if writeVersion():
    print "\nWARNING: Repository has uncommitted data\n\n"
      
  sys.skipSetupInit=True
  
  data_files=[]
  admResources=[]
  
  if installer == 'srcUpdate':
    ignoredfiles=[]
    
  def checkAddItem(fn, stripdirlen=0):
    if os.path.isdir(fn):
      if os.path.exists("%s/_requires.py" % fn):
        mod=__import__("%s._requires" % fn)
        try:
          requires=getattr(mod, "_requires")
          rq=requires.GetPrerequisites(True)
          if rq:
            if isinstance(rq, str):
              rq=rq.split(' ')
            requiredMods.extend(rq)
            packages.extend(rq)
        except:
          pass
        
      data_files.extend(searchFiles(fn, stripdirlen))
    else:
      if fn.startswith('ctl_') and fn.endswith('.py'):
        admResources.append(fn)
      else:
        ext=fn[fn.rfind('.'):].lower()
        if ext in filePatterns:
          admResources.append(fn)
  
  for fn in os.listdir("."):
    if fn.startswith('.') or fn in ignoredirs or fn in ignoredfiles or os.path.islink(fn):
      continue
    checkAddItem(fn)
  for fn in addModules:
    fn=os.path.abspath(fn)
    checkAddItem(fn, len(os.path.dirname(fn))+1)
    
  admResources.extend(moreFiles)
  data_files.append( (".", admResources) )
  
  data_files.reverse()
  requiredDirs = tuple(d.replace('.', '/') for d in requiredMods)
  packages.extend(requiredMods)
  packages=sorted(set(packages))

  if distDir.find('%s') >=0:
    distDir = distDir % versionTag
  elif versionTag:
    distDir += "-%s" % versionTag
    
  print "Required:", ", ".join(packages)
  
  if installer == 'srcUpdate':
    print "Collecting update into %s" %distDir
    try:
      shutil.rmtree(distDir)
      os.mkdir(distDir)
    except:
      pass
    try:
      os.mkdir(distDir)
    except:
      pass
    for d in data_files:
      if d[0] == '.':
        destDir = distDir
      else:
        destDir=os.path.join(distDir, d[0])
        os.mkdir(destDir)
      for file in d[1]:
        shutil.copy2(file, destDir)
    
  else:
    print "Creating package in %s" %distDir
    import distutils.core
    __import__(installer)
    info=dict( data_files=data_files,
                         name=appName,
                         author=version.author,
                         license=version.copyright,
                         version=version.version,
                         options={'py2exe': {'packages': packages,
                                             'includes': includes,
                                             'excludes': excludes,
                                             'dist_dir': distDir
                                             },
                                            
                                  'py2app': {'argv_emulation': False,
                                             'packages': packages,
                                             'includes': includes,
                                             'iconfile': '%s.icns' % appName,
                                             'dist_dir': distDir,
                                             'plist': { 'CFBundleIdentifier': 'org.%s' % appName.lower() }
                                             },
                                  'build': {'build_base': buildDir},
                                  }
                         )
  
    if platform == "Windows":
      distutils.core.setup(windows=[{'script': appEntry, 'icon_resources': [(1, '%s.ico' % appName)] }], **info)
    elif platform == "Darwin":
      distutils.core.setup(app=[appEntry], **info)
      libdir='%s/%s.app/Contents/Resources/lib/python2.7/wx' % (distDir, appName)
      if not '-A' in sys.argv:
        cleanWxDir(libdir)
        shutil.rmtree('%s/%s.app/Contents/Resources/mpl-data' % (distDir, appName))
  print "done."
