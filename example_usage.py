#!/usr/bin/env python3
"""
Exemplos de uso do Agente LLM para Dados de Pneus
Este arquivo demonstra como usar o sistema para diferentes tipos de análises.
"""

from llm_agent import TireDataLLMAgent
from statistical_analyzer import TireStatisticalAnalyzer
import json

def exemplo_consultas_basicas():
    """Exemplos de consultas básicas em linguagem natural."""
    print("=" * 60)
    print("EXEMPLOS DE CONSULTAS BÁSICAS")
    print("=" * 60)
    
    agent = TireDataLLMAgent()
    
    consultas_basicas = [
        "Quantos dispositivos únicos temos no sistema?",
        "Qual é a pressão média registrada?",
        "Qual é a temperatura média dos pneus?",
        "Quantas medições temos no total?"
    ]
    
    for consulta in consultas_basicas:
        print(f"\n🤖 Pergunta: {consulta}")
        try:
            resultado = agent.query(consulta)
            print(f"📊 Registros encontrados: {resultado['data_count']}")
            print(f"🔍 SQL gerado: {resultado['sql_query']}")
            print(f"💡 Análise: {resultado['analysis'][:200]}...")
        except Exception as e:
            print(f"❌ Erro: {e}")
        print("-" * 40)

def exemplo_analises_por_posicao():
    """Exemplos de análises específicas por posição de pneu."""
    print("\n" + "=" * 60)
    print("ANÁLISES POR POSIÇÃO DE PNEU")
    print("=" * 60)

    agent = TireDataLLMAgent()

    consultas_posicao = [
        "Mostre a pressão média por posição de pneu",
        "Qual posição de pneu tem a maior variação de temperatura?",
        "Compare a velocidade média por posição de pneu",
        "Lista de posições de pneu com pressão abaixo de 100 PSI"
    ]

    for consulta in consultas_posicao:
        print(f"\n📍 Pergunta: {consulta}")
        try:
            resultado = agent.query(consulta)
            print(f"📊 Registros: {resultado['data_count']}")
            print(f"💡 Insight: {resultado['analysis'][:150]}...")
        except Exception as e:
            print(f"❌ Erro: {e}")
        print("-" * 40)

def exemplo_analises_temporais():
    """Exemplos de análises temporais."""
    print("\n" + "=" * 60)
    print("ANÁLISES TEMPORAIS")
    print("=" * 60)
    
    agent = TireDataLLMAgent()
    
    consultas_temporais = [
        "Quantas medições foram registradas nos últimos 7 dias?",
        "Qual foi a pressão média dos pneus na última semana?",
        "Mostre a evolução diária das medições nos últimos 30 dias",
        "Qual dia teve a maior média de temperatura?",
        "Compare as medições de hoje com ontem"
    ]
    
    for consulta in consultas_temporais:
        print(f"\n📅 Pergunta: {consulta}")
        try:
            resultado = agent.query(consulta)
            print(f"📊 Registros: {resultado['data_count']}")
            print(f"💡 Tendência: {resultado['analysis'][:150]}...")
        except Exception as e:
            print(f"❌ Erro: {e}")
        print("-" * 40)

# Observação:
# A tabela ``tire_data_json_llm`` agora possui a coluna ``position``, que indica
# em qual pneu o sensor foi instalado (por exemplo, 1 para dianteiro esquerdo).
# Portanto, é possível realizar análises específicas por posição de pneu.
# Use a função ``exemplo_analises_por_posicao`` acima para ver exemplos de
# consultas e análises agrupadas por posição.

