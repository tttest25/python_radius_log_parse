#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, re, paramiko, MySQLdb, time
import traceback
from datetime import datetime


import logging
from logging import config
import traceback,sys

from config import account,dbacc

config.fileConfig('./logging.conf')
log = logging.getLogger('root')

logging.getLogger("paramiko").setLevel(logging.WARNING)

host = account["host"]  #'10.59.2.1'
user = account["user"]  #'root-rad01'
secret = account["secret"]  #'Getiparp'
port = account["port"]  #22

log.info('Start freeradius_realime host:%s user:%s' % (host, user))
log.info(' -> Db host:%s user:%s' % (dbacc["host"], dbacc["db"]))


def dbconnect():
  try:
    return MySQLdb.connect(host=dbacc["host"],user=dbacc["user"], passwd=dbacc["passwd"], db=dbacc["db"])
  except Exception as e:
    logging.error("ERROR dbconnect:->")
    logging.error(e)

try:
  db = dbconnect()
  db.ping(True)
  cur = db.cursor()
except Exception as e:
  logging.error(e)




def mac2ip(mac):
# Get ip from mac
  client = paramiko.SSHClient()
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  client.connect(hostname=host, username=user, password=secret, port=port, look_for_keys=False, allow_agent=False)

  REMAC = "([0-9a-f]{2})-([0-9a-f]{2})-([0-9a-f]{2})-([0-9a-f]{2})-([0-9a-f]{2})-([0-9a-f]{2})"
  smac = re.search(REMAC,mac)
  ciscomac = smac.group(1)+smac.group(2)+"."+smac.group(3)+smac.group(4)+"."+smac.group(5)+smac.group(6)

  #time.sleep(2)

  stdin, stdout, stderr = client.exec_command('show ip arp | i '+ciscomac)
  data = stdout.read()# + stderr.read()
  client.close()
  return data


def dbload(date_time, username, mac, ipaddr, wifi_device):
  global db,cur
  try:
    if(not  db.get_server_info()):
       logging.info(" -> Mysql recconect ")
       db = dbconnect()
       cur = db.cursor()
    wifi_insert = ("INSERT INTO wifi_dict ""(dt, wifi_login, wifi_mac, wifi_ip, wifi_ap)""VALUES (%s, %s, %s, %s, %s)")
    cur.execute (wifi_insert, (date_time, username, mac, ipaddr, wifi_device))
    db.commit()
  except Exception as e:
    logging.error(traceback.format_exc())
    logging.error(e)
    db.rollback()

def main():

  while True:
    currentDT_radius = datetime.now().strftime("%d.%m.%Y")
    currentDT_radius_temp = datetime.strftime(datetime.now(), "%Y.%m.%d %H:%M")
    log.info(' Open file : radiusd-%s.log' % (currentDT_radius))
    with open('/var/log/freeradius/radiusd-'+currentDT_radius+'.log', 'r') as f:
      f.seek(0, 2)
      while True:
        line = f.readline()
        #if not line or not line.endswith('\n'):
    #    line = f.findall(r'Login OK', line)
        if line:
          log.info('read line %s' % line.rstrip("\n\r"))
          matchObj = re.search('Login OK', line)
          if matchObj:
            matchObj = re.search('cli ', line.lstrip())
            if matchObj:
              match = re.split(r' : |\[|\/|>|client | port|cli |;vip|\)', line)
    #          print "Date: "+match[0]  print "User: "+match[2] print "WiFi device: "+match[5]   print "MAC: "+match[7] print line
              cur_date = match[0]
    #          print cur_date
              date_time = datetime.strptime(cur_date, '%a %b %d %H:%M:%S %Y')
    #          print "Date: " + str(date_time) print "Username: "+match[2].replace('@gorodperm.ru', "").replace('GORODPERM\\\\', "").replace('gorodperm\\\\', "")
              username = match[2].replace('@gorodperm.ru', "").replace('GORODPERM\\\\', "").replace('gorodperm\\\\', "")
              wifi_device = match[5]
              mac = match[7].lower()
              IPARPPARSE = "Internet +([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*) +([0-9]) +([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}) +(.*)"
              iparp = re.search(IPARPPARSE,mac2ip(mac))
              try:
                ipaddr = iparp.group(1)
              except Exception as e:
                ipaddr = "unknown"

              log.info(' -> connected date_time:%s username:%s mac:%s ipaddr:%s wifi_device:%s' %  (date_time, username, mac, ipaddr, wifi_device))
              dbload(date_time, username, mac, ipaddr, wifi_device)
        else:
          #log.info(' Line is ended !')
          if currentDT_radius != datetime.now().strftime("%d.%m.%Y") and os.path.exists('/var/log/freeradius/radiusd-%s.log' % (datetime.now().strftime("%d.%m.%Y"))):
          #if currentDT_radius_temp != datetime.strftime(datetime.now(), "%Y.%m.%d %H:%M") and os.path.exists('/var/log/freeradius/radiusd-%s.log' % (datetime.now().strftime("%d.%m.%Y"))):
            log.info(' Rotate file !')
            break
          time.sleep(2)
    log.info(' close file ! ')
    f.close() 
  
  log.info('=== Stop')


if __name__ == '__main__':
  try:
    main()
  except Exception as e:
    db.close()
    logging.error(e)
    logging.error(traceback.format_exc())
    # Logs the error appropriately. 
    #sys.exit(2)    
    #while(True):
    #    follow()
    #    time.sleep(30)
  finally:
    #closing database connection.
    if(db.is_connected()):
        cur.close()
        db.close()
        logging.info('Db is closed')
