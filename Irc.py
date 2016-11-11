import asynchat
from xml.etree              import ElementTree as ET
import asyncore
import socket
import re
import logging
import uuid

from On import *

from Stanzas import *
from IrcMessage import *
from Jid import Jid

logger = logging.getLogger(__name__)


class Ircd(asyncore.dispatcher):
    def __init__(self, component, config):
        asyncore.dispatcher.__init__(self)

        self.component = component
        self.config = config

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("localhost", 6667))
        self.listen(5)

    def handle_accept(self):
        channel, addr = self.accept()
        IrcClient(self.component, channel, self.config)

class IrcClient(asynchat.async_chat):
    nick = None
    jid = None
    associated = False
    channels = set()
    buffer = ""

    def __init__(self, component, sock, config):
        asynchat.async_chat.__init__(self, sock=sock)
        self.component = component
        self.config = config
        self.sock = sock
        self.set_terminator("\n")
        self.mapping = getOnMapping(self)


    def write(self, msg):
        if msg.prefix is None:
            msg.prefix = "xmpp"
        logger.debug("Irc writeing %s" % msg)
        self.push(str(msg))
        #self.push(str(msg))

    def invalidNick(self):
        msg = IrcMessage("433")
        msg.params = ["*", self.nick, "Nickname is already in use"]
        self.write(msg)


    @On("NICK")
    def onNick(self, args):
        try:
            nick = args[0]
        except IndexError:
            return

        if self.associated:
            msg = IrcMessage("433")
            msg.params = [self.nick, nick, "Nickname is already in use"]
            self.write(msg)
            return

        self.nick = nick
        if self.component.ircNickInUse(nick):
            self.invalidNick()
            return

        self.jid = "%s@irc.xmpp.local" % nick
        self.component.associateJid(self, Jid(self.jid))

        p = presence( pfrom = self.jid
                    , pto = "%s@muc.xmpp.local/%s" % (self.config["ircd_room"], self.nick)
                    )
        x = ET.SubElement(p, "x")
        x.set("xmlns", "http://jabber.org/protocol/muc")
        self.component.writeToJabber(p)

        ## get user list
        uid = str(uuid.uuid4())
        self.component.registerIq(uid, self.component.updateNicklist)
        i = iq( ifrom = self.jid
              , ito = self.config["muc_room"]
              , type = "get"
              , id = uid
              )
        q = ET.SubElement(i, "query")
        q.set("xmlns", "http://jabber.org/protocol/disco#items")
        self.component.writeToJabber(i)


    def sendPreamble(self):
        self.write(IrcMessage(":xmpp 001 %s :Hello %s" % (self.nick, self.nick)))
        self.write(IrcMessage(":xmpp 002 %s :Your host is xmpp" % self.nick))
        self.write(IrcMessage(":xmpp 003 %s :This server was created just for you" % self.nick))
        self.write(IrcMessage(":xmpp 004 %s" % self.nick))

        self.write(IrcMessage(":%s!x@x.x NICK %s" % (self.nick, self.nick)))

        self.write(IrcMessage(":xmpp 375 %s :- xmpp Message of the day -" % self.nick))
        self.write(IrcMessage(":xmpp 372 %s :- Hi" % self.nick))
        self.write(IrcMessage(":xmpp 376 %s :End of MOTD command" % self.nick))

        self.write(IrcMessage(":xmpp PING bla"))
        self.joinChannel()

    def joinChannel(self):
        self.write(IrcMessage(":%s!x@x.x JOIN %s" % (self.nick, self.config["ircd_room"])))
        if self.component.topic is not None:
            self.write(IrcMessage(":xmpp 332 %s %s :%s" % (self.component.topic[0], self.config["ircd_room"], self.component.topic[1])))
        self.write(IrcMessage(":xmpp 353 %s = %s :%s" % (self.nick, self.config["ircd_room"], self.component.nicklist())))
        self.write(IrcMessage(":xmpp 366 %s %s :End of /NAMES list." % (self.nick, self.config["ircd_room"]))) 
        self.write(IrcMessage(":xmpp 324 %s %s +t" % (self.config["ircd_room"], self.nick))) 



    @On("USER")
    def onUser(self, args):
        pass

    @On("PONG")
    def onPong(self, args):
        pass

    @On("TOPIC")
    def onTopic(self, args):
        try:
            chan = args[0]
            topic = args[1]
        except IndexError:
            return

        if chan != self.config["ircd_room"]:
            return

        m = message( mfrom = self.jid
                   , mto = self.config["muc_room"]
                   , mtype = "groupchat"
                   )
        s = ET.SubElement(m, "subject")
        s.text = topic
        self.component.writeToJabber(m)


    @On("QUIT")
    def onQuit(self, args):
        self.component.disassociateIrcConnection(self)
        self.close()


    @On("PART")
    def onPart(self, args):
        self.component.disassociateIrcConnection(self)


    @On("JOIN")
    def onJoin(self, args):
        try:
            if args[0] != self.config["ircd_room"]:
                self.write(IrcMessage("403 %s %s :No such Channel" % (self.nick, args[0])))
        except IndexError:
            pass

    @On("PRIVMSG")
    def onMsg(self, args):
        try:
            chan = args[0]
            msg = args[1]
        except IndexError:
            return

        if chan == self.config["ircd_room"]:
            m = message( mfrom = self.jid
                       , mto = self.config["muc_room"]
                       , mtype = "groupchat"
                       , body = msg
                       )
            self.component.writeToJabber(m)
        elif chan[0] == "#" or chan[0] == "&":
            self.write(IrcMessage("403 %s %s :No such Channel" % (self.nick, chan)))
        else:
            m = message( mfrom = self.jid
                       , mto = "%s/%s" % (self.config["muc_room"], chan)
                       , mtype = "chat"
                       , body = msg
                       )
            self.component.writeToJabber(m)


    @On("PING")
    def onPing(self, args):
        msg = IrcMessage("PONG")
        msg.params = args
        self.write(msg)



    ### ASYNCORE STUFF

    def collect_incoming_data(self, data):
        self.buffer += data

    def found_terminator(self):
        self.onIrcMessage(self.buffer)
        self.buffer = ""

    def handle_close(self):
        logger.debug("Connection closed")
        self.component.disassociateIrcConnection(self)
        self.close()


    def onIrcMessage(self, msg):
        msg = msg.decode("UTF-8")
        logger.debug("Got irc message %s" % msg)
        try:
            p = IrcMessage(msg)
        except ParserException:
            logger.debug("Couldnt parse irc message")
            return

        if p.command in self.mapping:
            self.mapping[p.command](p.params)
        else:
            nick = self.nick or "*"
            self.write(IrcMessage(":xmpp 421 %s %s :Unknown command\r\n" % (nick, p.command)))

