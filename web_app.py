#!/usr/bin/env python3
"""
Interface Web para Agente LLM de Análise de Pneus
Schulz Tech - Sistema de Monitoramento TPMS
Produção: https://api.schulztech.com.br
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, date, time, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv( )

# Adicionar o diretório atual ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar módulos do agente LLM
from llm_agent import TireDataLLMAgent
from statistical_analyzer import TireStatisticalAnalyzer

# Definir o caminho base do projeto para arquivos estáticos e templates
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            static_folder=os.path.join(PROJECT_ROOT, 'static'),
            template_folder=os.path.join(PROJECT_ROOT, 'templates'))

# Configurar CORS para permitir acesso do domínio HTTPS
CORS(app, origins=[
    "https://api.schulztech.com.br/",
    "http://localhost:*",
    "http://127.0.0.1:*",
    "http://34.125.196.215:*"
] )

# Configurações
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'schulz-tech-llm-agent-2025')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

# Configurações para produção HTTPS
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SERVER_NAME'] = None  # Permitir qualquer host

def convert_to_serializable(data ):
    """Converte DataFrames e outros tipos não serializáveis para JSON"""
    if isinstance(data, pd.DataFrame):
        return data.to_dict('records')
    elif isinstance(data, dict):
        return {k: convert_to_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_serializable(item) for item in data]
    elif isinstance(data, (datetime, date, time)):
        return data.isoformat()
    elif isinstance(data, timedelta):
        # retornar segundos para facilitar cálculos no frontend
        return data.total_seconds()
    elif pd.isna(data):
        return None
    else:
        return data

# Instanciar o agente LLM e analisador estatístico
try:
    llm_agent = TireDataLLMAgent()
    stats_analyzer = TireStatisticalAnalyzer()
    print("✅ Agente LLM e Analisador Estatístico inicializados com sucesso")
except Exception as e:
    print(f"❌ Erro ao inicializar componentes: {e}")
    llm_agent = None
    stats_analyzer = None

# Middleware para logs de produção
@app.before_request
def log_request_info():
    """Log informações da requisição para monitoramento"""
    if app.config['DEBUG']:
        print(f"🌐 {request.method} {request.url} - {request.remote_addr}")

@app.after_request
def after_request(response):
    """Adicionar headers de segurança para produção HTTPS"""
    # Headers de segurança
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # CORS headers para HTTPS
    if request.origin and 'schulztech.com.br' in request.origin:
        response.headers['Access-Control-Allow-Origin'] = request.origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    return response

@app.route('/')
def index():
    """Página principal da interface web"""
    return render_template('index_inline_fixed.html')

@app.route('/health')
def health_check():
    """Endpoint de health check para monitoramento"""
    return jsonify({
        'status': 'healthy',
        'service': 'Schulz Tech LLM Agent',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'llm_agent': 'online' if llm_agent else 'offline',
            'stats_analyzer': 'online' if stats_analyzer else 'offline'
        }
    })

@app.route('/api/query', methods=['POST'])
def api_query():
    """Endpoint para processar consultas em linguagem natural"""
    try:
        if not llm_agent:
            return jsonify({
                'success': False,
                'error': 'Agente LLM não está disponível'
            }), 500
        
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query não fornecida'
            }), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query vazia'
            }), 400
        
        # Processar a consulta com o agente LLM
        result = llm_agent.query(query)

        # Normalizar campos esperados pelo frontend
        sql_text = result.get('sql') or result.get('sql_query') or ''
        effective_sql_text = result.get('effective_sql') or ''
        analysis_text = result.get('analysis', '')

        # Dados podem vir como tuplas + 'columns' ou já como lista de dicts
        rows = result.get('data') or result.get('raw_data') or []
        columns = result.get('columns') or []

        data_records = rows
        if rows and columns and isinstance(rows[0], (list, tuple)):
            try:
                data_records = [ { columns[i]: row[i] for i in range(min(len(columns), len(row))) } for row in rows ]
            except Exception:
                # fallback para manter estrutura original
                data_records = rows

        record_count = result.get('record_count') or result.get('data_count') or (len(data_records) if isinstance(data_records, list) else 0)

        return jsonify({
            'success': True,
            'query': query,
            'sql': sql_text,
            'effective_sql': effective_sql_text,
            'analysis': analysis_text,
            'data': convert_to_serializable(data_records),
            'record_count': int(record_count) if record_count is not None else 0,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/query: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao processar consulta: {str(e)}'
        }), 500

@app.route('/api/generate-html', methods=['POST'])
def api_generate_html():
    """Gera HTML único com identidade visual Schulz Tech a partir da pergunta e análise."""
    try:
        if not llm_agent:
            return jsonify({ 'success': False, 'error': 'Agente LLM não está disponível' }), 500

        payload = request.get_json() or {}
        question = payload.get('question', '').strip()
        analysis = payload.get('analysis', '').strip()

        if not question or not analysis:
            return jsonify({ 'success': False, 'error': 'Parâmetros insuficientes: envie question e analysis' }), 400

        html = llm_agent.generate_branded_html(question, analysis)

        return jsonify({
            'success': True,
            'html': html,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ Erro no /api/generate-html: {str(e)}")
        return jsonify({ 'success': False, 'error': f'Erro ao gerar HTML: {str(e)}' }), 500

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Endpoint para obter estatísticas gerais do sistema"""
    try:
        if not stats_analyzer:
            return jsonify({
                'success': False,
                'error': 'Analisador estatístico não está disponível'
            }), 500
        
        # Obter estatísticas gerais
        stats = stats_analyzer.get_vehicle_statistics()
        
        return jsonify({
            'success': True,
            'stats': convert_to_serializable(stats),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao obter estatísticas: {str(e)}'
        }), 500

