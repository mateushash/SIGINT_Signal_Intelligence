import sys
import time
import requests

BUFFER_API_URL = "http://localhost:5000/api/central"

#Processo de busca por mensagens que foram completadas apos terem todos os pacotes daquele id sido processados.
def puxar_dados_do_banco():
    print("\n[Central] Checando o banco de dados por novas mensagens...")
    try:
        response = requests.get(BUFFER_API_URL)
        if response.status_code == 200:
            dados = response.json()
            mensagens = dados.get("mensagens_decodificadas", [])
            
            if not mensagens:
                print("-> Nenhuma mensagem completa pronta no banco no momento.")
            else:
                for m in mensagens:
                    print("=" * 60)
                    print(f"MESSAGE ID: {m['message_id']}")
                    print("-" * 60)
                    print(f"TEXTO DECODIFICADO:\n{m['texto']}")
                    print("=" * 60)
                    print("-> Registros atualizados no banco para: 'lido_central'")
        else:
            print(f"[Erro] Buffer retornou status: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("[Erro crítico] Não foi possível conectar ao Buffer. Ele está rodando?")

#Iteracao pelo terminal
def commandCentral():
    print("=========================================")
    print("        CENTRAL DE COMANDO ATIVA         ")
    print("=========================================")
    
    while True:
        print("\nOpções:")
        print("1. Solicitar mensagens decodificadas")
        print("2. Sair")
        
        escolha = input("Selecione um comando: ")
        
        if escolha == '1':
            puxar_dados_do_banco()
        elif escolha == '2':
            print("Encerrando a Central...")
            break
        else:
            print("Comando inválido.")

if __name__ == '__main__':
    try:
        commandCentral()
    except KeyboardInterrupt:
        print('\n[Interrompido pelo usuário]')
        sys.exit(0)