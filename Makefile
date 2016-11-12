
SRC := Component.py IrcMessage.py Jid.py Stanzas.py \
		XMPPComponent.py Irc.py On.py __main__.py

ircd-component: $(SRC)
	zip '$@.tmp' $^
	echo '#!/usr/bin/env python' | cat - '$@.tmp' > $@
	chmod +x $@
	rm '$@.tmp'

.PHONY: clean
clean:
	rm ircd-component


