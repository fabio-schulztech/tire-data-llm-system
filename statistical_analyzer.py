import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

# Importar mapeamento de IMEI para placa (opcional).
# A tabela tire_data_json_llm agora contém as colunas ``placa`` e ``cliente``,
# portanto não é necessário mapear IMEIs para placas. O import a seguir
# permanece apenas para compatibilidade com versões antigas que possam
# referenciar este módulo, mas o dicionário não é utilizado.
try:
    from device_plate_mapping import DEVICE_TO_PLATE  # noqa: F401
except Exception:
    DEVICE_TO_PLATE = {}
import psycopg2
import warnings
warnings.filterwarnings('ignore')

# Biblioteca para efetuar chamadas HTTP ao endpoint externo de atualização de dados.
try:
    import requests
except ImportError:
    requests = None

class TireStatisticalAnalyzer:
    """
    Classe para análises estatísticas avançadas com base na tabela
    ``tire_data_json_llm``.

    Nesta versão do sistema, todas as consultas são realizadas sobre a
    tabela ``tire_data_json_llm``, que contém medições brutas do sistema
    TPMS: pressão, temperatura, velocidade, odômetro, indicador de
    movimento, localização GPS, identificação do dispositivo (``imei``),
    placa do veículo (``placa``), posição do pneu (``position``) e
    cliente ou empresa proprietária (``cliente``). A coluna ``position``
    identifica em qual pneu o sensor estava instalado (por exemplo, 1 para
    dianteiro esquerdo), permitindo análises específicas por posição.
    Não há campo de alerta. As análises e agrupamentos padrão podem ser
    feitos por dispositivo, placa, cliente ou posição de pneu conforme
    necessário.
    """
    
    def __init__(self, db_url="postgresql://fabioobaid:abo220993@34.125.196.215:5432/tire_data"):
        self.db_url = db_url

    # -------------------------------------------------------------------------
    #  Atualização de dados
    #
    #  Na versão que utiliza a tabela ``tire_data_json_llm`` como fonte única
    #  de dados, não há necessidade de executar chamadas externas para
    #  atualizar o banco com base em placas e posições de pneus. Este método
    #  permanece como um stub para compatibilidade com versões anteriores.
    # -------------------------------------------------------------------------
    def refresh_remote_data(self, sample_limit: int = 100):
        """Stub de atualização remota.

        A tabela ``tire_data_json_llm`` é populada automaticamente a partir
        do sistema TPMS. Como a coluna ``placa`` já está presente na
        tabela (bem como ``cliente``), não há necessidade de executar
        chamadas externas para mapear dispositivos para placas ou clientes.
        Esta função é mantida para compatibilidade com versões anteriores,
        mas não realiza nenhuma ação.

        Args:
            sample_limit (int): parâmetro ignorado na versão atual.
        """
        return
        
    def connect_db(self):
        """Conecta ao banco de dados PostgreSQL."""
        return psycopg2.connect(self.db_url)
    
    # Condição padrão para filtrar leituras inválidas
    FILTER_CONDITION = "pressure <= 180 AND pressure >= 0 AND temperature <= 150"

    def get_vehicle_statistics(self):
        """
        Retorna estatísticas gerais registradas na tabela ``tire_data_json_llm``.

        Esta função calcula métricas básicas sobre os dados presentes na
        tabela. Apesar de a tabela conter colunas de placa (``placa``) e
        cliente (``cliente``), as métricas padrão são calculadas por
        dispositivo (``imei``) para manter compatibilidade com versões
        anteriores. Os resultados incluem o número total de dispositivos,
        o número total de medições, o primeiro e o último timestamp
        registrado, além das médias de velocidade, pressão e temperatura.
        Também são contados quantos registros correspondem a veículos em
        movimento e quantos correspondem a veículos parados. As colunas
        ``placa`` e ``cliente`` podem ser utilizadas para filtragens ou
        análises adicionais em consultas SQL personalizadas.
        """
        # Query para obter estatísticas globais da tabela tire_data_json_llm
        query = f"""
        SELECT
            COUNT(DISTINCT imei) AS total_devices,
            COUNT(*) AS total_measurements,
            MIN(_timestamp_) AS first_measurement,
            MAX(_timestamp_) AS last_measurement,
            ROUND(AVG(speed)::numeric, 2) AS avg_speed,
            ROUND(AVG(pressure)::numeric, 2) AS avg_pressure,
            ROUND(AVG(temperature)::numeric, 2) AS avg_temperature,
            COUNT(CASE WHEN movimento = TRUE THEN 1 END) AS moving_count,
            COUNT(CASE WHEN movimento = FALSE THEN 1 END) AS stationary_count
        FROM tire_data_json_llm
        WHERE {self.FILTER_CONDITION}
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df.iloc[0].to_dict()
    
    def get_pressure_statistics_by_vehicle(self, limit=20):
        """
        Retorna estatísticas de pressão por dispositivo (IMEI).

        Agrupa as leituras da tabela ``tire_data_json_llm`` por
        ``imei`` e calcula o número de medições, média, mínimo,
        máximo e desvio padrão da pressão. O resultado é ordenado pelo
        número de medições em ordem decrescente e limitado pelo parâmetro
        ``limit``.
        """
        query = f"""
        SELECT 
            imei AS device,
            COUNT(*) AS measurements_count,
            ROUND(AVG(pressure)::numeric, 2) AS avg_pressure,
            ROUND(MIN(pressure)::numeric, 2) AS min_pressure,
            ROUND(MAX(pressure)::numeric, 2) AS max_pressure,
            ROUND(STDDEV(pressure)::numeric, 2) AS pressure_stddev
        FROM tire_data_json_llm
        WHERE {self.FILTER_CONDITION}
        GROUP BY imei
        ORDER BY measurements_count DESC
        LIMIT {limit}
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    
    def get_temperature_statistics_by_vehicle(self, limit=20):
        """
        Retorna estatísticas de temperatura por dispositivo (IMEI).

        Calcula, para cada ``imei``, o número de medições, a
        temperatura média, mínima, máxima e o desvio padrão das leituras de
        temperatura. Os resultados são ordenados pelo número de medições e
        limitados pelo parâmetro ``limit``.
        """
        query = f"""
        SELECT 
            imei AS device,
            COUNT(*) AS measurements_count,
            ROUND(AVG(temperature)::numeric, 2) AS avg_temperature,
            ROUND(MIN(temperature)::numeric, 2) AS min_temperature,
            ROUND(MAX(temperature)::numeric, 2) AS max_temperature,
            ROUND(STDDEV(temperature)::numeric, 2) AS temperature_stddev
        FROM tire_data_json_llm
        WHERE {self.FILTER_CONDITION}
        GROUP BY imei
        ORDER BY measurements_count DESC
        LIMIT {limit}
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    
    def get_tire_position_analysis(self):
        """
        Análise agregada por posição de pneu.

        Esta função agrupa as leituras da tabela ``tire_data_json_llm``
        pela coluna ``position``, que indica a posição do pneu em que o
        sensor está instalado. Para cada posição, calcula o número de
        medições, a pressão média, a temperatura média, a velocidade média,
        e as contagens de registros em movimento e parados. O resultado é
        ordenado pelo número de medições em ordem decrescente.

        Returns:
            pandas.DataFrame: DataFrame com as métricas agregadas por
            posição de pneu.
        """
        query = f"""
        SELECT
            position,
            COUNT(*) AS measurements_count,
            ROUND(AVG(pressure)::numeric, 2) AS avg_pressure,
            ROUND(AVG(temperature)::numeric, 2) AS avg_temperature,
            ROUND(AVG(speed)::numeric, 2) AS avg_speed,
            COUNT(CASE WHEN movimento = TRUE THEN 1 END) AS moving_count,
            COUNT(CASE WHEN movimento = FALSE THEN 1 END) AS stationary_count
        FROM tire_data_json_llm
        WHERE {self.FILTER_CONDITION}
        GROUP BY position
        ORDER BY measurements_count DESC
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    
    def get_alert_analysis(self):
        """
        Análise temporal agregada por dia.

        Como a nova tabela ``tire_data_json_llm`` não possui coluna de alerta,
        esta função retorna uma análise temporal das leituras. Agrupa os dados
        por dia (``DATE_TRUNC('day', _timestamp_)``) e calcula o número de
        medições, dispositivos distintos, médias de velocidade, pressão e
        temperatura, além de contagens de veículos em movimento e parados.
        Por padrão analisa os últimos 30 dias, mas pode ser customizada
        via parâmetro ``days`` em ``get_temporal_analysis``.
        """
        # Delegar para a função get_temporal_analysis com 30 dias
        return self.get_temporal_analysis(days=30)
    
    def get_temporal_analysis(self, days=30):
        """
        Análise temporal dos últimos ``days`` dias.

        Agrupa as leituras por dia com base no campo ``_timestamp_`` e
        calcula métricas agregadas: número de medições, dispositivos
        distintos, médias de velocidade, pressão e temperatura, bem como
        contagem de registros em movimento e parados. Este método usa a
        tabela ``tire_data_json_llm`` e não depende de colunas de alerta.

        Args:
            days (int): número de dias a considerar a partir da data atual.

        Returns:
            pandas.DataFrame: DataFrame contendo uma linha por dia com as
            métricas calculadas.
        """
        query = f"""
        SELECT 
            DATE_TRUNC('day', _timestamp_) AS date,
            COUNT(*) AS daily_measurements,
            COUNT(DISTINCT imei) AS active_devices,
            ROUND(AVG(speed)::numeric, 2) AS avg_speed,
            ROUND(AVG(pressure)::numeric, 2) AS avg_pressure,
            ROUND(AVG(temperature)::numeric, 2) AS avg_temperature,
            COUNT(CASE WHEN movimento = TRUE THEN 1 END) AS moving_count,
            COUNT(CASE WHEN movimento = FALSE THEN 1 END) AS stationary_count
        FROM tire_data_json_llm
        WHERE _timestamp_ >= NOW() - INTERVAL '{days} days'
          AND {self.FILTER_CONDITION}
        GROUP BY DATE_TRUNC('day', _timestamp_)
        ORDER BY date DESC
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    
    def get_vehicle_health_score(self, limit=20):
        """
        Calcula um score de saúde para cada dispositivo (IMEI).

        O score de saúde é uma métrica composta que penaliza variações
        acentuadas de pressão e temperatura, bem como leituras extremas
        (pressão fora do intervalo 80–150 PSI e temperatura acima de 80 °C).
        Cada penalidade possui um peso diferente no cálculo final. Apenas
        dispositivos com mais de 100 medições são considerados para evitar
        vieses de poucos dados.

        Args:
            limit (int): número máximo de dispositivos a retornar ordenados
                         pelo score (descendente).

        Returns:
            pandas.DataFrame: DataFrame com colunas ``device``,
            ``health_score`` e métricas intermediárias.
        """
        query = f"""
        WITH device_stats AS (
            SELECT
                imei AS device,
                COUNT(*) AS total_measurements,
                AVG(pressure) AS avg_pressure,
                STDDEV(pressure) AS pressure_variation,
                AVG(temperature) AS avg_temperature,
                STDDEV(temperature) AS temperature_variation,
                AVG(speed) AS avg_speed,
                -- Contar pressões fora do intervalo aceitável (abaixo de 96 ou acima de 150)
                COUNT(CASE WHEN pressure < 96 OR pressure > 150 THEN 1 END) AS pressure_outliers,
                -- Contar temperaturas elevadas (acima de 80 °C)
                COUNT(CASE WHEN temperature > 80 THEN 1 END) AS high_temp_count,
                COUNT(CASE WHEN movimento = TRUE THEN 1 END) AS moving_count,
                COUNT(CASE WHEN movimento = FALSE THEN 1 END) AS stationary_count
            FROM tire_data_json_llm
            WHERE {self.FILTER_CONDITION}
            GROUP BY imei
        )
        SELECT
            device,
            total_measurements,
            ROUND(avg_pressure::numeric, 2) AS avg_pressure,
            ROUND(pressure_variation::numeric, 2) AS pressure_variation,
            ROUND(avg_temperature::numeric, 2) AS avg_temperature,
            ROUND(temperature_variation::numeric, 2) AS temperature_variation,
            ROUND(avg_speed::numeric, 2) AS avg_speed,
            pressure_outliers,
            high_temp_count,
            moving_count,
            stationary_count,
            ROUND((
                100
                - (pressure_outliers * 100.0 / NULLIF(total_measurements, 0)) * 0.4
                - (high_temp_count * 100.0 / NULLIF(total_measurements, 0)) * 0.3
                - LEAST(COALESCE(pressure_variation, 0) / 10, 10) * 0.2
                - LEAST(COALESCE(temperature_variation, 0) / 10, 10) * 0.1
            )::numeric, 2) AS health_score
        FROM device_stats
        WHERE total_measurements > 100
        ORDER BY health_score DESC
        LIMIT {limit}
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    
    def get_geographic_analysis(self):
        """
        Análise geográfica dos dados (quando coordenadas estão disponíveis).

        Agrupa os registros da tabela ``tire_data_json_llm`` por latitude e
        longitude arredondadas (4 casas decimais) para identificar pontos de
        concentração de medições. Calcula o número de leituras, número de
        dispositivos distintos, médias de pressão e temperatura e contagens
        de registros em movimento e parados. Filtra locais com mais de 50
        registros para evitar pontos esparsos.
        """
        query = f"""
        SELECT
            ROUND(latitude::numeric, 4) AS lat_rounded,
            ROUND(longtitude::numeric, 4) AS lng_rounded,
            COUNT(*) AS measurements_count,
            COUNT(DISTINCT imei) AS devices_count,
            ROUND(AVG(pressure)::numeric, 2) AS avg_pressure,
            ROUND(AVG(temperature)::numeric, 2) AS avg_temperature,
            COUNT(CASE WHEN movimento = TRUE THEN 1 END) AS moving_count,
            COUNT(CASE WHEN movimento = FALSE THEN 1 END) AS stationary_count
        FROM tire_data_json_llm
        WHERE latitude IS NOT NULL AND longtitude IS NOT NULL
          AND {self.FILTER_CONDITION}
        GROUP BY ROUND(latitude::numeric, 4), ROUND(longtitude::numeric, 4)
        HAVING COUNT(*) > 50
        ORDER BY measurements_count DESC
        LIMIT 50
        """
        conn = self.connect_db()
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    # ---------------------------------------------------------------------
    #  Consulta de dados brutos por placa na tabela tire_data_json_llm
    #
    #  A tabela tire_data_json_llm armazena leituras brutas do sistema TPMS
    #  e agora inclui as colunas ``placa`` e ``cliente``. Esta função
    #  permite recuperar diretamente todas as leituras associadas a uma
    #  determinada placa, sem necessidade de mapeamento de IMEI.
    # ---------------------------------------------------------------------
    def get_tire_data_json_by_plate(self, plate: str, limit: int = 1000):
        """
        Recupera dados da tabela ``tire_data_json_llm`` para uma determinada
        placa de veículo.

        A função realiza uma consulta direta na tabela utilizando a coluna
        ``placa``. A comparação de placas é feita de forma case-insensitive.
        Se a placa fornecida estiver vazia, a função retornará um
        DataFrame vazio.

        Args:
            plate (str): A placa do veículo (não diferencia maiúsculas/minúsculas).
            limit (int): Número máximo de registros a serem retornados (padrão 1000).

        Returns:
            pandas.DataFrame: DataFrame contendo os registros da tabela
            ``tire_data_json_llm`` correspondentes à placa.
        """
        # Normalizar placa para comparação sem diferenças de caixa
        if not plate:
            return pd.DataFrame()
        normalized_plate = plate.strip().lower()

        # Construir consulta parametrizada para filtrar por placa (case-insensitive)
        # Também aplicamos o filtro padrão para ignorar valores inválidos de pressão
        # e temperatura (ver ``FILTER_CONDITION``).
        query = f"""
        SELECT *
        FROM tire_data_json_llm
        WHERE LOWER(placa) = %s
          AND {self.FILTER_CONDITION}
        ORDER BY _timestamp_ DESC
        LIMIT %s
        """
        conn = self.connect_db()
        try:
            df = pd.read_sql(query, conn, params=[normalized_plate, limit])
        finally:
            conn.close()
        return df
    
    def create_visualization(self, data_type="pressure_by_vehicle", save_path=None):
        """
        Cria visualizações dos dados estatísticos.
        """
        plt.style.use('default')
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10
        
        # -----------------------
        # Visualização de pressão por dispositivo
        # -----------------------
        if data_type in ("pressure_by_vehicle", "pressure_by_device"):
            df = self.get_pressure_statistics_by_vehicle(15)
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
            # Gráfico de pressão média
            ax1.bar(range(len(df)), df['avg_pressure'], color='skyblue', alpha=0.7)
            ax1.set_xlabel('Dispositivos (IMEI)')
            ax1.set_ylabel('Pressão Média (PSI)')
            ax1.set_title('Pressão Média por Dispositivo')
            ax1.set_xticks(range(len(df)))
            ax1.set_xticklabels(df['device'], rotation=45, ha='right')
            # Gráfico de variação (desvio padrão)
            ax2.bar(range(len(df)), df['pressure_stddev'], color='lightcoral', alpha=0.7)
            ax2.set_xlabel('Dispositivos (IMEI)')
            ax2.set_ylabel('Desvio Padrão da Pressão')
            ax2.set_title('Variação da Pressão por Dispositivo')
            ax2.set_xticks(range(len(df)))
            ax2.set_xticklabels(df['device'], rotation=45, ha='right')
            plt.tight_layout()

        # -----------------------
        # Análise agregada por dispositivo
        # -----------------------
        elif data_type in ("tire_position_analysis", "device_analysis"):
            # Análise por posição de pneu
            df = self.get_tire_position_analysis()
            # Limitar a 15 posições para visualização
            df = df.head(15)
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            # Pressão média por posição
            ax1.bar(df['position'], df['avg_pressure'], color='lightblue')
            ax1.set_xlabel('Posição do Pneu')
            ax1.set_ylabel('Pressão Média (PSI)')
            ax1.set_title('Pressão Média por Posição de Pneu')
            ax1.tick_params(axis='x', rotation=45)
            # Temperatura média por posição
            ax2.bar(df['position'], df['avg_temperature'], color='orange')
            ax2.set_xlabel('Posição do Pneu')
            ax2.set_ylabel('Temperatura Média (°C)')
            ax2.set_title('Temperatura Média por Posição de Pneu')
            ax2.tick_params(axis='x', rotation=45)
            # Velocidade média por posição
            ax3.bar(df['position'], df['avg_speed'], color='lightgreen')
            ax3.set_xlabel('Posição do Pneu')
            ax3.set_ylabel('Velocidade Média (km/h)')
            ax3.set_title('Velocidade Média por Posição de Pneu')
            ax3.tick_params(axis='x', rotation=45)
            # Proporção de movimento vs parada por posição
            move_pct = df['moving_count'] / (df['moving_count'] + df['stationary_count']).replace(0, np.nan)
            ax4.bar(df['position'], move_pct * 100, color='purple')
            ax4.set_xlabel('Posição do Pneu')
            ax4.set_ylabel('% em Movimento')
            ax4.set_title('Percentual de Leituras em Movimento por Posição de Pneu')
            ax4.tick_params(axis='x', rotation=45)
            plt.tight_layout()
            
        elif data_type == "health_score":
            df = self.get_vehicle_health_score(15)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            # Cores baseadas no score
            colors = ['green' if score >= 80 else 'orange' if score >= 60 else 'red' 
                     for score in df['health_score']]
            # Score de saúde
            ax1.barh(range(len(df)), df['health_score'], color=colors, alpha=0.7)
            ax1.set_xlabel('Score de Saúde (0-100)')
            ax1.set_ylabel('Dispositivos (IMEI)')
            ax1.set_title('Score de Saúde por Dispositivo')
            ax1.set_yticks(range(len(df)))
            ax1.set_yticklabels(df['device'])
            ax1.axvline(x=80, color='green', linestyle='--', alpha=0.5, label='Bom (80+)')
            ax1.axvline(x=60, color='orange', linestyle='--', alpha=0.5, label='Regular (60-80)')
            ax1.legend()
            # Relação entre pressão fora do ideal e score
            ax2.scatter(df['pressure_outliers'], df['health_score'], alpha=0.7, s=60)
            ax2.set_xlabel('Nº de Pressões Fora do Ideal')
            ax2.set_ylabel('Score de Saúde')
            ax2.set_title('Pressões Fora do Ideal vs Score de Saúde')
            plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Gráfico salvo em: {save_path}")
        
        return plt
    
    def generate_comprehensive_report(self):
        """
        Gera um relatório estatístico abrangente.
        """
        report = {
            "general_stats": self.get_vehicle_statistics(),
            "pressure_stats": self.get_pressure_statistics_by_vehicle(),
            "temperature_stats": self.get_temperature_statistics_by_vehicle(),
            "tire_position_analysis": self.get_tire_position_analysis(),
            "alert_analysis": self.get_alert_analysis(),
            "temporal_analysis": self.get_temporal_analysis(),
            "health_scores": self.get_vehicle_health_score(),
            "geographic_analysis": self.get_geographic_analysis()
        }
        
        return report

