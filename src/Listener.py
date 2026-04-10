import pika 

class Listener:
    def __init__(self):
        pass

    def callback(self, ch, method, properties, body):
        print(f" [x] Received {body}")
    
    def listen(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost')) 
        channel = connection.channel()
        
        channel.queue_declare(queue='hello', durable=True, arguments={'x-queue-type': 'quorum'})
        
        channel.basic_consume(queue = 'hello',
                              auto_ack = True, 
                              on_message_callback=self.callback)
        print(" [*] Waiting for messages. To exit press CTRL-C")
        channel.start_consuming()
