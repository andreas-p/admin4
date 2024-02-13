# The Admin4 Project
# (c) 2013-2024 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# http://www.dnspython.org/docs
# http://www.dnspython.org/examples.html

try:
  import dns.query, dns.update, dns.message, dns.resolver, dns.tokenizer
  import dns.zone, dns.reversename, dns.tsig
  from dns.name import Name
  import dns.ipv4, dns.ipv6
  import dns.rdata, dns.rdataset
  # These imports are needed; silence PyDev
  import dns.rdatatype as rdatatype  # @UnusedImport
  import dns.rdataclass as rdataclass # @UnusedImport
  import dns.rcode as rcode # @UnusedImport
  if dns.__version__ < '2.3':
    raise Exception("dnspython too old; minimum 2.3")
except:
  dns=None
  print("python3-pythondns (dnspython) not present")

import requests
import xml.etree.cElementTree as xmltree
import logger


# https://en.wikipedia.org/wiki/List_of_DNS_record_types
# https://www.ionos.de/digitalguide/hosting/hosting-technik/dns-records/
dnsKnownTypes= {
  'A':           "IPV4 Address",
  'AAAA':        "IPV6 Address",
  'AFSDB':       "AFS Database",
  'AMTRELAY':    "Automatic Multicast Tunneling Relay",
  'APL':         "Address Prefix List",
  'AVC':         "Application Visibility and Control",
  "CAA":         "CA Authorization",
  'CDNSKEY':     "Child DS Key",
  'CDS':         "Child DS",
  'CERT':        "Certificate",
  'CNAME':       "Canonical Name",
  'CSYNC':       "Child-To-Parent Synchronization",
  'DHCID':       "DHCP Identifier",
  'DLV':         "DNSSEC Lookaside Validation Record",
  'DNAME':       "Delegation Name",
  'DNSKEY':      "DNS Key",
  'DS':          "Delegation Signer",
  'EUI48':       "MAC Address EUI-48",
  'EUI64':       "MAC Address EUI-64",
  'GPOS':        "Geographical Position", # outdated
  'HINFO':       "Host Information", # obsolete
  'HIP':         "Host Identifier Protocol",
  'HTTPS':       "HTTPS Binding",
  'IPSECKEY':    "IPSEC Key",
  'ISDN':        "ISDN Address", # outdated, never used 
  'KEY':         "DNSSEC Key",   # obsolete
  'KX':          "Key Exchange",
  'LOC':         "Location",
  'MX':          "Mail Exchange", 
  'NAPTR':       "Naming Authority Pointer",
  'NS':          "Name Server", 
  'NSEC':        "Next Secure Record",
  'NSEC3':       "Next Secure Record V3",
  'NSEC3PARAM':  "NSEC3 Parameters",
  'OPENPGPKEY':  "OpenPGP Public Key Record",
  'PTR':         "Domain Name Pointer",
  'RRSIG':       "DNSSEC Signature",
  'RP':          "Responsible Person",
  'SIG':         "DNSSEC Signature", # obsolete
  'SMIMEA':      "S/MIME Cert Association",
  'SOA':         "Start Of Authority",
  'SPF':         "Sender Policy Framework", # outdated
  'SRV':         "Service Locator",         
  'SSHFP':       "SSH Public Key Fingerprint",
  'SVCB':        "Service Binding",
  'TA':          "Trust Authority",
  'TKEY':        "Secret Key Record",
  'TLSA':        "TLSA Certificate Association",
  'TSIG':        "Transaction Signature",
  'TXT':         "Text Record",
  'URI':         "Uniform Resource Identifier",
  'WKS':         "Well known service description",
  'X25':         "X25 Address", # outdated, never used
  'ZONEMD':      "Message Digests for DNS Zones"
  }
dnsObsoleteTypes= [
  'MD', 'MF', 'MAILA', # RFC883
  'MB', 'MG', 'MR', 'MINFO', 'MAILB', # RFC883
  'NULL', # RFC883
  'NID', 'L32', 'L64','LP', # RFC6742
  'RT', # RFC1183
  'NSAP', 'NSAP_PTR', # RFC1706
  'PX', # RFC2163
  'NXT',
  'A6', # RFC2874
  'NINFO',
  'UNSPEC',
  'AVC', 'AMTRELAY'
]
dnsPseudoTypes= [
  'AXFR', 'IXFR', 'OPT', 'ANY'
  ]

DnsSupportedAlgorithms={}
DnsSupportedTypes={}

if dns:
  for n in dns.tsig.__dict__.keys(): # @noqa
    v=getattr(dns.tsig, n)
    if isinstance(v, Name) and (n.startswith("HMAC") or n.find('TSIG') > 0):
      DnsSupportedAlgorithms[n]=n
  for n in rdatatype.__dict__.keys(): # @noqa
    v=getattr(rdatatype, n)
    if isinstance(v, int) and v and n not in dnsObsoleteTypes + dnsPseudoTypes:
      info=dnsKnownTypes.get(n)
      if not info:
        info=n
  #      print(n)
      DnsSupportedTypes[n]=info
      
