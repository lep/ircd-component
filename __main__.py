import argparse
import asyncore
import logging

from Component import Component

parser = argparse.ArgumentParser(description="Ircd-component for xmpp servers")
parser.add_argument( "--xmpp-host", default="localhost"
                   , dest="xmpp_host"
                   , help="The xmpp-server to connect to" )
parser.add_argument( "--xmpp-port", default=5347, type=int
                   , dest="xmpp_port"
                   , help="The port of the xmpp-server" )
parser.add_argument( "--transport-domain", required=True
                   , dest="transport_domain"
                   , help="The domain this component will serve under" )
parser.add_argument( "--transport-password", required=True
                   , dest="transport_password"
                   , help="Password used to auth against the xmpp-server" )
parser.add_argument( "--ircd-room", required=True
                   , dest="ircd_room"
                   , help="The room to relay to the muc" )
parser.add_argument( "--muc-room", required=True
                   , dest="muc_room"
                   , help="The muc-room" )
parser.add_argument( "--debug", default=False, action='store_true'
				   , help="Print a lot of debug-messages" )

config = parser.parse_args()

logger = logging.getLogger()
fmt = logging.StreamHandler()
fmt.setFormatter(logging.Formatter(fmt='%(name)s: %(message)s'))
logger.addHandler(fmt)
if config.debug:
	logger.setLevel(logging.DEBUG)

Component(vars(config))
asyncore.loop()


