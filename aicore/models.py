class AuthenticationError(Exception):
    def __init__(self, provider :str, message :str, status_code :int=401):        
        self.provider = provider
        self.message = message
        self.status_code = status_code

    def __str__(self)->str:
        return str(self.__dict__)