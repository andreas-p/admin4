# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# http://initd.org/psycopg/docs/install.html#installation
  
def GetPrerequisites(info=False):
  try:
    import psycopg2
    if psycopg2.__version__ > "2.4":
      return "psycopg2 csv"
    else:
      if info:
        print "psycopg2 too old"
  except:
    if info:
      print "psycopg2 missing"
    pass
  return None

moreFiles=['kwlist.h']