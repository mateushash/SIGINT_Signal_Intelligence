# 🐰 Manual do Criasdecrip (Semanas 1 a 6)

Este projeto foi construído cobrindo **todos os requisitos** pedidos:

✅ **Semana 1 e 2:** Arquitetura centralizada + Fila (RabbitMQ) + Ingestão via Buffer + Persistência crua no SQLite (tabela `pacotes`).  
✅ **Semana 3 e 4:** Processamento isolado (Worker real com RabbitMQ) + Serviço de Score/Modelo para métricas + Salvar resultados no SQLite (tabela `scores`).  
✅ **Semana 5 e 6:** API REST completa + Dashboard profissional + Endpoints mínimos (health, stats, export, etc).

---

## 🟢 1. Como INICIAR tudo (Ligar o sistema)

Para iniciar o RabbitMQ no Docker e todos os serviços Python de uma só vez, abra o terminal e rode:

```bash
# Entre na pasta do projeto pelo terminal e rode:
chmod +x start.sh stop.sh
./start.sh
# depois o comando 
`python3 sending_test.py`
# para enviar mensagem de teste
```

> [!IMPORTANT]
> **Certifique-se de que o Docker Desktop está aberto no seu Mac!** Se o comando falhar, abra o aplicativo do Docker e tente novamente.

**O que isso faz?**
1. Liga o RabbitMQ no Docker (se já não estiver ligado).
2. Sobe o **Buffer**, **Worker** e **Score Service** em segundo plano.
3. Garante que processos antigos foram limpos.

---

## 🛑 2. Como PARAR tudo (Desligar o sistema)

Você pode desligar tudo de uma vez. No terminal, rode:

```bash
# Na pasta do projeto, rode:
./stop.sh
```

---

## 💻 3. Como rodar MANUALMENTE (Modo 4 Terminais)

Se você quiser ver os logs acontecendo em tempo real, não use o `./start.sh`. Siga os passos abaixo:

1. Pare tudo que estiver rodando escondido: `./stop.sh`
2. **Garanta o RabbitMQ ligado:** 
   `docker start rabbitmq || docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management`
3. Abra **4 janelas** de terminal diferentes. Em todas elas, entre na pasta do projeto.
4. **No Terminal 1:** Rode `python3 buffer.py` (API que recebe).
5. **No Terminal 2:** Rode `python3 worker_rabbit.py` (Decodificador).
6. **No Terminal 3:** Rode `python3 score_service.py` (Avaliador).
7. **No Terminal 4:** Quando quiser enviar uma mensagem, rode `python3 sending_test.py`.

Nesse formato, todos os terminais vão piscar mostrando o que estão fazendo por trás das câmeras!

---

## 📱 4. Como ver os resultados e testar

Com o sistema rodando (`./start.sh`):

**1. Enviar uma mensagem de teste:**
```bash
python3 sending_test.py
```

**2. Ver o Dashboard:**
Apenas dê dois cliques (ou abra no Live Server) o arquivo `painel.html` que está na sua pasta.
- Aba **📡 Monitor**: Mostra os pacotes brutos sendo processados em tempo real.
- Aba **📊 Scores**: Mostra o cálculo das métricas de integridade, reconstrução e latência.
- Aba **💬 Mensagens**: Lista todas as mensagens decodificadas + botão de exportar JSON e limpar banco.
- Aba **🔌 API Docs**: Documentação de todos os endpoints REST disponíveis.

**3. Ver na Central via Terminal (Extra):**
```bash
python3 central.py
```
*(Selecione a opção 1 para ler as mensagens que já foram concluídas no banco)*

---

## 🔌 5. Endpoints da API REST (Semana 5 e 6)

Todos os endpoints rodam em `http://localhost:5050`.

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/receber` | Envia mensagem binária para o buffer |
| `POST` | `/retorno` | Worker devolve resultado decodificado |
| `GET` | `/api/health` | Health check + uptime + status do RabbitMQ |
| `GET` | `/api/status` | Últimos 50 pacotes (monitor em tempo real) |
| `GET` | `/api/stats` | Estatísticas agregadas do sistema |
| `GET` | `/api/scores` | Últimos 20 scores calculados |
| `GET` | `/api/mensagens` | Lista mensagens decodificadas (read-only) |
| `GET` | `/api/mensagem/<id>` | Detalhe completo de uma mensagem específica |
| `GET` | `/api/central` | Central lê mensagens (altera status) |
| `GET` | `/api/exportar` | Exporta tudo em JSON (mensagens + scores + stats) |
| `POST` | `/api/limpar` | Limpa o banco de dados inteiro (reset) |

**Exemplos de uso com curl:**
```bash
# Health check
curl http://localhost:5050/api/health

# Ver estatísticas
curl http://localhost:5050/api/stats

# Exportar tudo em JSON
curl http://localhost:5050/api/exportar > backup.json

# Limpar banco
curl -X POST http://localhost:5050/api/limpar
```
