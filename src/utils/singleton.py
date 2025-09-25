class Singleton:
    """
    Base class to implement singleton pattern.

    Any class that inherits from this will be a singleton - only one instance
    will be created and reused across the application.
    """

    _instances = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__new__(cls)
        return cls._instances[cls]

    def __init__(self, *args, **kwargs):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        super().__init__()
