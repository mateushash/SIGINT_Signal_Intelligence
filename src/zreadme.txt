com o docker e o RabbitMQ ja istalados e rodando, tendo disponibilidade de acessar o http://localhost:15672/#/

comece rodando o buffer.py, e o worker.py em terminais separados

em outro terminal rode o sending_test.py, assim ele realizara o envio para o buffer e o processo começara,

assim que estiver terminado os processos no terminal, ative em outro o central.py e ensira o comando 1 para receber as mensagems.

cheque o Banco de dados para ver os registros com SQlite