# Exemplo de uso
if __name__ == "__main__":
    analyzer = TireStatisticalAnalyzer()
    
    print("=== RELATÓRIO ESTATÍSTICO COMPLETO ===\n")
    
    # Estatísticas gerais
    general = analyzer.get_vehicle_statistics()
    print("ESTATÍSTICAS GERAIS:")
    print(f"- Total de dispositivos: {general['total_devices']}")
    print(f"- Total de medições: {general['total_measurements']:,}")
    print(f"- Primeira medição: {general['first_measurement']}")
    print(f"- Última medição: {general['last_measurement']}")
    print(f"- Velocidade média: {general['avg_speed']} km/h")
    print(f"- Pressão média: {general['avg_pressure']} PSI")
    print(f"- Temperatura média: {general['avg_temperature']} °C")
    print(f"- Leituras em movimento: {general['moving_count']}")
    print(f"- Leituras paradas: {general['stationary_count']}")
    
    print("\n" + "="*50)
    
    # Top 10 dispositivos por número de medições
    pressure_stats = analyzer.get_pressure_statistics_by_vehicle(10)
    print("\nTOP 10 DISPOSITIVOS (por número de medições):")
    print(pressure_stats.to_string(index=False))
    print("\n" + "="*50)
    # Análise agregada por dispositivo
    device_analysis = analyzer.get_tire_position_analysis()
    print("\nANÁLISE AGREGADA POR DISPOSITIVO:")
    print(device_analysis.to_string(index=False))
    print("\n" + "="*50)
    # Score de saúde dos dispositivos
    health_scores = analyzer.get_vehicle_health_score(10)
    print("\nSCORE DE SAÚDE DOS DISPOSITIVOS (Top 10):")
    print(health_scores[['device', 'health_score', 'pressure_outliers', 'high_temp_count', 'total_measurements']].to_string(index=False))

