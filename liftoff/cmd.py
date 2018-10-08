def launch():
    from liftoff.liftoff import main as _launch
    _launch()


def evolve():
    from liftoff.liftoff import evolve as _evolve
    _evolve()


def prepare():
    from liftoff.prepare import main as _prepare
    _prepare()


def status():
    from liftoff.liftoff_utils import status as _status
    _status()


def abort():
    from liftoff.liftoff_utils import abort as _abort
    _abort()


def elite():
    from liftoff.elite import elite as _elite
    _elite()


def please_do():
    from liftoff.the_client import main as _do
    _do()


def errors():
    from liftoff.errors import main as _errors
    _errors()


def manual_add():
    from liftoff.elite import manual_add as _manual_add
    _manual_add()
