from xml.etree import ElementTree as ET

def message(**kwargs):
    msg = ET.Element("message")
    msg.set("xmlns", "jabber:component:accept")

    for k, v in kwargs.items():
        if k == 'mfrom':
            msg.set("from", v)
        elif k == 'mto':
            msg.set('to', v)
        elif k == 'mtype':
            msg.set("type", v)
        elif k == 'body':
            body = ET.Element("body")
            body.text = v
            msg.append(body)
        else:
            msg.set(k, v)

    return msg


def presence(**kwargs):
    msg = ET.Element("presence")
    msg.set("xmlns", "jabber:component:accept")
    for k, v in kwargs.items():
        if k == 'pfrom':
            msg.set("from", v)
        elif k == 'pto':
            msg.set('to', v)
        elif k == 'ptype':
            msg.set("type", v)
        else:
            msg.set(k, v)

    return msg

def iq(**kwargs):
    msg = ET.Element("iq")
    msg.set("xmlns", "jabber:component:accept")
    for k, v in kwargs.items():
        if k == 'ifrom':
            msg.set("from", v)
        elif k == 'ito':
            msg.set('to', v)
        elif k == 'itype':
            msg.set("type", v)
        else:
            msg.set(k, v)

    return msg