def DnsName(*args):
  lst=[]
  for arg in args:
    if isinstance(arg, list):
      lst.extend(arg)
    elif arg == ".":
      lst.append("")
    else:
      lst.extend(arg.split('.'))
      
  return Name(lst)

def DnsAbsName(*args):
  lst=[]
  for arg in args:
    if isinstance(arg, list):
      lst.extend(arg)
    else:
      lst.extend(arg.split('.'))
      
  if lst[-1]:
    lst.append("") # make it an absolute name
  
  return Name(lst)

def RdataClass(rdClass, rdType):
  return dns.rdata.get_rdata_class(rdClass, rdType)  # @UndefinedVariable

def Rdata(dset, *args):
  cls=RdataClass(dset.rdclass, dset.rdtype)
  return cls(dset.rdclass, dset.rdtype, *args)

def RdataEmpty(dset):
  cls=RdataClass(dset.rdclass, dset.rdtype)
  zero=[]
  for _slot in cls.__slots__:
    zero.append("0")
  return cls.from_text(dset.rdclass, dset.rdtype, dns.tokenizer.Tokenizer(" ".join(zero)))
  
def Rdataset(ttl, rdclass, rdtype, *args):
  rds=dns.rdataset.Rdataset(rdclass, rdtype)
  if args:
    rds.add(Rdata(rds, *args), ttl)
  else:
    rds.add(RdataEmpty(rds), ttl)
  return rds

def DnsRevName(address):
  return dns.reversename.from_address(address)

def DnsRevAddress(name):
  return dns.reversename.to_address(name)

def checkIpAddress(address):
  try:
    dns.ipv4.inet_aton(address)
    return 4
  except:
    try:
      dns.ipv6.inet_aton(address)
      return 6
    except:
      pass
  return None



class BindConnection():

  def __init__(self, server):
    self.server=server
    self.hasFailed=False
    self.queryProc=dns.query.tcp # or udp

  def HasFailed(self):
    return self.hasFailed
  
  
  def execute(self, name, rdtype, rdclass):  
    if not isinstance(name, Name):
      name=DnsName(name)
    request=dns.message.make_query(name, rdtype, rdclass)
    tsig=self.GetTsig()
    if tsig:
      request.use_tsig(tsig)

    response=self.queryProc(request, self.server.address, timeout=self.server.settings.get('timeout', 1.), port=self.server.settings['port'])
    if response:
      answer=dns.resolver.Answer(name, rdtype, rdclass, response)
      return answer.rrset
    return []

  def Updater(self, zonename):
    return dns.update.Update(zonename, keyring=self.GetTsig())
  
  def GetVersion(self):
    rdtype=dns.rdatatype.TXT
    rdclass=dns.rdataclass.CH
    try:
      name=Name("version.bind.".split('.'))
#      rrset=self.execute(DnsAbsName("version.bind"), rdtype, rdclass)
      rrset=self.execute(name, rdtype, rdclass)
      return b" ".join(rrset[0].strings).decode()
    except dns.resolver.NoAnswer:
      return ""
    except Exception as e:
      print(e)
      logger.exception("Error getting Bind version")
      return None
    return ""

  def Query(self, name, rdtype=dns.rdatatype.A, rdclass=dns.rdataclass.IN):
    try:
      rrset=self.execute(name, rdtype, rdclass)
      return rrset
    except:
      logger.exception("Error querying %s", str(name))
      return None
    return []

  def GetTsig(self):
    if self.server.password and self.server.settings['keyname']:
      name=self.server.settings['keyname']
      name=dns.name.from_text(name)
      algtext=self.server.settings.get('algorithm', "HMAC_MD5") # backward compatibility
      alg=getattr(dns.tsig, algtext)
      tsig=dns.tsig.Key(name, self.server.password, alg)
      return tsig;
    else:
      return None

  def ReadStatistics(self):
    if not self.server.settings.get('statsport'):
      return None
    try:
      response=requests.get("http://%s:%d" % (self.server.address, self.server.settings['statsport']), timeout=self.server.settings.get('timeout', 1.))
      response.raise_for_status()
      txt=response.text
    except Exception as _e:
      return None

    try:
      root=xmltree.fromstring(txt)
    except Exception as _e:
      import adm, time
      fname="%s/xml-%s_%s.xml" % (adm.loaddir, self.server.address, time.strftime("%Y%m%d%H%M%S", time.localtime(time.time())))
      logger.exception("Error parsing BIND response %s", fname)
      f=open(fname, "w")
      f.write(txt)
      f.close() 
      return None
    return root
  
  def Send(self, updater):
    return self.queryProc(updater, self.server.address, timeout=self.server.settings.get('timeout', 1.), port=self.server.settings['port'])

  def GetZone(self, zone):
    xfr = dns.query.xfr(self.server.address, zone, timeout=self.server.settings.get('timeout', 1.)*10., port=self.server.settings['port'], keyring=self.GetTsig())
    zoneObj = dns.zone.from_xfr(xfr)
    return zoneObj

