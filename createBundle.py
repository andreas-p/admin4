#! /usr/bin/python3
# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License,
# see LICENSE.TXT for conditions of usage


filePatterns=['.png', '.ico', '.xrc', '.py', '.html']
ignoredirs=['xrced', 'build', 'dist', '_update', 'release', 'docker']
ignoredfiles=['createBundle.py']
moreFiles=["LICENSE.TXT", 'CHANGELOG']

requiredMods=['wx.lib.ogl', 'xml']
appEntry='admin4.py'
packages=['wx']
includes=['ast']
addModules=[]
excludes=['lib2to3', 'hotshot', 'distutils', 'ctypes', 'unittest']
buildDir=".build"
releaseDir="release/"
versionTag=None
gitTag=None
requiredAdmVersion="3.0.0" # this is written to __version.py
checkGit=True
checkGitCommits=False
recentlyChanged=[]
createSha=True
repo="adminfour/admin4"

if __name__ == '__main__':
  import sys, os, platform, time
  import shutil, zipfile
  import hashlib
  import version
  import git
  import subprocess

  appName=version.appName
  standardInstallDir="/usr/share/%s" % appName

  platform=platform.system()
  try:  os.mkdir(releaseDir)
  except: pass

  if len(sys.argv) > 1 and sys.argv[1] in ['srcUpdate', 'py2exe', 'py2app', 'docker']:
    installer=sys.argv[1]
    distDir=releaseDir + "admin4"
  else:
    if platform == "Windows":
      installer='py2exe'
      distDir=releaseDir + "Admin4-%s-Win"
    elif platform == "Darwin":
      installer='py2app'
      distDir=releaseDir + "Admin4-%s-Mac"
    elif platform == "Linux":
      installer='zip'
      distDir=releaseDir + "Admin4-%s-Linux"
    else:
      print ("Platform %s not supported" % platform)
      sys.exit(1)
    sys.argv.insert(1, installer)

  if installer == "srcUpdate":
    checkGitCommits=True
    distDir=releaseDir + 'Admin4-%s-Src'

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
    
  def appendChanged(lst, name):
    if not recentlyChanged or name in recentlyChanged:
      lst.append(name)
      
  def cleanWxDir(wxdir):
    remainder=0
    for fn in os.listdir(wxdir):
      path=os.path.join(wxdir, fn)
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
        
  def searchFiles(searchdir, stripdirlen, addFiles=[]):
    lst=[]
    filenames=addFiles
    for fn in os.listdir(searchdir):
      if fn.startswith('.'):
        continue
      path=os.path.join(searchdir, fn)
      if os.path.isdir(path):
        lst.extend(searchFiles(path, stripdirlen))
      else:
        ext=path[path.rfind('.'):].lower()
        if ext in filePatterns:
          appendChanged(filenames, path)
    
    if filenames:
      lst.append( (searchdir[stripdirlen:], filenames) )
    return lst

  def readVersion():
    version=None
    try:
      with open('__version.py') as f:
        verSrc=f.read()
      exec (verSrc)
    except:
      pass
    return version
  

  def writeVersion():
    # https://pythonhosted.org/GitPython/0.3.2/index.html
    global versionTag, gitTag
    
    if checkGit:
      try: 
        if git.__version__ < "0.3":
          print ("\nWARNING: GIT too old, must be >0.3\n\n")
          return False
      except:
        print ("\nWARNING: No GIT installed\n\n")
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
        gitTag=versionTag=tag.name
        if checkGitCommits:
          for commit in repo.iter_commits("%s..HEAD" % versionTag):
            for change in commit.diff(tag.commit):
              path=change.a_blob.path
              if path not in recentlyChanged:
                recentlyChanged.append(path)
            
        with open("__version.py", "w") as f:
          f.write("# Automatically created from GIT by createBundle.\n# Do not edit manually!\n\n")
          f.write("version='%s'\n" % tag.name)
          f.write("requiredAdmVersion='%s'\n" % requiredAdmVersion)
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
          f.write("standardInstallDir='%s'" % standardInstallDir)
        
        return repo.is_dirty()
      else:
        print ("No tags found")
        return True    

    versionTag=readVersion()
    if versionTag != None:
      print ("\nWARNING: using existing __version.py file.")
      return False
    else:
      print ("\nWARNING: No __version file!")
      sys.exit()
    

  # Start of code
  if writeVersion():
    print ("\nWARNING: Repository has uncommitted data\n\n")
      
  sys.skipSetupInit=True
  
  data_files=[]
  admResources=[]
  
    
  def checkAddItem(fn, stripdirlen=0):
    if os.path.isdir(fn):
      addFiles=[]
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
          if hasattr(requires, 'moreFiles'):
            # requires.morefiles must be a list of filenames located in the module dir; no subdir allowed
            for mf in requires.moreFiles:
              appendChanged(addFiles, os.path.join(fn, mf))
        except:  pass
        
      data_files.extend(searchFiles(fn, stripdirlen, addFiles))
    else:
      if fn.startswith('ctl_') and fn.endswith('.py'):
        appendChanged(admResources, fn)
      else:
        ext=fn[fn.rfind('.'):].lower()
        if ext in filePatterns:
          appendChanged(admResources, fn)
  
  for fn in os.listdir("."):
    if fn.startswith('.') or fn in ignoredirs or fn in ignoredfiles or os.path.islink(fn):
      continue
    checkAddItem(fn)
  for fn in addModules:
    fn=os.path.abspath(fn)
    checkAddItem(fn, len(os.path.dirname(fn))+1)

  for file in moreFiles:
    appendChanged(admResources, file)

  data_files.append( (".", admResources) )

  data_files.reverse()
  requiredDirs = tuple(d.replace('.', '/') for d in requiredMods)
  packages.extend(requiredMods)
  packages=sorted(set(packages))

  if not installer in ['docker']:
    if distDir.find('%s') >=0:
      distDir = distDir % versionTag
    elif versionTag:
      distDir += "-%s" % versionTag

  print ("Requirements detected:", ", ".join(packages))

  if installer == 'srcUpdate' or platform == 'Linux':
    if recentlyChanged:
      distDir = distDir[:-4] + "+%s-Upd" % time.strftime("%y%m%d", time.localtime(time.time()))

    print ("Collecting update into %s" % distDir)
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
    if recentlyChanged:
      shutil.copy2('__version.py', distDir)
    
  else:
    print ("Creating package in %s" %distDir)
    # os.environ['DISTUTILS_DEBUG'] = 'true'
    import distutils.core
    
    info=dict( data_files=data_files,
                         name=appName,
                         author=version.author,
                         license=version.copyright,
                         version=str(version.version),
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
      __import__(installer)
      distutils.core.setup(windows=[{'script': appEntry, 'icon_resources': [(1, '%s.ico' % appName)] }], **info)
    elif platform == "Darwin":
      py2app=__import__(installer)
      if tuple(map(int, py2app.__version__.split('.'))) < (0, 27):
        raise Exception("py2app too old: must be 0.8 or newer")

      # if you're getting "Cannot include subpackages using the 'packages' option" py2app is too old
      distutils.core.setup(app=[appEntry], **info)
      libdir='%s/%s.app/Contents/Resources/lib/python%d.%d/wx' % (distDir, appName, sys.version_info.major, sys.version_info.minor)
      if not '-A' in sys.argv:
        cleanWxDir(libdir)
        # not necessary any more shutil.rmtree('%s/%s.app/Contents/Resources/mpl-data' % (distDir, appName))
 #   elif platform == "Linux":
      
  if installer == 'py2app':
    print ("\nWriting dmg.")
    distribPackage=distDir+".dmg"
    with subprocess.Popen([
          "hdiutil", "create",
          "-format", "UDBZ",
          "-volname", appName,
          "-noanyowners", "-nospotlight",
          "-srcfolder", distDir,
          distribPackage
          ]) as proc:
      proc.communicate()
      if proc.returncode:
        sys.exit(8)
  elif installer == "docker":
    createSha=False
    dockerTag="%s:%s" % (repo, gitTag)
    if gitTag != versionTag:
      dockerTag += "-upd"
    print("\nCreating docker container", dockerTag)
#    sys.exit(8)
    with subprocess.Popen([
          "docker", "build",
          "--file", "docker/Dockerfile",
          "--tag", dockerTag,
          "release"
          ]) as proc:
      proc.communicate()
      if proc.returncode:
        sys.exit(8)
    with subprocess.Popen([
          "docker", "tag",
          dockerTag, "%s:latest" % repo
         ]) as proc:
      proc.communicate()
      if proc.returncode:
        sys.exit(8)
  else:
    def zipwrite(path, stripLen):
      fzip.write(path, path[stripLen:])
      if os.path.isdir(path):
        for f in os.listdir(path):
          if f in ['.', '..']:
            continue
          zipwrite(os.path.join(path, f), stripLen)
  
    print ("\nWriting zip.")
    distribPackage=distDir+".zip"
    fzip=zipfile.ZipFile(distribPackage, 'w', zipfile.ZIP_DEFLATED)
    zipwrite(distDir, len(os.path.dirname(distDir))+1)
    fzip.close()
  if createSha:
    with open(distribPackage, 'rb') as f:
      data=f.read(102400)
      m=hashlib.sha1()
      while data != b"":
        m.update(data)
        data=f.read(102400)

    digest=m.hexdigest()
  
    with open(distDir+".sha1", 'w') as f:
      f.write(digest)

    print ("SHA1 Hash for %s: %s" % (distribPackage, digest))

print ("\ndone.")