@app.route('/api/health-score', methods=['GET'])
def api_health_score():
    """Endpoint para obter score de saúde dos veículos"""
    try:
        if not stats_analyzer:
            return jsonify({
                'success': False,
                'error': 'Analisador estatístico não está disponível'
            }), 500
        
        # Obter score de saúde
        health_scores = stats_analyzer.get_vehicle_health_score(limit=50)
        
        return jsonify({
            'success': True,
            'health_scores': convert_to_serializable(health_scores),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/health-score: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao calcular health score: {str(e)}'
        }), 500

@app.route('/api/tire-analysis', methods=['GET'])
def api_tire_analysis():
    """Endpoint para análise por posição de pneu"""
    try:
        if not stats_analyzer:
            return jsonify({
                'success': False,
                'error': 'Analisador estatístico não está disponível'
            }), 500
        
        # Obter análise por posição de pneu
        tire_analysis = stats_analyzer.get_tire_position_analysis()
        
        return jsonify({
            'success': True,
            'tire_analysis': convert_to_serializable(tire_analysis),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/tire-analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao analisar pneus: {str(e)}'
        }), 500

@app.route('/api/alerts', methods=['GET'])
def api_alerts():
    """Endpoint para análise de alertas"""
    try:
        if not stats_analyzer:
            return jsonify({
                'success': False,
                'error': 'Analisador estatístico não está disponível'
            }), 500
        
        # Obter análise de alertas
        alerts_analysis = stats_analyzer.get_alert_analysis()
        
        return jsonify({
            'success': True,
            'alerts': convert_to_serializable(alerts_analysis),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/alerts: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao analisar alertas: {str(e)}'
        }), 500

@app.route('/api/system-info', methods=['GET'])
def api_system_info():
    """Endpoint para informações do sistema"""
    try:
        system_info = {
            'agent_status': 'online' if llm_agent else 'offline',
            'stats_analyzer_status': 'online' if stats_analyzer else 'offline',
            'result_limit': os.getenv('RESULT_LIMIT', '50000'),
            'max_query_timeout': os.getenv('MAX_QUERY_TIMEOUT', '30'),
            'cache_size': os.getenv('CACHE_SIZE', '100'),
            'version': '1.0.0',
            'environment': 'production',
            'domain': 'https://api.schulztech.com.br',
            'timestamp': datetime.now( ).isoformat()
        }
        
        return jsonify({
            'success': True,
            'system_info': system_info
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/system-info: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao obter informações do sistema: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'available_endpoints': [
            '/health',
            '/api/query',       # <--- CORRIGIDO
            '/api/stats',       # <--- CORRIGIDO
            '/api/health-score',
            '/api/tire-analysis',
            '/api/alerts',
            '/api/system-info'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor'
    }), 500

if __name__ == '__main__':
    print("🚀 Iniciando Interface Web do Agente LLM...")
    print(f"🌐 Domínio de Produção: https://api.schulztech.com.br" )
    print(f"📊 RESULT_LIMIT: {os.getenv('RESULT_LIMIT', '50000')}")
    print(f"⏱️  MAX_QUERY_TIMEOUT: {os.getenv('MAX_QUERY_TIMEOUT', '30')}s")
    print(f"🔧 DEBUG: {app.config['DEBUG']}")
    
    # Executar aplicação
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 7719)),
        debug=app.config['DEBUG']
    )
