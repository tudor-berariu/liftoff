
def launch():
    from liftoff.liftoff import main as _launch
    _launch()


def generate():
    from liftoff.prepare import main as _prepare
    _prepare()
