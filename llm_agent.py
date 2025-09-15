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
Você é um especialista em desenvolvimento web, design e visualização de dados. Crie uma página HTML completa e elegante para exibir uma análise de dados de um sistema TPMS (Tire Pressure Monitoring System) com visualizações interativas.

INFORMAÇÕES PARA EXIBIR:
- Pergunta: {question}
- Análise: {analysis}
- Consulta SQL: {sql_query or 'Não disponível'}
{data_summary}

CHAVE DA API GOOGLE MAPS: {google_maps_key}

REQUISITOS OBRIGATÓRIOS:
1. **Design Schulz Tech**: Use cores corporativas azul (#2c3e50, #3498db) e cinza (#7f8c8d, #95a5a6)
2. **Layout em Cards**: Organize o conteúdo em cards elegantes com sombras e bordas arredondadas
3. **Efeitos Visuais**: Use gradientes, animações CSS, hover effects e transições suaves
4. **Gráficos Interativos**: Inclua gráficos usando Chart.js v4.4.0 para:
   - Pressão vs Tempo (se houver dados temporais)
   - Temperatura vs Tempo (se houver dados temporais)
   - Distribuição de pressões por veículo
   - Gráficos de barras para estatísticas
5. **Mapa Google**: Integre Google Maps com a chave fornecida para mostrar localizações dos veículos
6. **Responsivo**: Layout adaptável para mobile e desktop
7. **Tipografia**: Use fontes modernas (Inter, Roboto, ou similar)
8. **Ícones**: Use Font Awesome ou emojis para elementos visuais

ESTRUTURA OBRIGATÓRIA:
- Header com logo Schulz Tech e gradiente
- Card da pergunta com destaque visual
- Card da consulta SQL (se disponível)
- Card da análise com formatação rica
- Card de gráficos com Chart.js
- Card do mapa Google (se houver coordenadas)
- Card de estatísticas resumidas
- Footer corporativo

TECNOLOGIAS A USAR:
- Chart.js v4.4.0 para gráficos (use CDN: https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js)
- Google Maps API com a chave fornecida
- CSS Grid/Flexbox para layout
- Animações CSS para efeitos
- Font Awesome para ícones

IMPORTANTE:
- Use a chave da API do Google Maps fornecida: {google_maps_key}
- Use Chart.js v4.4.0 para evitar problemas de compatibilidade
- Adicione loading=async no script do Google Maps
- Use google.maps.marker.AdvancedMarkerElement em vez de google.maps.Marker (mais moderno)

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
        """Gera HTML de fallback elegante com gráficos e mapas"""
        # Obter chave da API do Google Maps do ambiente
        google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY', 'YOUR_API_KEY')
        
        return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Dados TPMS - Schulz Tech</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js"></script>
    <script src="https://maps.googleapis.com/maps/api/js?key={google_maps_key}&callback=initMap&loading=async" async defer></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="75" cy="75" r="1" fill="rgba(255,255,255,0.1)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
            opacity: 0.1;
        }}
        
        .header h1 {{
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 10px;
            position: relative;
            z-index: 1;
        }}
        
        .header .subtitle {{
            font-size: 1.2rem;
            opacity: 0.9;
            position: relative;
            z-index: 1;
        }}
        
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            border: 1px solid rgba(52, 152, 219, 0.1);
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
        }}
        
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #ecf0f1;
        }}
        
        .card-icon {{
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            color: white;
            font-size: 1.5rem;
        }}
        
        .card-title {{
            font-size: 1.5rem;
            font-weight: 600;
            color: #2c3e50;
        }}
        
        .question-card {{
            grid-column: 1 / -1;
        }}
        
        .question-text {{
            font-size: 1.1rem;
            line-height: 1.6;
            color: #555;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            border-left: 4px solid #3498db;
        }}
        
        .analysis-text {{
            font-size: 1rem;
            line-height: 1.8;
            color: #444;
            white-space: pre-wrap;
        }}
        
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
        }}
        
        .map-container {{
            height: 400px;
            border-radius: 12px;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 12px;
            border: 1px solid #dee2e6;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #3498db;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            font-size: 0.9rem;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .footer {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            text-align: center;
            padding: 30px;
            border-radius: 20px;
            margin-top: 30px;
        }}
        
        .footer .logo {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        
        .footer .timestamp {{
            opacity: 0.8;
            font-size: 0.9rem;
        }}
        
        .sql-code {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 12px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            overflow-x: auto;
            margin: 15px 0;
        }}
        
        @media (max-width: 768px) {{
            .cards-grid {{
                grid-template-columns: 1fr;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            .card {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-tire"></i> Análise de Dados TPMS</h1>
            <div class="subtitle">Sistema Inteligente de Monitoramento de Pneus - Schulz Tech</div>
        </div>
        
        <div class="cards-grid">
            <div class="card question-card">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-question-circle"></i>
                    </div>
                    <div class="card-title">Pergunta</div>
                </div>
                <div class="question-text">{question}</div>
            </div>
            
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
            
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="card-title">Análise Inteligente</div>
                </div>
                <div class="analysis-text">{analysis}</div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-chart-bar"></i>
                    </div>
                    <div class="card-title">Gráficos de Dados</div>
                </div>
                <div class="chart-container">
                    <canvas id="pressureChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-map-marker-alt"></i>
                    </div>
                    <div class="card-title">Localização dos Veículos</div>
                </div>
                <div class="map-container" id="map"></div>
            </div>
        </div>
        
        <div class="footer">
            <div class="logo">Schulz Tech</div>
            <div>Powered by AI • Sistema de Monitoramento TPMS</div>
            <div class="timestamp">Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</div>
        </div>
    </div>
    
    <script>
        // Gráfico de pressão
        const ctx = document.getElementById('pressureChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
                datasets: [{{
                    label: 'Pressão Média (PSI)',
                    data: [120, 118, 122, 119, 121, 120],
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    tension: 0.4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: false,
                        min: 100,
                        max: 140
                    }}
                }}
            }}
        }});
        
        // Mapa Google
        function initMap() {{
            const map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 10,
                center: {{ lat: -23.5505, lng: -46.6333 }}, // São Paulo
                mapId: 'DEMO_MAP_ID' // Necessário para AdvancedMarkerElement
            }});
            
            // Adicionar marcadores de exemplo usando AdvancedMarkerElement
            const markers = [
                {{ lat: -23.5505, lng: -46.6333, title: 'Veículo 1' }},
                {{ lat: -23.5515, lng: -46.6343, title: 'Veículo 2' }},
                {{ lat: -23.5495, lng: -46.6323, title: 'Veículo 3' }}
            ];
            
            markers.forEach(markerData => {{
                const marker = new google.maps.marker.AdvancedMarkerElement({{
                    position: markerData,
                    map: map,
                    title: markerData.title
                }});
            }});
        }}
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
