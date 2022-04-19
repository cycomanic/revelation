"""Revelation configuration handler"""

from pathlib import Path
from types import ModuleType
from typing import Optional

from . import default_config


class Config(dict):
    """
    Class that stores revelation configs thanks to flask Config:

    https://github.com/pallets/flask/blob/master/flask/config.py

    It loads the default_config variables and if a path is passed it also
    loads the external configs
    """

    def __init__(self, filename: Optional[Path] = None, update: Optional[bool] = True):
        """Initializes the config with the defaults or with custom
        variables from an external file"""
        self.load_from_object(default_config, update=False)

        if filename and filename.is_file():
            self.load_from_pyfile(filename, update)

    def load_from_object(self, obj: ModuleType, update: Optional[bool] = True):
        """Load the configs from a python object passed
        to the function"""
        for key in dir(obj):
            if key.isupper():
                if update and key in self:
                    try:
                        self[key].update(getattr(obj, key))
                    except AttributeError:
                        self[key] = getattr(obj, key)
                else:
                    self[key] = getattr(obj, key)

    def load_from_pyfile(self, filename: Path, update:Optional[bool] = True):
        """Load the configs from a python file as it was imported"""
        module = ModuleType("config")
        module.__file__ = str(filename)

        try:
            with filename.open(mode="rb") as fp:
                exec(compile(fp.read(), filename, "exec"), module.__dict__)
        except IOError as error:
            strerror = error.strerror
            error.strerror = f"Unable to load configuration file ({strerror})"

            raise error

        self.load_from_object(module, update)
