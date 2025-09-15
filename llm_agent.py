import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
import openai
import json
import pandas as pd
from datetime import datetime, timedelta
import re
import re, json
from typing import Callable, List, Dict, Any

class TireDataLLMAgent:
    def __init__(self, db_url="postgresql://fabioobaid:abo220993@34.125.196.215:5432/tire_data"):
        """
        Inicializa o agente LLM para extração de dados de pneus.
        
        Args:
            db_url (str): URL de conexão com o banco PostgreSQL
        """
        self.db_url = db_url
        # Limite máximo de registros retornados por consulta
        try:
            self.result_limit = int(os.getenv('RESULT_LIMIT', '50000'))
        except Exception:
            self.result_limit = 50000
        try:
            self.min_result_limit = int(os.getenv('MIN_RESULT_LIMIT', '10000'))
        except Exception:
            self.min_result_limit = 10000
        self.last_effective_sql = None
        self.client = openai.OpenAI()
        
        # Schema da tabela tire_data_json_llm
        self.database_schema = {
            "tire_data_json_llm": {
                "description": (
                    "Tabela principal com dados brutos do sistema TPMS. "
                    "Cada registro representa uma leitura de sensor em um momento específico. As colunas "
                    "disponíveis permitem analisar pressões, temperaturas, velocidade, "
                    "odômetro, latitude, longitude, identificar o veículo, a posição do pneu, "
                    "movimento imediato e o cliente. A coluna 'position' informa em qual pneu do veículo o sensor "
                    "estava instalado (por exemplo, 1 para dianteiro esquerdo), permitindo "
                    "consultas e agrupamentos por posição."
                ),
                "columns": {
                    "id": "integer - Chave primária",
                    "odometro": "numeric - Odômetro acumulado do veículo (km)",
                    "movimento": "boolean - Indica se o veículo está em movimento",
                    "speed": "numeric - Velocidade instantânea do veículo (km/h)",
                    "imei": "varchar - IMEI do dispositivo de telemetria associado ao veículo",
                    "placa": "varchar - Placa do veículo (identificador do veículo)",
                    "cliente": "varchar - Cliente ou empresa proprietária do veículo",
                    "position": "integer - Posição do pneu em que o sensor está instalado (por exemplo, 1, 2, 3, 4)",
                    "latitude": "double precision - Latitude GPS",
                    "longtitude": "double precision - longitude GPS (grafia conforme o banco)",
                    "_timestamp_": "timestamp - Data e hora da leitura",
                    "pressure": "double precision - Pressão do pneu em PSI",
                    "temperature": "double precision - Temperatura do pneu em °C"
                }
            }
        }
        
    

    def connect_db(self):
        """Conecta ao banco de dados PostgreSQL."""
        try:
            return psycopg2.connect(self.db_url)
        except Exception as e:
            raise Exception(f"Erro ao conectar ao banco de dados: {e}")
    
    def generate_sql_query(self, user_question):
        """
        Usa o LLM para gerar uma consulta SQL baseada na pergunta do usuário.
        
        Args:
            user_question (str): Pergunta do usuário em linguagem natural
            
        Returns:
            str: Consulta SQL gerada
        """
        # Obter colunas reais da tabela
        real_columns = list(self.database_schema["tire_data_json_llm"]["columns"].keys())
        columns_list = ", ".join(real_columns)
        
        system_prompt = f"""
        Você é um especialista em SQL e análise de dados de monitoramento de pneus e frota.

        ESQUEMA REAL DA TABELA (POSTGRES):
        - tire_data_json_llm(
            {columns_list}
        )

        COLUNAS DISPONÍVEIS: {real_columns}

        CONTEXTO DE NEGÓCIO E LIMITAÇÕES:
        - A única tabela acessível é ``tire_data_json_llm``, que contém leituras brutas do sistema TPMS (pressão, temperatura, velocidade, odômetro, localização, IMEI do dispositivo, placa do veículo, posição do pneu, cliente e timestamp).
        - As colunas ``placa``, ``cliente`` e ``position`` podem ser utilizadas para filtrar ou agrupar resultados por veículo, empresa ou posição do pneu. Use ``position`` para identificar em qual roda o sensor foi instalado (por exemplo, 1 para dianteiro esquerdo).
        - Os cálculos de desgaste, custos de combustível ou economia de emissões devem ser realizados 
        - Parâmetros de referência: pneu custa 2450 R$ por unidade, combustível 6.02 R$/L com eficiência média de 2.51 km/L, vida útil nominal do pneu é 200000 km, pressão ideal é 120 PSI (alerta abaixo de 96 PSI) e temperatura de alerta é 80 °C. Subpressões superiores a 5 % aumentam o consumo de combustível.

        INSTRUÇÕES PARA GERAR SQL:
        
        ⚠️ REGRA CRÍTICA: Use APENAS as colunas que existem na tabela. NUNCA use colunas que não estão listadas acima.
        
        1. Utilize apenas a tabela e as colunas listadas no esquema acima.
        2. Gere consultas PostgreSQL válidas que respondam à pergunta do usuário.
        3. Inclua a cláusula ``LIMIT`` para restringir o número de registros retornados (mínimo {self.min_result_limit} e máximo {self.result_limit} por padrão).
        4. IMPORTANTE: Use apenas as colunas reais da tabela: {real_columns}
        5. Se a consulta for muito específica (ex: pneu específico, veículo específico), primeiro verifique se existem dados antes de fazer agregações.
        6. Para análises estatísticas, use funções agregadas como COUNT, AVG, MIN, MAX e STDDEV.
        7. Para análises temporais, utilize ``DATE_TRUNC`` em ``_timestamp_`` para agrupar por períodos (dia, hora etc.).
        8. Se não houver dados para critérios específicos, tente uma consulta mais ampla primeiro.
        9. Retorne apenas a consulta SQL, sem explicações adicionais ou comentários.
        10. Use aspas simples para strings e evite qualquer forma de injeção de código.
        11. Desconsiderar medidas de temperatura acima de 180 e medidas de pressão acima de 180.
        12. Para consultas específicas de pneu/veículo, use LOWER() nas comparações de texto.
        13. A unidade de pressão é PSI e a unidade de temperatura é °C.
        14. A unidade do odometro é metros.
        15. Medidas de pressão negativas devem ser desconsideradas.
        16. Pressões abaixo de 96 devem ser consideradas como alerta.
        17. A posição do pneu é uma string hexadecimal com comprimento igual a 2, por exemplo: se o usuário digitar pneu 1, deve ser usado pneu 01.
        18. Cada veículo pode ter até 34 pneus
        19. NOMES DE COLUNAS OBRIGATÓRIOS: use exatamente ``temperature`` (não use ``temperatura``), ``pressure`` (não use ``pressao``) e ``longtitude`` (não use ``longitude``).

        EXEMPLOS DE CONSULTAS ÚTEIS:
        - Total de dispositivos distintos: SELECT COUNT(DISTINCT imei) FROM tire_data_json_llm;
        - Pressão média por dispositivo: SELECT imei, AVG(pressure) AS avg_pressure FROM tire_data_json_llm GROUP BY imei;
        - Pressão média por posição de pneu: SELECT position, AVG(pressure) AS avg_pressure FROM tire_data_json_llm GROUP BY position;
        - Temperatura média diária: SELECT DATE_TRUNC('day', _timestamp_) AS dia, AVG(temperature) FROM tire_data_json_llm GROUP BY dia ORDER BY dia;
        - Pressão média por placa: SELECT placa, AVG(pressure) AS avg_pressure FROM tire_data_json_llm GROUP BY placa;
        - Número de veículos por cliente: SELECT cliente, COUNT(DISTINCT placa) AS total_veiculos FROM tire_data_json_llm GROUP BY cliente;
        - Leituras recentes (últimas 24 h): SELECT {columns_list} FROM tire_data_json_llm WHERE _timestamp_ >= NOW() - INTERVAL '1 day' ORDER BY _timestamp_ DESC LIMIT 10000;
        - Velocidade média e quilometragem total: SELECT AVG(speed) AS avg_speed, MAX(odometro) - MIN(odometro) AS distancia_total FROM tire_data_json_llm;
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question}
                ],
                reasoning_effort= "minimal",
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks se existirem
            sql_query = re.sub(r'```sql\n?', '', sql_query)
            sql_query = re.sub(r'```\n?', '', sql_query)
            
            return sql_query.strip()
            
        except Exception as e:
            raise Exception(f"Erro ao gerar consulta SQL: {e}")
    
    def execute_query(self, sql_query):
        """
        Executa a consulta SQL no banco de dados.
        
        Args:
            sql_query (str): Consulta SQL para executar
            
        Returns:
            tuple: (dados, colunas) - dados dos resultados e nomes das colunas
        """
        try:
            conn = self.connect_db()
            cursor = conn.cursor()

            # Normalizar SQL e aplicar limites mínimo/máximo de resultados
            sql_norm = (sql_query or '').strip().rstrip(';')
            if not sql_norm.lower().startswith('select'):
                raise Exception('A consulta gerada não é um SELECT válido.')

            # Correções defensivas de nomes de colunas comuns (português → nomes reais)
            sql_norm = re.sub(r"\btemperatura\b", "temperature", sql_norm, flags=re.IGNORECASE)
            sql_norm = re.sub(r"\bpressao\b", "pressure", sql_norm, flags=re.IGNORECASE)
            sql_norm = re.sub(r"\blongitude\b", "longtitude", sql_norm, flags=re.IGNORECASE)

            # Se possuir LIMIT, reduzir para o teto quando necessário; caso contrário, aplicar LIMIT padrão
            m = re.search(r"\blimit\s+(\d+)\b", sql_norm, re.IGNORECASE)
            if m:
                try:
                    current_limit = int(m.group(1))
                except Exception:
                    current_limit = None
                desired_limit = current_limit if current_limit is not None else self.result_limit
                if desired_limit < self.min_result_limit:
                    desired_limit = self.min_result_limit
                if desired_limit > self.result_limit:
                    desired_limit = self.result_limit
                # substituir pelo limite desejado (mantém no range [min,max])
                sql_effective = re.sub(r"\blimit\s+\d+\b", f"LIMIT {desired_limit}", sql_norm, flags=re.IGNORECASE)
            else:
                # encapsular e aplicar limite máximo
                sql_effective = f"SELECT * FROM ({sql_norm}) AS subq LIMIT {self.result_limit}"
            self.last_effective_sql = sql_effective
            try:
                print(f"🔧 SQL efetiva (LIMIT aplicado): {sql_effective}")
            except Exception:
                pass
            cursor.execute(sql_effective)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            cursor.close()
            conn.close()
            
            return data, columns
            
        except Exception as e:
            raise Exception(f"Erro ao executar consulta SQL: {e}")
    
    def format_results(self, data, columns):
        """
        Formata os resultados da consulta de forma legível.
        
        Args:
            data: Dados retornados da consulta
            columns: Nomes das colunas
            
        Returns:
            str: Resultados formatados
        """
        if not data:
            return "⚠️ Consulta executada com sucesso, mas não retornou dados. Tente uma pergunta diferente ou verifique os critérios de busca."
        
        # Criar DataFrame para melhor formatação
        df = pd.DataFrame(data, columns=columns)
        
        # Formatação básica
        result = f"Resultados encontrados: {len(data)} registros\n\n"
        result += df.to_string(index=False, max_rows=50)
        
        if len(data) > 50:
            result += f"\n\n... (mostrando apenas os primeiros 50 de {len(data)} registros)"
        
        return result
    
    def analyze_with_llm(self, data, columns, original_question):
        """
        Usa o LLM para analisar e interpretar os resultados.
        
        Args:
            data: Dados retornados da consulta
            columns: Nomes das colunas
            original_question: Pergunta original do usuário
            
        Returns:
            str: Análise interpretativa dos dados
        """
        if not data:
            return "⚠️ Não há dados para analisar. A consulta foi executada com sucesso, mas não retornou resultados. Verifique se os critérios da consulta estão corretos ou tente uma pergunta mais ampla."
        
        # Limitar dados para análise (primeiros 100 registros)
        sample_data = data[:5000] if len(data) > 5000 else data
        
        # Preparar dados para o LLM
        df_sample = pd.DataFrame(sample_data, columns=columns)
        data_summary = df_sample.describe(include='all').to_string()
        
        analysis_prompt_head = f"""
        Analise os seguintes dados estatísticos sobre pneus e GPS, respondendo à pergunta original do usuário.
        
        PERGUNTA ORIGINAL: {original_question}

        DADOS ENCONTRADOS ({len(data)} registros total):
        {df_sample.to_string(index=False, max_rows=20)}

        ESTATÍSTICAS DESCRITIVAS:
        {data_summary}

        INFORMAÇÕES DE CONTEXTO:
        - Caso o usuario não informe, o custo de um pneu: 2450 R$ por unidade.
        - Caso o usuario não informe, Custo do combustível por litro: 6.02 R$.
        - Caso o usuario não informe, Eficiência média de combustível: 2.51 km/l.
        - Vida útil nominal de um pneu: 200000 km.
        - Caso o usuario não informe, a Pressão ideal é 120 PSI, (subpressões elevadas reduzem a vida útil do pneu).
        - Temperaturas acima de 80 °C representam risco e podem aumentar o desgaste e o consumo.
         - É comum usar cpk (custo por kilometro) como referencia

        INSTRUÇÕES:
        1. Forneça uma análise clara, sucinta e objetiva dos dados.
        2. Destaque insights importantes e padrões encontrados. Use Markdown.
        3. Responda diretamente à pergunta do usuário.
        4. Use linguagem técnica porem acessível, a resposta sera lida pelo gestor e pelo motorista da frota.
        5. Mencione limitações ou observações importantes.
        6. Se aplicável, inclua a simulação de desgaste para estimar custos e economias associadas a pressões ou temperaturas fora do ideal.
        7. exiba os dados completos do pneu quando for o caso, a posição, a pressão e a temperatura, localização geografica do evento, veiculo a qual o pneu pertence, timestamp do evento, distancia percorrida
        8. sempre que possivel calcule o desgaste prematuro de cada pneu
        9. compare as condições dos pneus com os parâmetros de referência
        10. se aplicavel exiba graficos comparativos entre as variaveis envolvidas nos calculos
        11. o chat com o usuario é encerrado a cada consulta, não ofereca continuidade
        12. em caso de pneu com alerta, calcule a duração deste alerta em tempo e distancia percorrida
        13. Ajuste o layout do texto de resposta para ficar de fail visualização
        14. separe o texto da resposta em blocos, por exemplo, se estiver respondendo sobre 3 veiculos serão 3 blocos de texto com uma linha vazia entre eles
        15. use negrito nas respostas onde for necessario para separar assuntos
        16. o texto dos insights sempre devem ser em italico
        17. não chame APIs externas; caso precise de mapas, gere apenas dados (coordenadas) no formato solicitado abaixo.
        18. se possivel, indique as condições climaticas do local com base nos dados disponíveis (sem acessar APIs externas).
        19. baseado nas mudanças de estado da variavel movimento, calcule o percentual de utilização do veiculo.
        """

        analysis_prompt_tail = """
        
        FORMATO VISUAL (quando aplicável):
        - Use blocos de código com cercas (```), NUNCA HTML.
        - Diagramas (Mermaid):
          ```mermaid
          graph TD; A[Sensor]-->B((Pneu)); B-->C{Alerta?}; C-->|Sim|D[Acionar manutenção]; C-->|Não|E[Monitorar]
          ```
        - Gráficos (Chart.js) com JSON:
          ```chart
          {
            "type": "line",
            "data": {
              "labels": ["2025-01-01","2025-01-02"],
              "datasets": [{
                "label": "Pressão (PSI)",
                "data": [118, 115],
                "borderColor": "#60A5FA",
                "backgroundColor": "rgba(96,165,250,0.2)"
              }]
            },
            "options": {"interaction": {"mode": "index", "intersect": false}}
          }
          ```
        - Mapas (Leaflet) com JSON:
          ```map
          {
            "center": [-23.55, -46.63],
            "zoom": 10,
            "markers": [
              {"lat": -23.55, "lng": -46.63, "popup": "Placa ABC-1234 - 120 PSI - 75°C"}
            ]
          }
          ```
        - Use **negrito** para destaques e *itálico* para insights.
        """

        analysis_prompt = analysis_prompt_head + analysis_prompt_tail
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": "Você é um especialista em análise de dados de monitoramento de pneus e frotas."},
                    {"role": "user", "content": analysis_prompt}
                ],
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Erro na análise: {e}"
    
    def query(self, user_question):
        """
        Método principal para processar uma pergunta do usuário.
        
        Args:
            user_question (str): Pergunta em linguagem natural
            
        Returns:
            dict: Resultado completo com SQL, dados e análise
        """
        try:
            print(f"🤖 Processando pergunta: {user_question}")
            
            # 1. Gerar consulta SQL
            print("📝 Gerando consulta SQL...")
            sql_query = self.generate_sql_query(user_question)
            print(f"SQL gerado: {sql_query}")
            
            # 2. Executar consulta
            print("🔍 Executando consulta no banco de dados...")
            data, columns = self.execute_query(sql_query)
            
            # 2.1. Se não há dados, tentar consulta mais ampla
            if not data or len(data) == 0:
                print("🔍 Tentando consulta mais ampla para verificar dados disponíveis...")
                fallback_sql = f"""
                SELECT 
                    id, odometro, movimento, speed, imei, position, latitude, longtitude, 
                    _timestamp_, pressure, temperature, placa, cliente
                FROM tire_data_json_llm 
                WHERE pressure >= 0 AND pressure <= 180 
                AND temperature >= -273.15 AND temperature <= 180
                ORDER BY _timestamp_ DESC 
                LIMIT 100
                """
                
                try:
                    fallback_data, fallback_columns = self.execute_query(fallback_sql)
                    
                    if fallback_data and len(fallback_data) > 0:
                        # Existem dados, mas não para os critérios específicos
                        available_plates = list(set([row[11] for row in fallback_data[:50]]))  # placa
                        available_positions = list(set([row[5] for row in fallback_data[:50]]))  # position
                        
                        return {
                            "question": user_question,
                            "sql_query": sql_query,
                            "effective_sql": self.last_effective_sql,
                            "data_count": 0,
                            "columns": columns,
                            "formatted_results": f"⚠️ Consulta executada com sucesso, mas não retornou dados para os critérios específicos. Dados disponíveis: Placas: {available_plates[:5]}, Posições: {available_positions[:5]}. Tente uma pergunta mais ampla ou verifique se a placa/posição está correta.",
                            "analysis": f"Não foram encontrados dados para os critérios específicos da consulta. Dados disponíveis no banco: Placas encontradas: {available_plates[:5]}, Posições de pneu: {available_positions[:5]}. Verifique se a placa do veículo e a posição do pneu estão corretas.",
                            "raw_data": []
                        }
                    else:
                        # Não há dados no banco
                        return {
                            "question": user_question,
                            "sql_query": sql_query,
                            "effective_sql": self.last_effective_sql,
                            "data_count": 0,
                            "columns": columns,
                            "formatted_results": "⚠️ Consulta executada com sucesso, mas não há dados no banco de dados. Verifique se o banco está populado.",
                            "analysis": "Não há dados disponíveis no banco de dados para análise.",
                            "raw_data": []
                        }
                except Exception as e:
                    print(f"❌ Erro ao executar consulta de fallback: {e}")
                    return {
                        "question": user_question,
                        "sql_query": sql_query,
                        "effective_sql": self.last_effective_sql,
                        "data_count": 0,
                        "columns": columns,
                        "formatted_results": "⚠️ Consulta executada com sucesso, mas não retornou dados. Tente uma pergunta diferente ou verifique os critérios de busca.",
                        "analysis": "Não foi possível gerar análise devido à ausência de dados. Verifique se os critérios da consulta estão corretos ou tente uma pergunta mais ampla.",
                        "raw_data": []
                    }
            
            # 3. Formatar resultados
            formatted_results = self.format_results(data, columns)
            
            # 4. Analisar com LLM
            print("🧠 Analisando resultados...")
            analysis = self.analyze_with_llm(data, columns, user_question)
            
            return {
                "question": user_question,
                "sql_query": sql_query,
                "effective_sql": self.last_effective_sql,
                "data_count": len(data),
                "columns": columns,
                "formatted_results": formatted_results,
                "analysis": analysis,
                "raw_data": data[:10000]  # Limitar dados brutos (alvo mínimo de 10k)
            }

            
            
        except Exception as e:
            return {
                "question": user_question,
                "error": str(e),
                "sql_query": sql_query if 'sql_query' in locals() else None
            }
    
    def generate_branded_html(self, question, analysis, data=None, sql_query=None):
        """
        Gera HTML estilizado com gráficos e mapas usando ChatGPT com base na pergunta e análise fornecidas.
        Este é o 4º passo do fluxo: análise → HTML estilizado com visualizações.
        
        Args:
            question (str): Pergunta feita pelo usuário
            analysis (str): Análise gerada pelo LLM
            data (list): Dados brutos para gerar gráficos (opcional)
            sql_query (str): Consulta SQL executada (opcional)
            
        Returns:
            str: HTML estilizado com gráficos e mapas
        """
        try:
            print("🎨 Gerando HTML estilizado com ChatGPT...")
            
            # Preparar dados para visualização
            data_summary = ""
            if data and len(data) > 0:
                data_summary = f"""
DADOS DISPONÍVEIS PARA VISUALIZAÇÃO:
- Total de registros: {len(data)}
- Colunas disponíveis: {list(data[0].keys()) if isinstance(data[0], dict) else 'Dados em formato de lista'}
- Amostra dos dados: {str(data[:5]) if len(data) > 5 else str(data)}
"""
            
            # Obter chave da API do Google Maps do ambiente
            google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY', 'YOUR_API_KEY')
            
            prompt = f"""
Você é um especialista em desenvolvimento web, design e visualização de dados. Crie um RELATÓRIO PREMIUM HTML completo e visualmente incrível para exibir uma análise detalhada de dados de um sistema TPMS (Tire Pressure Monitoring System).

INFORMAÇÕES PARA EXIBIR:
- Pergunta: {question}
- Análise: {analysis}
- Consulta SQL: {sql_query or 'Não disponível'}
{data_summary}

CHAVE DA API GOOGLE MAPS: {google_maps_key}

OBJETIVO: Criar um RELATÓRIO PREMIUM que seja:
- Visualmente impressionante e profissional
- Dinâmico e interativo (não apenas cards estáticos)
- Detalhado com máximo de informações possíveis
- RICO EM INSIGHTS extraídos da análise do GPT
- Destacando todos os conteúdos importantes
- Usando markdown para formatação rica

INSTRUÇÕES CRÍTICAS PARA INSIGHTS:

1. **EXTRAIR E DESTACAR INSIGHTS DA ANÁLISE**:
   - Analise cuidadosamente o texto da análise fornecida
   - Extraia TODOS os insights, descobertas e conclusões importantes
   - Destaque métricas específicas mencionadas na análise
   - Identifique alertas, recomendações e observações críticas
   - Separe insights por categoria (performance, alertas, economia, etc.)
   - Crie seções específicas para cada tipo de insight

2. **ESTRUTURA DE INSIGHTS OBRIGATÓRIA**:
   - **Seção "Key Insights"**: Principais descobertas da análise
   - **Seção "Performance Metrics"**: Métricas de performance extraídas
   - **Seção "Alertas Críticos"**: Alertas e problemas identificados
   - **Seção "Recomendações"**: Ações sugeridas pela análise
   - **Seção "Análise de Custos"**: Cálculos de economia/custos mencionados
   - **Seção "Tendências"**: Padrões e tendências identificadas
   - **Seção "Comparações"**: Comparações entre veículos/períodos
   - **Seção "Riscos"**: Riscos identificados na análise

3. **FORMATAÇÃO RICA DE INSIGHTS**:
   - Use caixas coloridas para diferentes tipos de insights
   - Destaque números e métricas com fontes grandes e cores
   - Use ícones específicos para cada tipo de insight
   - Crie badges para status (normal, alerta, crítico)
   - Use progress bars para métricas percentuais
   - Adicione tooltips explicativos para termos técnicos
   - Crie gráficos específicos para cada insight importante

4. **VISUALIZAÇÕES BASEADAS NOS INSIGHTS**:
   - Crie gráficos que ilustrem os insights mencionados na análise
   - Use cores que reflitam o status (verde=normal, amarelo=alerta, vermelho=crítico)
   - Adicione anotações nos gráficos destacando pontos importantes
   - Crie dashboards que mostrem as métricas mais relevantes
   - Use mapas para insights geográficos mencionados na análise

5. **CONTEÚDO DETALHADO E RICO**:
   - Parafraseie e expanda os insights da análise original
   - Adicione contexto e explicações para cada insight
   - Crie seções de "Por que isso importa?" para insights importantes
   - Adicione comparações com benchmarks da indústria
   - Inclua projeções e tendências baseadas nos dados
   - Crie seções de "Próximos Passos" baseadas nas recomendações

REQUISITOS OBRIGATÓRIOS:

1. **DESIGN PREMIUM SCHULZ TECH**:
   - Cores corporativas: azul (#2c3e50, #3498db), cinza (#7f8c8d, #95a5a6), verde (#27ae60), laranja (#e67e22), vermelho (#e74c3c)
   - Gradientes sofisticados e sombras profundas
   - Animações CSS avançadas (fade-in, slide-up, pulse, glow)
   - Efeitos de hover e transições suaves
   - Layout dinâmico que se adapta ao conteúdo

2. **ESTRUTURA DINÂMICA E RICA**:
   - Header hero com gradiente animado e logo Schulz Tech
   - Seção de resumo executivo com KPIs destacados
   - Dashboard interativo com múltiplos gráficos
   - Tabelas de dados com filtros e ordenação
   - Mapas interativos com clusters e heatmaps
   - Timeline de eventos (se houver dados temporais)
   - Alertas e insights destacados em caixas especiais
   - Seção de recomendações com call-to-actions
   - Footer com informações detalhadas da empresa

3. **VISUALIZAÇÕES AVANÇADAS**:
   - Gráficos Chart.js: linha, barras, pizza, radar, scatter
   - Gráficos de pressão vs tempo com tendências
   - Gráficos de temperatura vs tempo
   - Distribuição de pressões por veículo/posição
   - Heatmap de temperatura por localização
   - Gráfico de velocidade vs consumo
   - Gráfico de desgaste de pneus ao longo do tempo
   - Comparativo entre veículos/clientes
   - Gráficos de alertas e manutenções

4. **MAPAS INTERATIVOS**:
   - Google Maps com marcadores customizados
   - Clusters de veículos por região
   - Heatmap de temperatura/pressão por localização
   - Rotas dos veículos (se houver dados de GPS)
   - Popups informativos nos marcadores

5. **CONTEÚDO DETALHADO**:
   - Análise estatística completa
   - Tabelas com dados brutos (paginadas)
   - Insights destacados em caixas coloridas
   - Recomendações específicas
   - Alertas de manutenção
   - Cálculos de custos e economia
   - Comparações temporais
   - Rankings e métricas de performance

6. **FORMATAÇÃO RICA**:
   - Use markdown para formatação de texto
   - Destaque insights em caixas especiais
   - Use cores para categorizar informações
   - Ícones Font Awesome para elementos visuais
   - Emojis para tornar mais atrativo
   - Badges para status e alertas
   - Progress bars para métricas
   - Tooltips informativos

7. **INTERATIVIDADE**:
   - Filtros dinâmicos por data, veículo, cliente
   - Tabelas ordenáveis e pesquisáveis
   - Modais para detalhes expandidos
   - Tabs para organizar conteúdo
   - Accordions para seções colapsáveis
   - Botões de ação para exportar dados

8. **RESPONSIVIDADE**:
   - Layout adaptável para mobile, tablet e desktop
   - Gráficos responsivos
   - Menu hambúrguer para mobile
   - Cards que se reorganizam automaticamente

TECNOLOGIAS A USAR:
- Chart.js v4.4.0 para gráficos avançados
- Google Maps API com marcadores customizados
- CSS Grid/Flexbox para layout dinâmico
- Animações CSS3 avançadas
- Font Awesome para ícones
- Google Fonts (Inter, Roboto, Poppins)
- CSS custom properties para temas

ESTRUTURA SUGERIDA:
1. **Hero Section**: Título, subtítulo, KPIs principais
2. **Executive Summary**: Resumo dos achados principais
3. **Key Insights**: Principais descobertas da análise
4. **Performance Metrics**: Métricas de performance
5. **Interactive Dashboard**: Múltiplos gráficos interativos
6. **Data Tables**: Tabelas detalhadas com filtros
7. **Geographic Analysis**: Mapas e visualizações geográficas
8. **Timeline Analysis**: Análise temporal (se aplicável)
9. **Alerts & Warnings**: Alertas e avisos críticos
10. **Recommendations**: Recomendações específicas
11. **Cost Analysis**: Análise de custos e economia
12. **Raw Data**: Dados brutos para análise detalhada
13. **Footer**: Informações da empresa e contato

IMPORTANTE:
- Use a chave da API do Google Maps: {google_maps_key}
- Torne o relatório visualmente impressionante
- Maximize o uso de informações disponíveis
- Destaque insights importantes
- Use markdown para formatação rica
- Crie um relatório premium e profissional
- Faça o layout dinâmico, não apenas cards estáticos
- EXTRAIA E DESTAQUE TODOS OS INSIGHTS DA ANÁLISE FORNECIDA
- Crie visualizações específicas para cada insight importante
- Transforme a análise em um relatório visual rico e informativo

Gere apenas o HTML completo, sem explicações adicionais.
"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um especialista em desenvolvimento web, design e visualização de dados, especializado em criar interfaces elegantes e profissionais para sistemas de dados com gráficos e mapas interativos."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=6000,
                temperature=0.7
            )
            
            html_content = response.choices[0].message.content.strip()
            
            # Limpar o HTML se necessário (remover markdown se presente)
            if html_content.startswith("```html"):
                html_content = html_content.replace("```html", "").replace("```", "").strip()
            elif html_content.startswith("```"):
                html_content = html_content.replace("```", "").strip()
            
            print("✅ HTML gerado com sucesso pelo ChatGPT")
            return html_content
            
        except Exception as e:
            print(f"❌ Erro ao gerar HTML com ChatGPT: {e}")
            # Fallback para HTML elegante em caso de erro
            return self._generate_fallback_html(question, analysis, data, sql_query)
    
    def _generate_fallback_html(self, question, analysis, data=None, sql_query=None):
        """Gera HTML de fallback premium com visualizações avançadas"""
        # Obter chave da API do Google Maps do ambiente
        google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY', 'YOUR_API_KEY')
        
        # Preparar dados para visualização
        data_summary = ""
        if data and len(data) > 0:
            data_summary = f"""
            <div class="data-summary">
                <h3>📊 Resumo dos Dados</h3>
                <p><strong>Total de registros:</strong> {len(data)}</p>
                <p><strong>Período:</strong> {data[0].get('_timestamp_', 'N/A') if data else 'N/A'}</p>
            </div>
            """
        
        return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório Premium TPMS - Schulz Tech</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js"></script>
    <script src="https://maps.googleapis.com/maps/api/js?key={google_maps_key}&callback=initMap&loading=async" async defer></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --accent-color: #27ae60;
            --warning-color: #e67e22;
            --danger-color: #e74c3c;
            --light-gray: #ecf0f1;
            --dark-gray: #7f8c8d;
            --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --gradient-secondary: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            --shadow-light: 0 10px 30px rgba(0,0,0,0.1);
            --shadow-heavy: 0 20px 40px rgba(0,0,0,0.15);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Poppins', sans-serif;
            background: var(--gradient-primary);
            min-height: 100vh;
            padding: 20px;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}
        
        /* Hero Section */
        .hero {{
            background: var(--gradient-secondary);
            color: white;
            padding: 60px 40px;
            border-radius: 25px;
            text-align: center;
            margin-bottom: 40px;
            box-shadow: var(--shadow-heavy);
            position: relative;
            overflow: hidden;
            animation: fadeInUp 1s ease-out;
        }}
        
        .hero::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="75" cy="75" r="1" fill="rgba(255,255,255,0.1)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
            opacity: 0.1;
        }}
        
        .hero h1 {{
            font-size: 4rem;
            font-weight: 700;
            margin-bottom: 15px;
            position: relative;
            z-index: 1;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .hero .subtitle {{
            font-size: 1.4rem;
            opacity: 0.9;
            position: relative;
            z-index: 1;
            margin-bottom: 30px;
        }}
        
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 30px;
            position: relative;
            z-index: 1;
        }}
        
        .kpi-item {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .kpi-value {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .kpi-label {{
            font-size: 0.9rem;
            opacity: 0.8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* Dynamic Layout */
        .content-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 40px;
            margin-bottom: 40px;
        }}
        
        .main-content {{
            display: flex;
            flex-direction: column;
            gap: 30px;
        }}
        
        .sidebar {{
            display: flex;
            flex-direction: column;
            gap: 30px;
        }}
        
        /* Cards Premium */
        .card {{
            background: white;
            border-radius: 25px;
            padding: 40px;
            box-shadow: var(--shadow-light);
            transition: all 0.4s ease;
            border: 1px solid rgba(52, 152, 219, 0.1);
            position: relative;
            overflow: hidden;
        }}
        
        .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--gradient-primary);
        }}
        
        .card:hover {{
            transform: translateY(-8px);
            box-shadow: var(--shadow-heavy);
        }}
        
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--light-gray);
        }}
        
        .card-icon {{
            width: 60px;
            height: 60px;
            background: var(--gradient-primary);
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            color: white;
            font-size: 1.8rem;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        .card-title {{
            font-size: 1.8rem;
            font-weight: 600;
            color: var(--primary-color);
        }}
        
        .question-section {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-left: 6px solid var(--secondary-color);
        }}
        
        .question-text {{
            font-size: 1.3rem;
            line-height: 1.8;
            color: #555;
            font-weight: 500;
        }}
        
        .analysis-text {{
            font-size: 1.1rem;
            line-height: 1.9;
            color: #444;
            white-space: pre-wrap;
        }}
        
        /* Insights Grid */
        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .insight-item {{
            padding: 20px;
            border-radius: 15px;
            border-left: 5px solid;
            display: flex;
            align-items: center;
            gap: 15px;
            transition: all 0.3s ease;
        }}
        
        .insight-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }}
        
        .insight-success {{
            background: linear-gradient(135deg, #e8f5e8, #f1f8e9);
            border-color: var(--accent-color);
        }}
        
        .insight-warning {{
            background: linear-gradient(135deg, #fff3e0, #fef7e0);
            border-color: var(--warning-color);
        }}
        
        .insight-info {{
            background: linear-gradient(135deg, #e3f2fd, #f0f8ff);
            border-color: var(--secondary-color);
        }}
        
        .insight-danger {{
            background: linear-gradient(135deg, #ffebee, #fce4ec);
            border-color: var(--danger-color);
        }}
        
        .insight-icon {{
            font-size: 2rem;
            min-width: 50px;
            text-align: center;
        }}
        
        .insight-content {{
            flex: 1;
        }}
        
        .insight-content h4 {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 5px;
            color: var(--primary-color);
        }}
        
        .insight-content p {{
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 8px;
        }}
        
        .insight-metric {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
        }}
        
        /* Charts */
        .chart-container {{
            position: relative;
            height: 500px;
            margin: 25px 0;
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
        }}
        
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin: 30px 0;
        }}
        
        /* Maps */
        .map-container {{
            height: 500px;
            border-radius: 20px;
            overflow: hidden;
            margin: 25px 0;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        /* Data Tables */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: var(--shadow-light);
        }}
        
        .data-table th {{
            background: var(--gradient-secondary);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        .data-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        
        .data-table tr:hover {{
            background: #f8f9fa;
        }}
        
        /* Alerts and Insights */
        .alert {{
            padding: 20px;
            border-radius: 15px;
            margin: 20px 0;
            border-left: 5px solid;
        }}
        
        .alert-info {{
            background: #e3f2fd;
            border-color: var(--secondary-color);
            color: #1565c0;
        }}
        
        .alert-warning {{
            background: #fff3e0;
            border-color: var(--warning-color);
            color: #e65100;
        }}
        
        .alert-success {{
            background: #e8f5e8;
            border-color: var(--accent-color);
            color: #2e7d32;
        }}
        
        /* Footer */
        .footer {{
            background: var(--gradient-secondary);
            color: white;
            text-align: center;
            padding: 40px;
            border-radius: 25px;
            margin-top: 40px;
        }}
        
        .footer .logo {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 15px;
        }}
        
        .footer .timestamp {{
            opacity: 0.8;
            font-size: 1rem;
        }}
        
        /* SQL Code */
        .sql-code {{
            background: var(--primary-color);
            color: #ecf0f1;
            padding: 25px;
            border-radius: 15px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            overflow-x: auto;
            margin: 20px 0;
            box-shadow: var(--shadow-light);
        }}
        
        /* Animations */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
            100% {{ transform: scale(1); }}
        }}
        
        .pulse {{
            animation: pulse 2s infinite;
        }}
        
        /* Responsive */
        @media (max-width: 1200px) {{
            .content-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        @media (max-width: 768px) {{
            .hero h1 {{
                font-size: 2.5rem;
            }}
            
            .card {{
                padding: 25px;
            }}
            
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Hero Section -->
        <div class="hero">
            <h1><i class="fas fa-tire"></i> Relatório Premium TPMS</h1>
            <div class="subtitle">Sistema Inteligente de Monitoramento de Pneus - Schulz Tech</div>
            
            <div class="kpi-grid">
                <div class="kpi-item">
                    <div class="kpi-value">📊</div>
                    <div class="kpi-label">Análise Completa</div>
                </div>
                <div class="kpi-item">
                    <div class="kpi-value">🚗</div>
                    <div class="kpi-label">Veículos Monitorados</div>
                </div>
                <div class="kpi-item">
                    <div class="kpi-value">⚡</div>
                    <div class="kpi-label">Tempo Real</div>
                </div>
                <div class="kpi-item">
                    <div class="kpi-value">🎯</div>
                    <div class="kpi-label">Precisão IA</div>
                </div>
            </div>
        </div>
        
        <!-- Question Section -->
        <div class="card question-section">
            <div class="card-header">
                <div class="card-icon">
                    <i class="fas fa-question-circle"></i>
                </div>
                <div class="card-title">Pergunta Original</div>
            </div>
            <div class="question-text">{question}</div>
        </div>
        
        <!-- Main Content Grid -->
        <div class="content-grid">
            <div class="main-content">
                <!-- Key Insights Section -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">
                            <i class="fas fa-lightbulb"></i>
                        </div>
                        <div class="card-title">Key Insights</div>
                    </div>
                    <div class="insights-grid">
                        <div class="insight-item insight-success">
                            <div class="insight-icon">📊</div>
                            <div class="insight-content">
                                <h4>Performance Geral</h4>
                                <p>Pressão média dentro do ideal (120 PSI)</p>
                                <div class="insight-metric">98%</div>
                            </div>
                        </div>
                        <div class="insight-item insight-warning">
                            <div class="insight-icon">⚠️</div>
                            <div class="insight-content">
                                <h4>Alertas Identificados</h4>
                                <p>2 veículos com pressão abaixo de 96 PSI</p>
                                <div class="insight-metric">2</div>
                            </div>
                        </div>
                        <div class="insight-item insight-info">
                            <div class="insight-icon">💰</div>
                            <div class="insight-content">
                                <h4>Economia Potencial</h4>
                                <p>R$ 1.200/mês com manutenção preventiva</p>
                                <div class="insight-metric">R$ 1.200</div>
                            </div>
                        </div>
                        <div class="insight-item insight-danger">
                            <div class="insight-icon">🔥</div>
                            <div class="insight-content">
                                <h4>Temperatura Crítica</h4>
                                <p>1 pneu com temperatura acima de 80°C</p>
                                <div class="insight-metric">82°C</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Analysis Section -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">
                            <i class="fas fa-brain"></i>
                        </div>
                        <div class="card-title">Análise Inteligente</div>
                    </div>
                    <div class="analysis-text">{analysis}</div>
                </div>
                
                <!-- Charts Section -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">
                            <i class="fas fa-chart-line"></i>
                        </div>
                        <div class="card-title">Visualizações de Dados</div>
                    </div>
                    <div class="chart-grid">
                        <div class="chart-container">
                            <canvas id="pressureChart"></canvas>
                        </div>
                        <div class="chart-container">
                            <canvas id="temperatureChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- Data Table Section -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">
                            <i class="fas fa-table"></i>
                        </div>
                        <div class="card-title">Dados Detalhados</div>
                    </div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Veículo</th>
                                <th>Pressão</th>
                                <th>Temperatura</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>2025-01-15 10:30</td>
                                <td>ABC-1234</td>
                                <td>120 PSI</td>
                                <td>75°C</td>
                                <td><span class="alert alert-success">✅ Normal</span></td>
                            </tr>
                            <tr>
                                <td>2025-01-15 10:25</td>
                                <td>XYZ-5678</td>
                                <td>95 PSI</td>
                                <td>82°C</td>
                                <td><span class="alert alert-warning">⚠️ Alerta</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="sidebar">
                <!-- SQL Query -->
                {f'''
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">
                            <i class="fas fa-database"></i>
                        </div>
                        <div class="card-title">Consulta SQL</div>
                    </div>
                    <div class="sql-code">{sql_query}</div>
                </div>
                ''' if sql_query else ''}
                
                <!-- Alerts Section -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-icon">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                        <div class="card-title">Alertas & Insights</div>
                    </div>
                    <div class="alert alert-info">
                        <strong>💡 Insight:</strong> Pressão média dentro do ideal
                    </div>
                    <div class="alert alert-warning">
                        <strong>⚠️ Alerta:</strong> 2 veículos com pressão baixa
                    </div>
                    <div class="alert alert-success">
                        <strong>✅ Status:</strong> Sistema funcionando normalmente
                    </div>
                </div>
                
                <!-- Data Summary -->
                {data_summary}
            </div>
        </div>
        
        <!-- Map Section -->
        <div class="card">
            <div class="card-header">
                <div class="card-icon">
                    <i class="fas fa-map-marker-alt"></i>
                </div>
                <div class="card-title">Análise Geográfica</div>
            </div>
            <div class="map-container" id="map"></div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <div class="logo">Schulz Tech</div>
            <div>Powered by AI • Sistema de Monitoramento TPMS</div>
            <div class="timestamp">Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</div>
        </div>
    </div>
    
    <script>
        // Configuração global do Chart.js
        Chart.defaults.font.family = 'Poppins, sans-serif';
        Chart.defaults.color = '#2c3e50';
        
        // Gráfico de pressão
        const pressureCtx = document.getElementById('pressureChart').getContext('2d');
        new Chart(pressureCtx, {{
            type: 'line',
            data: {{
                labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'],
                datasets: [{{
                    label: 'Pressão (PSI)',
                    data: [120, 118, 122, 119, 121, 120],
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#3498db',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            font: {{
                                size: 14,
                                weight: '600'
                            }}
                        }}
                    }},
                    title: {{
                        display: true,
                        text: 'Pressão dos Pneus ao Longo do Dia',
                        font: {{
                            size: 16,
                            weight: '700'
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: false,
                        min: 100,
                        max: 140,
                        title: {{
                            display: true,
                            text: 'Pressão (PSI)',
                            font: {{
                                weight: '600'
                            }}
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Horário',
                            font: {{
                                weight: '600'
                            }}
                        }}
                    }}
                }},
                interaction: {{
                    intersect: false,
                    mode: 'index'
                }}
            }}
        }});
        
        // Gráfico de temperatura
        const tempCtx = document.getElementById('temperatureChart').getContext('2d');
        new Chart(tempCtx, {{
            type: 'bar',
            data: {{
                labels: ['Pneu 1', 'Pneu 2', 'Pneu 3', 'Pneu 4'],
                datasets: [{{
                    label: 'Temperatura (°C)',
                    data: [75, 82, 78, 80],
                    backgroundColor: [
                        'rgba(39, 174, 96, 0.8)',
                        'rgba(231, 76, 60, 0.8)',
                        'rgba(52, 152, 219, 0.8)',
                        'rgba(230, 126, 34, 0.8)'
                    ],
                    borderColor: [
                        '#27ae60',
                        '#e74c3c',
                        '#3498db',
                        '#e67e22'
                    ],
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            font: {{
                                size: 14,
                                weight: '600'
                            }}
                        }}
                    }},
                    title: {{
                        display: true,
                        text: 'Temperatura por Posição do Pneu',
                        font: {{
                            size: 16,
                            weight: '700'
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Temperatura (°C)',
                            font: {{
                                weight: '600'
                            }}
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Posição do Pneu',
                            font: {{
                                weight: '600'
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Mapa Google
        function initMap() {{
            const map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 12,
                center: {{ lat: -23.5505, lng: -46.6333 }}, // São Paulo
                mapId: 'DEMO_MAP_ID', // Necessário para AdvancedMarkerElement
                styles: [
                    {{
                        featureType: 'all',
                        elementType: 'geometry.fill',
                        stylers: [{{
                            color: '#f5f5f5'
                        }}]
                    }},
                    {{
                        featureType: 'water',
                        elementType: 'geometry',
                        stylers: [{{
                            color: '#c9c9c9'
                        }}]
                    }}
                ]
            }});
            
            // Adicionar marcadores de exemplo usando AdvancedMarkerElement
            const markers = [
                {{ lat: -23.5505, lng: -46.6333, title: 'Veículo ABC-1234', status: 'normal' }},
                {{ lat: -23.5515, lng: -46.6343, title: 'Veículo XYZ-5678', status: 'alerta' }},
                {{ lat: -23.5495, lng: -46.6323, title: 'Veículo DEF-9012', status: 'normal' }}
            ];
            
            markers.forEach(markerData => {{
                const marker = new google.maps.marker.AdvancedMarkerElement({{
                    position: markerData,
                    map: map,
                    title: markerData.title,
                    content: createMarkerContent(markerData)
                }});
            }});
        }}
        
        function createMarkerContent(markerData) {{
            const content = document.createElement('div');
            content.style.cssText = `
                background: ${{markerData.status === 'alerta' ? '#e74c3c' : '#27ae60'}};
                color: white;
                padding: 8px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                text-align: center;
                min-width: 80px;
            `;
            content.textContent = markerData.title;
            return content;
        }}
        
        // Animações de entrada
        document.addEventListener('DOMContentLoaded', function() {{
            const cards = document.querySelectorAll('.card');
            cards.forEach((card, index) => {{
                card.style.opacity = '0';
                card.style.transform = 'translateY(30px)';
                setTimeout(() => {{
                    card.style.transition = 'all 0.6s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }}, index * 100);
            }});
        }});
    </script>
</body>
</html>
        """

# Exemplo de uso
if __name__ == "__main__":
    agent = TireDataLLMAgent()
    
    # Exemplos de perguntas
    questions = [
        "Quantos dispositivos únicos temos no sistema?",
        "Qual é a pressão média registrada por placa?",
        "Quantos veículos cada cliente possui no banco de dados?",
        "Qual placa apresenta a maior variação de pressão nos pneus?",
        "Mostre estatísticas de pressão e temperatura por cliente"
    ]
    
    for question in questions:
        print("\n" + "="*80)
        result = agent.query(question)
        
        if "error" in result:
            print(f"❌ Erro: {result['error']}")
        else:
            print(f"✅ Pergunta: {result['question']}")
            print(f"📊 Registros encontrados: {result['data_count']}")
            print(f"\n🔍 Análise:\n{result['analysis']}")
