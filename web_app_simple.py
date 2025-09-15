#!/usr/bin/env python3
"""
Aplicação Flask simplificada para teste do sistema TPMS com IA
"""

import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
import json

# Importar apenas o agente LLM
from llm_agent import TireDataLLMAgent

app = Flask(__name__)
CORS(app)

# Inicializar agente LLM
print("🤖 Inicializando Agente LLM...")
try:
    llm_agent = TireDataLLMAgent()
    print("✅ Agente LLM inicializado com sucesso")
except Exception as e:
    print(f"❌ Erro ao inicializar Agente LLM: {e}")
    llm_agent = None

@app.route('/')
def index():
    """Página principal"""
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sistema TPMS com IA - Teste</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; text-align: center; }
            .form-group { margin: 20px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #2980b9; }
            .result { margin-top: 20px; padding: 15px; background: #ecf0f1; border-radius: 5px; }
            .error { background: #e74c3c; color: white; }
            .success { background: #27ae60; color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Sistema TPMS com IA - Teste</h1>
            <p>Sistema inteligente de monitoramento de pneus com integração ChatGPT</p>
            
            <div class="form-group">
                <label for="query">Faça sua pergunta sobre os dados de pneus:</label>
                <input type="text" id="query" placeholder="Ex: Quantos veículos temos no sistema?" />
            </div>
            
            <button onclick="askQuestion()">Perguntar</button>
            <button onclick="generateHTML()" style="background: #27ae60; margin-left: 10px;">Gerar Relatório HTML</button>
            
            <div id="result" class="result" style="display: none;"></div>
            <div id="htmlResult" class="result" style="display: none;"></div>
        </div>

        <script>
            async function askQuestion() {
                const query = document.getElementById('query').value;
                const resultDiv = document.getElementById('result');
                
                if (!query.trim()) {
                    alert('Por favor, digite uma pergunta');
                    return;
                }
                
                resultDiv.style.display = 'block';
                resultDiv.className = 'result';
                resultDiv.innerHTML = '🤔 Processando pergunta...';
                
                try {
                    const response = await fetch('/api/query', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ query: query })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `
                            <h3>✅ Resposta:</h3>
                            <p><strong>Pergunta:</strong> ${data.query}</p>
                            <p><strong>SQL Gerado:</strong></p>
                            <pre style="background: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 5px; overflow-x: auto;">${data.sql}</pre>
                            <p><strong>Registros encontrados:</strong> ${data.record_count}</p>
                            <p><strong>Análise:</strong></p>
                            <div style="white-space: pre-wrap; background: #34495e; color: #ecf0f1; padding: 15px; border-radius: 5px;">${data.analysis}</div>
                        `;
                        
                        // Armazenar dados para geração de HTML
                        window.lastQueryData = data;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `❌ Erro: ${data.error}`;
                    }
                } catch (error) {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `❌ Erro de conexão: ${error.message}`;
                }
            }
            
            async function generateHTML() {
                if (!window.lastQueryData) {
                    alert('Por favor, faça uma pergunta primeiro');
                    return;
                }
                
                const htmlResultDiv = document.getElementById('htmlResult');
                htmlResultDiv.style.display = 'block';
                htmlResultDiv.className = 'result';
                htmlResultDiv.innerHTML = '🎨 Gerando relatório HTML estilizado...';
                
                try {
                    const response = await fetch('/api/generate-html', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            question: window.lastQueryData.query,
                            analysis: window.lastQueryData.analysis,
                            data: window.lastQueryData.raw_data || [],
                            sql_query: window.lastQueryData.sql
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        htmlResultDiv.className = 'result success';
                        htmlResultDiv.innerHTML = `
                            <h3>✅ Relatório HTML Gerado:</h3>
                            <p>Relatório estilizado com gráficos e mapas gerado com sucesso!</p>
                            <button onclick="openHTMLReport()" style="background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px;">
                                📊 Abrir Relatório Completo
                            </button>
                        `;
                        
                        // Armazenar HTML para abrir em nova janela
                        window.generatedHTML = data.html;
                    } else {
                        htmlResultDiv.className = 'result error';
                        htmlResultDiv.innerHTML = `❌ Erro: ${data.error}`;
                    }
                } catch (error) {
                    htmlResultDiv.className = 'result error';
                    htmlResultDiv.innerHTML = `❌ Erro de conexão: ${error.message}`;
                }
            }
            
            function openHTMLReport() {
                if (window.generatedHTML) {
                    const newWindow = window.open('', '_blank');
                    newWindow.document.write(window.generatedHTML);
                    newWindow.document.close();
                }
            }
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Endpoint de saúde da aplicação"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'llm_agent': 'available' if llm_agent else 'unavailable'
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
        
        print(f"🤖 Processando pergunta: {query}")
        
        # Processar a consulta com o agente LLM
        result = llm_agent.query(query)

        # Normalizar campos esperados pelo frontend
        sql_text = result.get('sql') or result.get('sql_query') or ''
        analysis_text = result.get('analysis', '')
        record_count = result.get('record_count') or result.get('data_count') or 0
        raw_data = result.get('raw_data', [])

        return jsonify({
            'success': True,
            'query': query,
            'sql': sql_text,
            'analysis': analysis_text,
            'record_count': record_count,
            'raw_data': raw_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/query: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@app.route('/api/generate-html', methods=['POST'])
def api_generate_html():
    """Endpoint para gerar HTML estilizado com gráficos e mapas"""
    try:
        if not llm_agent:
            return jsonify({
                'success': False,
                'error': 'Agente LLM não está disponível'
            }), 500
        
        payload = request.get_json() or {}
        question = payload.get('question', '').strip()
        analysis = payload.get('analysis', '').strip()
        data = payload.get('data', [])
        sql_query = payload.get('sql_query', '')

        if not question or not analysis:
            return jsonify({
                'success': False,
                'error': 'Parâmetros insuficientes: envie question e analysis'
            }), 400

        print(f"🎨 Gerando HTML estilizado para: {question}")
        
        # Gerar HTML com dados completos
        html = llm_agent.generate_branded_html(
            question=question,
            analysis=analysis,
            data=data,
            sql_query=sql_query
        )

        return jsonify({
            'success': True,
            'html': html,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Erro no /api/generate-html: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro ao gerar HTML: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("🚀 Iniciando Interface Web do Agente LLM...")
    print("🌐 Acesse: http://localhost:7719")
    print("📊 RESULT_LIMIT: 10000")
    print("⏱️  MAX_QUERY_TIMEOUT: 30s")
    print("🔧 DEBUG: True")
    
    app.run(
        host='0.0.0.0',
        port=7719,
        debug=True
    )