def exemplo_analises_estatisticas_avancadas():
    """Exemplos usando o módulo de análises estatísticas."""
    print("\n" + "=" * 60)
    print("ANÁLISES ESTATÍSTICAS AVANÇADAS")
    print("=" * 60)
    
    analyzer = TireStatisticalAnalyzer()
    
    print("📈 1. ESTATÍSTICAS GERAIS")
    try:
        stats = analyzer.get_vehicle_statistics()
        print(f"   Total de dispositivos: {stats.get('total_devices', stats.get('total_vehicles', 'N/A'))}")
        print(f"   Total de medições: {stats.get('total_measurements', 0):,}")
        print(f"   Período: {stats.get('first_measurement')} a {stats.get('last_measurement')}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    print("\n📊 2. TOP 10 DISPOSITIVOS POR MEDIÇÕES")
    try:
        pressure_stats = analyzer.get_pressure_statistics_by_vehicle(10)
        for _, row in pressure_stats.iterrows():
            device = row.get('device') or row.get('imei')
            print(f"   {device}: {row['measurements_count']:,} medições, "
                  f"pressão média {row['avg_pressure']:.1f} PSI")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    print("\n🏥 3. SCORE DE SAÚDE DOS DISPOSITIVOS")
    try:
        health_scores = analyzer.get_vehicle_health_score(10)
        for _, row in health_scores.iterrows():
            device = row.get('device') or row.get('imei')
            status = "🟢" if row['health_score'] >= 90 else "🟡" if row['health_score'] >= 70 else "🔴"
            print(f"   {status} {device}: Score {row['health_score']:.1f} "
                  f"({row.get('pressure_outliers', 0)} pressões fora do ideal)")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

def exemplo_consultas_complexas():
    """Exemplos de consultas mais complexas."""
    print("\n" + "=" * 60)
    print("CONSULTAS COMPLEXAS")
    print("=" * 60)
    
    agent = TireDataLLMAgent()
    
    consultas_complexas = [
        "Mostre dispositivos com pressão média acima de 130 PSI e mais de 1000 medições",
        "Identifique dispositivos com variação alta de pressão (alto desvio padrão)",
        "Compare a performance de dispositivos em diferentes regiões geográficas",
        "Qual é a relação entre temperatura média e velocidade média por dispositivo?",
        "Qual dispositivo percorreu a maior distância no período registrado?"
    ]
    
    for consulta in consultas_complexas:
        print(f"\n🧠 Pergunta: {consulta}")
        try:
            resultado = agent.query(consulta)
            print(f"📊 Registros: {resultado['data_count']}")
            print(f"🔍 SQL: {resultado['sql_query'][:100]}...")
            print(f"💡 Insight: {resultado['analysis'][:200]}...")
        except Exception as e:
            print(f"❌ Erro: {e}")
        print("-" * 40)

def exemplo_geracao_relatorio():
    """Exemplo de geração de relatório completo."""
    print("\n" + "=" * 60)
    print("GERAÇÃO DE RELATÓRIO COMPLETO")
    print("=" * 60)
    
    analyzer = TireStatisticalAnalyzer()
    
    try:
        print("📋 Gerando relatório abrangente...")
        relatorio = analyzer.generate_comprehensive_report()

        print("\n📊 RESUMO EXECUTIVO:")
        stats = relatorio['general_stats']
        print(f"• Total de dispositivos monitorados: {stats.get('total_devices', stats.get('total_vehicles', 'N/A'))}")
        print(f"• Volume de dados: {stats.get('total_measurements', 0):,} medições")
        print(f"• Período de análise: {stats.get('first_measurement')} a {stats.get('last_measurement')}")

        print("\n📈 MÉTRICAS POR DISPOSITIVO:")
        pressure_stats = relatorio['pressure_stats']
        print(f"• Dispositivos analisados: {len(pressure_stats)}")
        
        print("\n🏆 TOP DISPOSITIVOS (por pressão média):")
        top_pressure = pressure_stats.sort_values(by='avg_pressure', ascending=False).head(3)
        for _, row in top_pressure.iterrows():
            device = row.get('device') or row.get('imei')
            print(f"• {device}: pressão média {row['avg_pressure']:.1f} PSI")
        
        print("\n⚠️ DISPOSITIVOS COM MAIOR VARIAÇÃO DE TEMPERATURA:")
        temp_stats = relatorio['temperature_stats']
        top_temp = temp_stats.sort_values(by='temperature_stddev', ascending=False).head(3)
        for _, row in top_temp.iterrows():
            device = row.get('device') or row.get('imei')
            print(f"• {device}: desvio padrão {row['temperature_stddev']:.2f}")
        
        print("\n✅ Relatório gerado com sucesso!")
    except Exception as e:
        print(f"❌ Erro na geração do relatório: {e}")

def exemplo_visualizacoes():
    """Exemplo de geração de visualizações."""
    print("\n" + "=" * 60)
    print("GERAÇÃO DE VISUALIZAÇÕES")
    print("=" * 60)
    
    analyzer = TireStatisticalAnalyzer()
    
    visualizacoes = [
        ("pressure_by_device", "Pressão por Dispositivo"),
        ("tire_position_analysis", "Análise por Posição de Pneu"),
        ("health_score", "Score de Saúde")
    ]
    
    for viz_type, titulo in visualizacoes:
        try:
            print(f"📈 Gerando gráfico: {titulo}")
            plt = analyzer.create_visualization(viz_type, f"{viz_type}.png")
            print(f"✅ Gráfico salvo: {viz_type}.png")
        except Exception as e:
            print(f"❌ Erro ao gerar {titulo}: {e}")

def exemplo_monitoramento_tempo_real():
    """Exemplo de monitoramento em tempo real."""
    print("\n" + "=" * 60)
    print("SIMULAÇÃO DE MONITORAMENTO EM TEMPO REAL")
    print("=" * 60)
    
    agent = TireDataLLMAgent()
    
    # Consultas para monitoramento contínuo
    consultas_monitoramento = [
        "Quantas medições foram registradas na última hora?",
        "Quais dispositivos têm temperatura acima de 60°C agora?",
        "Há algum dispositivo com pressão crítica (abaixo de 80 PSI)?",
        "Quantos dispositivos estão ativos nas últimas 2 horas?"
    ]
    
    print("🔄 Executando verificações de monitoramento...")
    
    for i, consulta in enumerate(consultas_monitoramento, 1):
        try:
            print(f"\n{i}. {consulta}")
            resultado = agent.query(consulta)
            
            # Exibir contagem de registros e insight resumido
            print(f"   Dados: {resultado['data_count']} registros")
            print(f"   Insight: {resultado['analysis'][:100]}...")
            
        except Exception as e:
            print(f"❌ Erro na verificação {i}: {e}")

def main():
    """Executa todos os exemplos."""
    print("🚀 DEMONSTRAÇÃO DO AGENTE LLM PARA DADOS DE PNEUS")
    print("=" * 80)
    
    exemplos = [
        exemplo_consultas_basicas,
        exemplo_analises_por_posicao,
        exemplo_analises_temporais,
        exemplo_analises_estatisticas_avancadas,
        exemplo_consultas_complexas,
        exemplo_geracao_relatorio,
        exemplo_visualizacoes,
        exemplo_monitoramento_tempo_real
    ]
    
    for exemplo in exemplos:
        try:
            exemplo()
        except KeyboardInterrupt:
            print("\n\n⏹️ Execução interrompida pelo usuário.")
            break
        except Exception as e:
            print(f"\n❌ Erro no exemplo {exemplo.__name__}: {e}")
            continue
    
    print("\n" + "=" * 80)
    print("✅ DEMONSTRAÇÃO CONCLUÍDA")
    print("💡 Para usar o sistema, importe as classes e faça suas próprias consultas!")
    print("📚 Consulte o README.md e MANUAL_TECNICO.md para mais informações.")

if __name__ == "__main__":
    main()

