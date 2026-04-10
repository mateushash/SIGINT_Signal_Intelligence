import sys
import os

import threading
import time

# MY MODULES
import Buffer
import Sender
import Listener
import Worker

def commandCentral():
    print("Welcome to the command central")
  #  print("Please select an option:")
  #  print("1. Create a buffer")
  #  print("2. Attach a listener to a buffer")
  #  print("3. Choose a cypher for ")
  #  print("3. Exit")

    buffer1 =  Buffer.Buffer()
    print("Buffer created")

    source =  Sender.Sender()
    print("Source signal Found")

    listener1 =  Listener.Listener() 
    print("Listenning for signals")

    worker1 =  Worker.Worker()
    print("Worker ready to process signals")

    t1 = threading.Thread(target=source.send_message(), daemon=True)
    t2 = threading.Thread(target=listener1.listen, daemon=True)

    t1.start(); t2.start()

    while t1.is_alive() and t2.is_alive():
        time.sleep(0.5)    

if __name__ == '__main__':
    try:
        commandCentral()
    except KeyboardInterrupt:
        print('Interruped')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
