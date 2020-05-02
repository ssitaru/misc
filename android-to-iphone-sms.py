#!/usr/bin/python3
#
#        Android SMS to iPhone DB importer
#
# 2016 by Sebastian Sitaru, CC-BY-SA
# 

import sys
from xml.dom.minidom import parse
import sqlite3
import re
import pprint

""" settings """
isDebug = 0
writeToDB = 1


def printIfDebug(string):
        if(isDebug == 1):
                print(string)

def sqliteRead(flags):
        return (int(flags) & 0x02) >> 1;

def convertTime(oldTime):
        """ the Android SMS backup tool uses milliseconds (!), not normal seconds since the epoch """
        return int(int(oldTime) / 1000);

if(len(sys.argv) < 3):
        print("Usage: ",sys.argv[0], " <android XML>  <iPhone DB>")
        sys.exit(1)


fileH = open(sys.argv[1])
print("Parsing XML, wait....", end='')
sys.stdout.flush()
xmlDOM = parse(fileH)
print("done.\n")

print("Reading XML tree...", end='')
sys.stdout.flush()
mySMS = []
for sms in xmlDOM.getElementsByTagName("sms"):
        mySMS.append(sms)
print("OK,",len(mySMS),"SMS\n")

print("Building groups...", end='')
sys.stdout.flush()
myGroups = {}
for sms in xmlDOM.getElementsByTagName("sms"):
        """ what we do here is we go through the SMS entries and add unique keys to myGroups """
        #smsSvcCenter = sms.getAttribute("service_center")
        smsAddress = sms.getAttribute("address")
        """ convert smsAddress to intl format +49... """
        if(re.match(r"0([1-9][0-9]*)$", smsAddress) != None):
                printIfDebug("Address is in format 0176: "+smsAddress)
                smsAddress = "+49"+re.match(r"0([1-9][0-9]*)$", smsAddress).group(1)
        elif(re.match(r"00([0-9]*)", smsAddress) != None):
                printIfDebug("Address is in format 0049: "+smsAddress)
                smsAddress = "+"+re.match(r"00([0-9]*)$", smsAddress).group(1)
        elif(re.match(r"[1-9][0-9]*", smsAddress) != None):
                printIfDebug("Address is special address without prefix: "+smsAddress)
        else:
                printIfDebug("Address is in good format or string: "+smsAddress)
        printIfDebug("\tNew address "+smsAddress)
        """ try to add the current SMS to the group (number) to which it belongs """
        try:
                myGroups[smsAddress]["elements"].append(sms)
        except KeyError:
                """ if group doesnt exist, create it & add the SMS to it """
                myGroups[smsAddress] = {"id":None, "elements":[sms]}

print("OK,",len(myGroups),"groups\n")

print("Opening iPhone DB...", end='')
iPhoneDB = sqlite3.connect(sys.argv[2])
dbCursor = iPhoneDB.cursor()
iPhoneDB.create_function("read", 1, sqliteRead)
print("OK\n")

""" get latest groupID """
dbCursor.execute("SELECT * FROM group_member")
takenGroupIDs = []
for row in dbCursor:
        takenGroupIDs.append(row[1])
takenGroupIDs.sort()
takenGroupIDs.reverse()
printIfDebug("Last taken GID in iPhone DB: "+str(takenGroupIDs[0]))
lastGID = takenGroupIDs[0]

print("Importing SMS into iPhone DB...", end='')
for i in range(0, len(myGroups)):
        lastGID += 1
        group = myGroups.popitem()
        printIfDebug("Group "+str(group[0]))
        printIfDebug("Entries "+str(len(group[1]['elements'])))
        dbCursor.execute("INSERT INTO group_member (group_id, address, country) VALUES ("+str(lastGID)+", \""+group[0]+"\", \"de\")")
        dbCursor.execute("INSERT INTO msg_group (ROWID) VALUES ("+str(lastGID)+")")
        printIfDebug("Inserted new group with GID "+str(lastGID))
        for sms in group[1]['elements']:
                escapedBody = sms.getAttribute("body").replace("'", "''")
                """
                        type/flag list for the iPhone/Android SMS DB:
                        iPhone           | Android
                        t = 2: recieved  | recieved: t = 1
                        t = 3: sent      | sent: t = 2
                        t = 33: error    | error: t = 32
                        t = 129: deleted |   [info n/a]
                """
                origType = int(sms.getAttribute("type"))
                iPhoneType = (origType+1) if ((origType == 1) or (origType == 2)) else 33
                printIfDebug("Query INSERT INTO message (address, date, text, flags, group_id, country, read, svc_center) VALUES (\"{0}\", {1}, '{2}', {3}, {4!s}, 'de', 1, \"{5!s}\")".format(group[0],
                                                                                                        convertTime(sms.getAttribute("date")),
                                                                                                        escapedBody,
                                                                                                        iPhoneType,
                                                                                                        lastGID,
                                                                                                        sms.getAttribute("service_center")))
                dbCursor.execute("INSERT INTO message (address, date, text, flags, group_id, country, read, svc_center) VALUES (\"{0}\", {1}, '{2}', {3}, {4!s}, 'de', 1, \"{5!s}\")".format(group[0],
                                                                                                        convertTime(sms.getAttribute("date")),
                                                                                                        escapedBody,
                                                                                                        iPhoneType,
                                                                                                        lastGID,
                                                                                                        sms.getAttribute("service_center")))

                #print "\tItem with type",sms.getAttribute("type"),"and body [",sms.getAttribute("body"),"]"
print("OK.\n")

print("Closing iPhone Database....", end='')
if(writeToDB == 1):
        iPhoneDB.commit()
        dbCursor.close()
else:
        print("[writeToDB is off] ", end='')
print("done.")
