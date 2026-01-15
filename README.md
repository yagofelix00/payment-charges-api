# 💳 Payment Platform — PIX Webhooks

Plataforma de pagamentos desenvolvida para **simular um fluxo real de cobranças e confirmações via PIX**, utilizando **webhooks assinados**, **Redis como fonte de verdade**, **idempotência**, **rate limit** e um **Fake Bank Service** para integração completa.

O projeto tem foco educacional e de portfólio, demonstrando **como sistemas de pagamento funcionam em produção**, indo além de CRUDs simples.

---

## 🚀 Visão Geral

- Tipo: **API REST**
- Domínio: **Pagamentos / PIX / Webhooks**
- Objetivo principal: Criar cobranças e confirmar pagamentos **exclusivamente via webhook**
- Cenário de uso: Plataformas que dependem de confirmação assíncrona (e-commerce, SaaS, marketplaces)

---

## 🧠 Arquitetura & Conceitos

### Arquitetura

- Arquitetura REST
- Separação clara por **camadas e responsabilidades**
- Serviços desacoplados (Payment API ↔ Fake Bank Service)
- Integração via HTTP + Webhooks

### Conceitos aplicados

- Webhooks assinados (HMAC + SHA-256)
- Proteção contra replay attacks (timestamp + tolerância)
- Idempotência com Redis
- Redis como fonte de verdade para expiração (TTL)
- Rate limiting em endpoints sensíveis
- Logs estruturados para auditoria
- Simulação realista de integração bancária

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.11**
- **Flask**
- **Flask SQLAlchemy**
- **SQLite** (execução local simples)
- **Redis** (TTL, cache, idempotência)
- **Docker / Docker Compose**
- **Postman** (testes manuais)

---

## 📂 Estrutura do Projeto

```text
payment-platform/
├── payment-charges-api/
│   ├── app.py
│   ├── routes/
│   │   ├── charges.py
│   │   └── webhooks.py
│   ├── services/
│   ├── repository/
│   ├── security/
│   │   ├── auth.py
│   │   ├── idempotency.py
│   │   └── webhook_signature.py
│   ├── infrastructure/
│   │   └── redis_client.py
│   ├── audit/
│   │   └── logger.py
│   └── requirements.txt
│
├── fake-bank-service/
│   ├── app.py
│   ├── routes/
│   │   └── pix.py
│   ├── services/
│   │   └── pix_service.py
│   ├── clients/
│   │   └── webhook_client.py
│   ├── security/
│   │   └── hmac.py
│   └── requirements.txt
│
└── docker-compose.yml
```

---

## 🔐 Autenticação & Segurança

- API Key para endpoints sensíveis
- Rate limit para evitar abuso
- Webhook assinado com **HMAC (SHA-256)**
- Validação de corpo bruto (raw body)
- Timestamp + janela de tolerância contra replay attacks
- Idempotência de eventos via Redis
- Redis TTL como controle de expiração de cobranças

> O modelo de segurança segue padrões utilizados por provedores como **Stripe** e **Mercado Pago**.

---

## 🔗 Endpoints da API

### 🔹 Cobranças

- `POST /charges` — Criação de cobrança
- `GET /charges/{id}` — Consulta de cobrança (com cache Redis)

### 🔹 Webhooks

- `POST /webhooks/pix` — Confirmação de pagamento via banco

---

## 📥 Exemplo de Webhook (Fake Bank → API)

Payload:

```json
{
  "external_id": "9a6c1c55-acde-4b9b-9c6f-8c7b4b2e9a12",
  "value": 150.00,
  "status": "PAID"
}
```

Headers:

```
X-Signature: sha256=...
X-Timestamp: 1700000000
```

---

## 🧪 Testes da API

- Testes manuais via Postman
- Cenários testados:
  - Criação de cobrança válida
  - Webhook válido
  - Webhook duplicado (idempotência)
  - Webhook fora da janela de tempo
  - Tentativa de pagamento expirado
  - Rate limit excedido

---

## ⚙️ Como Executar o Projeto

### Pré-requisitos

- Docker
- Docker Compose

### Subir todos os serviços

```bash
docker-compose up
```

A API ficará disponível em:

```
http://localhost:5000
```

Fake Bank Service:

```
http://localhost:6000
```

---

## 📌 Próximos Passos (Backlog)

- [ ] Testes automatizados
- [ ] Retry com backoff para webhooks
- [ ] Observabilidade (metrics)
- [ ] Persistência no Fake Bank
- [ ] Deploy em ambiente cloud

---

## 👨‍💻 Author

**Yago Félix**

💼 Desenvolvedor Python — Back-end | Full Stack  
🔍 Focado em APIs, automação e sistemas distribuídos  

🔗 GitHub: https://github.com/yagofelix00  
🔗 LinkedIn: https://www.linkedin.com/in/yago-felix-737011279/
