""" Here we define a class that reads liftoff configuration files to provide
    default values for several options.
"""


class LiftoffConfig:
    """ LiftoffConfig works on a single level for now.
    """

    def __init__(self):
        self.cfg = dict({})

    def get(self, name):
        """ Returns the value for the requested option, otherwise returns None.
        """

        return self.cfg.get(name, None)
