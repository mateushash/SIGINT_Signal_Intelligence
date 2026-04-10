import pika 
import os 
import sys

class Sender:
    def __init__(self):
        pass

    def send_message(self):
        
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost')) 
        channel = connection.channel()
        
        channel.queue_declare(queue='hello', durable=True, arguments={'x-queue-type': 'quorum'})


        message = input("Type your message(CTRL-C to exit): \n")

        try:
            while not message:
                channel.basic_publish(exchange='', 
                              routing_key='hello',
                              body=message)
                print(f" [X] Sent '{message}'\n") 
        except KeyboardInterrupt:
            connection.close()
            print('Interruped, Connection closed.')
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)
