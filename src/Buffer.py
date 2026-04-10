class Buffer:
    def __init__(self):
        self.listeners = []
            
    def connect(self, listener):
        self.listeners.append(listener)
    
    def putToListen(self, listener):
        for l in self.listeners:
            if l == listener:
                l.listen()




    
