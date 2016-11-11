import inspect

class On:
    def __init__(self, typ):
        self.typ = typ

    def __call__(self, fn):
        fn.callback = self.typ
        return fn

def getOnMapping(obj):
    mapping = {}
    members = inspect.getmembers(obj, predicate=inspect.ismethod)
    for m in members:
        if hasattr(m[1], "callback"):
            fn = m[1]
            fname = m[0]
            mapping[fn.callback] = getattr(obj, fname)
    return mapping
