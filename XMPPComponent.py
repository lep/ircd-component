from xml.etree              import ElementTree as ET
from xml.etree.ElementTree  import XMLParser

import asyncore
import hashlib
import socket
import threading
import logging

from Jid import Jid
from On import *

logger = logging.getLogger(__name__)

message_tag = "{jabber:component:accept}message"
iq_tag = "{jabber:component:accept}iq"
presence_tag = "{jabber:component:accept}presence"
handshake_tag = "{jabber:component:accept}handshake"


class XMPPComponent(asyncore.dispatcher_with_send):
    parser = None
    root = None
    current = None
    depth = 0

    config = None

    mapping = dict()
    
    def __init__(self, component, config):
        asyncore.dispatcher_with_send.__init__(self)
        self.config = config
        self.parser = XMLParser(target = self)

        self.mapping = getOnMapping(self)
        self.component = component


        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect( (self.config["xmpp_host"], self.config["xmpp_port"]) )

    ############################
    # Jabber message callbacks #
    ############################
    @On(handshake_tag)
    def streamReady(self, _):
        pass

    @On("stream:error")
    def streamError(self, msg):
        raise Exception(msg)

    @On(presence_tag)
    def handlePresence(self, message):
        # handle nick-conflict
        if message.get('type') == 'error':
            self.component.invalidateIrcNick(message.get("to"))
        else:
            self.component.handlePresence(message)

    @On(iq_tag)
    def handleIq(self, msg):
        uid = msg.get("id")
        self.component.incomingIq(uid, msg)

    @On(message_tag)
    def handleMessage(self, message):
        self.component.handleMessage(message)

        
    ######################
    # Asyncore callbacks #
    ######################

    def handle_connect(self):
        self.write("<?xml version='1.0' encoding='UTF-8'?>")
        self.write("<stream:stream to='%s' "\
                   "xmlns:stream='http://etherx.jabber.org/streams' "\
                   "xmlns='jabber:component:accept'>" % self.config["transport_domain"] )

    def write(self, buf):
        logger.debug("to server: %s" % buf)
        self.send(buf)

    def handle_read(self):
        buf = self.recv(4096)
        logger.debug("from server:  %s" % buf)
        self.parser.feed(buf)
        
    def handle_close(self):
        self.close()
        pass
        
                

    #######################
    # XMLParser callbacks #
    #######################
    
    def start(self, tag, attrib):
        if self.current is None:
            self.current = ET.Element(tag, attrib)
        else:
            tmp = ET.SubElement(self.current, tag, attrib)
            tmp.parent = self.current
            self.current = tmp

        if self.root is None:
            self.root = self.current
        self.depth += 1

        if self.depth == 1:
            pw = self.config["transport_password"]
            handshake = ET.Element("handshake")
            handshake.text = hashlib.sha1(attrib['id'] + pw).hexdigest()
            handshake = ET.tostring(handshake)
            self.write(handshake)

    def end(self, tag):
        if self.depth == 2:
            if tag in self.mapping:
                self.mapping[tag](self.current)
        try:
            self.root.remove(self.current)
        except:
            pass
        self.current = self.current.parent
        self.depth -= 1

    def data(self, data):
        if self.current.text is None:
            self.current.text = data
        else:
            self.current.text += data
