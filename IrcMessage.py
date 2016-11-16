import re
import logging

logger = logging.getLogger(__name__)

class ParserException(BaseException):
    pass

class IrcMessage:
    prefix = None
    command = None
    params = []

    def __str__(self):
        ret = ""
        if self.prefix is not None:
            ret += ":%s " % self.prefix
        ret += "%s " % self.command
        
        if self.params:
            for arg in self.params[:-1]:
                ret += "%s " % arg

            ret += ":%s" % self.params[-1]

        ret += "\n"

        return ret


    def __init__(self, msg):
        p = re.compile(r"""(?::(
                                ([^@!\ ]*)
                                (?:
                                  (?:
                                    !([^@]*)
                                  )?
                                  @([^\ ]*)
                                )?
                               )\ )?

                               ([^\ ]+)

                               (
                                (?:
                                  \ [^:\ ][^\ ]*
                                ){0,14}
                               )
                               (?:\ :?(.*))?
                           $""", re.VERBOSE)
        res = re.match(p, msg)
        if res is None:
            raise ParserException() 

        self.prefix = res.group(1)
        self.command = res.group(5)
        self.params = res.group(6).split()
        if res.group(7) is not None:
            self.params.append(res.group(7))
