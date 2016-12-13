from xml.etree              import ElementTree as ET
import asyncore

from Irc import Ircd
from XMPPComponent import XMPPComponent

import logging

import uuid

from Jid import *
from IrcMessage import *
from Stanzas import *

logger = logging.getLogger(__name__)


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

    def incomingIq(self, uid, iqstanza):
        try:
            self.iqCallbacks[uid](iqstanza)
            del self.iqCallbacks[uid]
        except KeyError:
            uid = iqstanza.get("id")
            i = iq( ifrom = iqstanza.get("to")
                  , ito   = iqstanza.get("from")
                  , id = uid
                  , itype = "error")
            error = ET.SubElement(i, "error")
            error.set("type", "cancel")
            inner_error = ET.SubElement(error, "feature-not-implemented")
            inner_error.set("xmlns", "urn:ietf:params:xml:ns:xmpp-stanzas")

            self.writeToJabber(i)


    def registerIq(self, uid, fn):
        self.iqCallbacks[uid] = fn

    def associateJid(self, irc, jid):
        self.ircConnectionsByJid[str(jid)] = irc
        self.addNick(jid.name)
        i = iq( itype="set"
              , ifrom=self.config["transport_domain"]
              , ito=self.config["muc_room"]
              , id=str(uuid.uuid4())
              )

        query = ET.SubElement(i, "query")
        query.set("xmlns", "http://jabber.org/protocol/muc#admin")

        item = ET.SubElement(query, "item")
        item.set("affiliation", "member")
        item.set("jid", "%s@%s" % (irc.nick, self.config["transport_domain"]))

        self.writeToJabber(i)
    def disassociateIrcConnection(self, irc):
        if not irc.associated:
            return

        jid = "%s@%s" % (irc.nick, self.config["transport_domain"])
        p = presence( pfrom = jid
                    , pto = "%s/%s" % (self.config["muc_room"], irc.nick)
                    , ptype = "unavailable"
                    )

        i = iq( ifrom = self.config["transport_domain"]
              , ito = self.config["muc_room"]
              , itype = "set"
              , id = str(uuid.uuid4())
              )
        
        x = ET.SubElement(i, "query")
        x.set("xmlns", "http://jabber.org/protocol/muc#admin")
        item = ET.SubElement(x, "item")
        item.set("affiliation", "none")
        item.set("jid", "%s@%s" % (irc.nick, self.config["transport_domain"]))

        self.writeToJabber(i)
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

    def handleMe(self, msg):
        act = "/me "
        if msg.startswith(act):
            return "\x01ACTION " + msg[len(act):] + "\x01"
        else:
            return msg

    def handleMessage(self, message):
        ircJid = Jid(message.get("to"))
        fromJid = Jid(message.get("from"))

        msg = message.find("{jabber:component:accept}body")

        if message.get("type") == "groupchat":
            subject = message.find("{jabber:component:accept}subject")
            if msg is not None:
                txt = self.handleMe(msg.text.encode("UTF-8"))
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
                        txt = self.handleMe(msg.text.encode("UTF-8"))
                        irc =":%s!x@x PRIVMSG %s :%s" % (fromJid.resource, conn.nick, txt)
                        irc = IrcMessage(irc)
                        conn.write(irc)
                    except KeyError:
                        pass


