# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# Mac OSX 10.8, 10.9:
# xcode-select --install
# sudo easy_install pip
# sudo pip install dnspython
# sudo pip install requests
#
# Debian:
# apt-get install python-dnspython python-requests
#
# Windows:
# http://www.dnspython.org
# http://www.python-requests.org
 

def GetPrerequisites(info=False):
  try:
    import dns.version
    if dns.version.version < "2.0.":
      if info:
        print ("dnspython too old")
      return None
    return "dns requests"
  except:
    if info:
      print ("dnspython missing")
    pass
  return None
