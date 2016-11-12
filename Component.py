from xml.etree              import ElementTree as ET
import asyncore

from Irc import Ircd
from XMPPComponent import XMPPComponent

import logging

import uuid

from Jid import *
from IrcMessage import *
from Stanzas import *


class Component:
    ircConnectionsByJid = dict()
    ircNicks = set()
    topic = None
    iqCallbacks = dict()

    def __init__(self, config):
        self.config = config

        self.xmpp = XMPPComponent(self, config)

        self.ircd = Ircd(self, config)

    def nicklist(self):
        return " ".join(self.ircNicks)

    def addNick(self, nick):
        if nick not in self.ircNicks:
            self.ircNicks.add(nick)
            for conn in self.ircConnectionsByJid.values():
                conn.write(IrcMessage(":%s!x@x.x JOIN %s" % (nick, self.config["ircd_room"])))

    def removeNick(self, nick):
        if nick in self.ircNicks:
            self.ircNicks.remove(nick)
            for conn in self.ircConnectionsByJid.values():
                conn.write(IrcMessage(":%s!x@x.x PART %s" % (nick, self.config["ircd_room"])))

    def updateNicklist(self, iq):
        for item in iq.iter("{http://jabber.org/protocol/disco#items}item"):
            nick = item.get("name")
            if nick not in self.ircNicks:
                self.addNick(nick)

    def updateTopic(self, iq):
        pass

    def incomingIq(self, uid, iq):
        try:
            self.iqCallbacks[uid](iq)
            del self.iqCallbacks[uid]
        except KeyError:
            pass

    def registerIq(self, uid, fn):
        self.iqCallbacks[uid] = fn

    def associateJid(self, irc, jid):
        self.ircConnectionsByJid[str(jid)] = irc
        self.addNick(jid.name)

    def disassociateIrcConnection(self, irc):
        if not irc.associated:
            return

        jid = "%s@%s" % (irc.nick, self.config["transport_domain"])
        p = presence( pfrom = jid
                    , pto = "%s/%s" % (self.config["muc_room"], irc.nick)
                    , ptype = "unavailable"
                    )

        self.writeToJabber(p)

        if jid.lower() in self.ircConnectionsByJid:
            del self.ircConnectionsByJid[jid.lower()]
        self.removeNick(irc.nick)


    def writeToJabber(self, stanza):
        self.xmpp.write(ET.tostring(stanza))

    def invalidateIrcNick(self, jid):
        try:
            self.ircConnectionsByJid[jid].invalidNick()
        except KeyError:
            pass

    def ircNickInUse(self, nick):
        return nick in self.ircNicks

    def handlePresence(self, msg):
        try:
            conn = self.ircConnectionsByJid[msg.get("to")]
        except KeyError:
            return

        fromJid = Jid(msg.get("from"))
        if fromJid.resource == conn.nick:
            conn.associated = True
            if msg.get("type") != "unavailable":
                conn.sendPreamble()
        else:
            if msg.get("type") == "unavailable":
                self.removeNick(fromJid.resource)
            else:
                self.addNick(fromJid.resource)

    def handleMessage(self, message):
        ircJid = Jid(message.get("to"))
        fromJid = Jid(message.get("from"))

        msg = message.find("{jabber:component:accept}body")

        if message.get("type") == "groupchat":
            subject = message.find("{jabber:component:accept}subject")
            if msg is not None:
                txt = msg.text.encode("UTF-8")
                irc = IrcMessage(":%s!x@x.x PRIVMSG %s :%s" % (fromJid.resource, self.config["ircd_room"], txt))

                conn = self.ircConnectionsByJid[message.get("to")]
                if conn.nick != fromJid.resource:
                    conn.write(irc)

            if subject is not None and subject.text is not None:
                try:
                    self.topic = (fromJid.resource, subject.text.encode("UTF-8"))
                    conn = self.ircConnectionsByJid[message.get("to")]
                    conn.write(IrcMessage(":%s!x@x.x TOPIC %s :%s" % (self.topic[0], self.config["ircd_room"], self.topic[1])))
                except KeyError:
                    pass
                
        elif message.get("type") == "chat":
            if Jid(message.get("from")).bare != self.config["muc_room"]:
                # maybe send some error here
                pass
            else:
                if msg is not None:
                    try:
                        conn = self.ircConnectionsByJid[message.get("to")]
                        irc = IrcMessage(":%s!x@x PRIVMSG %s :%s" % (fromJid.resource, conn.nick, msg.text))
                        conn.write(irc)
                    except KeyError:
                        pass


