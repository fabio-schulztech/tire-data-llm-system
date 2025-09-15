# Sistema de Análise de Dados TPMS com IA

Sistema inteligente de monitoramento de pneus (TPMS - Tire Pressure Monitoring System) que utiliza ChatGPT para gerar consultas SQL, analisar dados e criar relatórios HTML estilizados.

## 🚀 Funcionalidades

- **Consultas em Linguagem Natural**: Faça perguntas em português sobre os dados de pneus
- **Geração Automática de SQL**: ChatGPT converte perguntas em consultas SQL otimizadas
- **Análise Inteligente de Dados**: IA analisa resultados e gera insights detalhados
- **Relatórios HTML Estilizados**: Geração automática de relatórios visuais profissionais
- **Interface Web Responsiva**: Interface moderna e intuitiva
- **Validação de Schema**: Garante que consultas usem apenas colunas existentes

## 🏗️ Arquitetura

### Fluxo de Dados
1. **Usuário** → Pergunta em linguagem natural
2. **ChatGPT** → Gera consulta SQL baseada na pergunta
3. **PostgreSQL** → Executa consulta e retorna dados
4. **ChatGPT** → Analisa dados e gera insights
5. **ChatGPT** → Cria HTML estilizado com a análise
6. **Usuário** → Recebe relatório HTML completo

### Componentes Principais
- **`llm_agent.py`**: Agente LLM principal com integração ChatGPT
- **`web_app.py`**: Interface Flask para API e frontend
- **`statistical_analyzer.py`**: Analisador estatístico de dados
- **`explore_database.py`**: Utilitário para exploração do banco

## 📊 Banco de Dados

### Tabela: `tire_data_json_llm`
- **id**: Chave primária
- **odometro**: Odômetro acumulado do veículo (km)
- **movimento**: Indica se o veículo está em movimento
- **speed**: Velocidade instantânea (km/h)
- **imei**: IMEI do dispositivo de telemetria
- **placa**: Placa do veículo
- **cliente**: Cliente/empresa proprietária
- **position**: Posição do pneu (1, 2, 3, 4)
- **latitude/longitude**: Coordenadas GPS
- **pressure**: Pressão do pneu (PSI)
- **temperature**: Temperatura do pneu (°C)
- **_timestamp_**: Data e hora da leitura

## 🛠️ Instalação

### Pré-requisitos
- Python 3.8+
- PostgreSQL
- Conta OpenAI (API Key)

### Configuração
1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/tire-data-llm-system.git
cd tire-data-llm-system
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

4. Configure o banco de dados:
```bash
# Crie o banco PostgreSQL e configure a URL de conexão
```

5. Execute a aplicação:
```bash
python web_app.py
```

## 🔧 Configuração

### Variáveis de Ambiente
```env
OPENAI_API_KEY=sua_chave_openai
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
RESULT_LIMIT=50000
MIN_RESULT_LIMIT=10000
MAX_QUERY_TIMEOUT=30
DEBUG=True
```

### Dependências
- `flask`: Framework web
- `openai`: Integração com ChatGPT
- `psycopg2`: Conexão PostgreSQL
- `pandas`: Manipulação de dados
- `python-dotenv`: Gerenciamento de variáveis de ambiente

## 📝 Uso

### API Endpoints

#### `POST /api/query`
Processa consultas em linguagem natural.

**Request:**
```json
{
  "query": "Qual é a pressão média dos pneus do veículo ABC1234?"
}
```

**Response:**
```json
{
  "success": true,
  "query": "Qual é a pressão média dos pneus do veículo ABC1234?",
  "sql": "SELECT AVG(pressure) FROM tire_data_json_llm WHERE placa = 'ABC1234'",
  "analysis": "Análise detalhada dos dados...",
  "data_count": 150,
  "data": [...]
}
```

#### `POST /api/generate-html`
Gera relatório HTML estilizado.

**Request:**
```json
{
  "question": "Pergunta original",
  "analysis": "Análise gerada pelo ChatGPT"
}
```

**Response:**
```json
{
  "success": true,
  "html": "<!DOCTYPE html>...",
  "timestamp": "2024-01-01T12:00:00"
}
```

### Exemplos de Perguntas
- "Quantos veículos temos no sistema?"
- "Qual placa tem a maior variação de pressão?"
- "Mostre estatísticas de temperatura por cliente"
- "Quais pneus estão com pressão baixa?"
- "Qual é o consumo de combustível estimado por veículo?"

## 🧠 Inteligência Artificial

### Modelos Utilizados
- **GPT-4o-mini**: Geração de SQL e análise de dados
- **GPT-4o-mini**: Criação de HTML estilizado

### Prompts Especializados
- **Geração de SQL**: Otimizado para PostgreSQL com validação de schema
- **Análise de Dados**: Contexto específico de TPMS e gestão de frotas
- **Geração de HTML**: Design responsivo e profissional

## 📈 Monitoramento

### Logs
- Consultas SQL geradas
- Tempo de execução
- Erros e exceções
- Análises geradas

### Métricas
- Número de consultas processadas
- Tempo médio de resposta
- Taxa de sucesso das consultas
- Uso de recursos

## 🔒 Segurança

- Validação de entrada de dados
- Sanitização de consultas SQL
- Rate limiting (configurável)
- Logs de auditoria
- Tratamento seguro de erros

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 👥 Equipe

- **Desenvolvimento**: Equipe Schulz Tech
- **IA/ML**: Integração ChatGPT
- **Backend**: Python/Flask/PostgreSQL
- **Frontend**: HTML/CSS/JavaScript

## 📞 Suporte

Para suporte e dúvidas:
- Email: suporte@schulztech.com.br
- Issues: [GitHub Issues](https://github.com/seu-usuario/tire-data-llm-system/issues)

---

**Desenvolvido com ❤️ pela equipe Schulz Tech**
