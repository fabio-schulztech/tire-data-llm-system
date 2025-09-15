#!/usr/bin/env python3
"""
Aplicação Flask simplificada para teste do sistema TPMS com IA
"""

import os
from flask import Flask, render_template, request, jsonify, Response
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
            
            /* Modal de Loading */
            .modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            }
            
            .modal-content {
                background: #2c3e50;
                border-radius: 15px;
                padding: 0;
                max-width: 600px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                animation: modalSlideIn 0.3s ease-out;
            }
            
            @keyframes modalSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(-50px) scale(0.9);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }
            
            .modal-header {
                background: linear-gradient(135deg, #3498db, #2980b9);
                color: white;
                padding: 20px;
                border-radius: 15px 15px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .modal-header h2 {
                margin: 0;
                font-size: 1.5em;
            }
            
            .loading-spinner {
                width: 30px;
                height: 30px;
                border: 3px solid rgba(255, 255, 255, 0.3);
                border-top: 3px solid white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .modal-body {
                padding: 30px;
            }
            
            .progress-container {
                margin-bottom: 30px;
            }
            
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #34495e;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 10px;
            }
            
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #3498db, #2ecc71);
                width: 0%;
                transition: width 0.5s ease;
                border-radius: 4px;
            }
            
            .progress-text {
                color: #ecf0f1;
                font-weight: 600;
                text-align: center;
                font-size: 1.1em;
            }
            
            .loading-steps {
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .step {
                display: flex;
                align-items: center;
                padding: 15px;
                background: #34495e;
                border-radius: 10px;
                transition: all 0.3s ease;
                border-left: 4px solid #34495e;
            }
            
            .step.active {
                background: #2c3e50;
                border-left-color: #3498db;
                transform: translateX(5px);
            }
            
            .step.completed {
                background: #27ae60;
                border-left-color: #2ecc71;
            }
            
            .step-icon {
                font-size: 1.5em;
                margin-right: 15px;
                min-width: 30px;
            }
            
            .step-text {
                flex: 1;
                color: #ecf0f1;
                font-weight: 500;
            }
            
            .step-status {
                color: #95a5a6;
                font-size: 0.9em;
                font-weight: 600;
            }
            
            .step.completed .step-status {
                color: #2ecc71;
            }
            
            .step.active .step-status {
                color: #3498db;
            }
            
            .modal-footer {
                padding: 20px 30px;
                background: #34495e;
                border-radius: 0 0 15px 15px;
                text-align: center;
            }
            
            .loading-details {
                color: #bdc3c7;
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Sistema TPMS com IA - Teste</h1>
            <p>Sistema inteligente de monitoramento de pneus com integração ChatGPT</p>
            
            <div class="form-group">
                <label for="query">Faça sua pergunta sobre os dados de pneus:</label>
                <input type="text" id="query" placeholder="Ex: Quantos veículos temos no sistema?" />
                <small style="color: #7f8c8d; font-size: 0.9em; display: block; margin-top: 5px;">
                    💡 O relatório HTML será gerado e aberto automaticamente em uma nova aba após a análise
                </small>
            </div>
            
            <button onclick="askQuestion()">Perguntar</button>
            <button onclick="downloadCSV()" style="background: #e67e22; margin-left: 10px;">📊 Download CSV</button>
            
            <div id="result" class="result" style="display: none;"></div>
            <div id="htmlResult" class="result" style="display: none;"></div>
        </div>

        <!-- Modal de Loading -->
        <div id="loadingModal" class="modal" style="display: none;">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>🔄 Processando Consulta</h2>
                    <div class="loading-spinner"></div>
                </div>
                <div class="modal-body">
                    <div class="progress-container">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill"></div>
                        </div>
                        <div class="progress-text" id="progressText">Iniciando...</div>
                    </div>
                    <div class="loading-steps">
                        <div class="step" id="step1">
                            <div class="step-icon">🤖</div>
                            <div class="step-text">Processando pergunta com IA</div>
                            <div class="step-status" id="status1">⏳ Aguardando...</div>
                        </div>
                        <div class="step" id="step2">
                            <div class="step-icon">📝</div>
                            <div class="step-text">Gerando consulta SQL</div>
                            <div class="step-status" id="status2">⏳ Aguardando...</div>
                        </div>
                        <div class="step" id="step3">
                            <div class="step-icon">🔍</div>
                            <div class="step-text">Executando consulta no banco</div>
                            <div class="step-status" id="status3">⏳ Aguardando...</div>
                        </div>
                        <div class="step" id="step4">
                            <div class="step-icon">📊</div>
                            <div class="step-text">Gerando CSV para análise</div>
                            <div class="step-status" id="status4">⏳ Aguardando...</div>
                        </div>
                        <div class="step" id="step5">
                            <div class="step-icon">🧠</div>
                            <div class="step-text">Analisando dados com IA</div>
                            <div class="step-status" id="status5">⏳ Aguardando...</div>
                        </div>
                        <div class="step" id="step6">
                            <div class="step-icon">🎨</div>
                            <div class="step-text">Gerando relatório HTML premium</div>
                            <div class="step-status" id="status6">⏳ Aguardando...</div>
                        </div>
                        <div class="step" id="step7">
                            <div class="step-icon">🚀</div>
                            <div class="step-text">Abrindo relatório em nova aba</div>
                            <div class="step-status" id="status7">⏳ Aguardando...</div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <div class="loading-details" id="loadingDetails">
                        <small>Preparando sistema para processar sua consulta...</small>
                    </div>
                </div>
            </div>
        </div>

        <script>
            async function askQuestion() {
                const query = document.getElementById('query').value;
                const resultDiv = document.getElementById('result');
                
                if (!query.trim()) {
                    alert('Por favor, digite uma pergunta');
                    return;
                }
                
                // Mostrar modal de loading
                showLoadingModal();
                
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
                        
                        // Gerar e exibir HTML automaticamente
                        setTimeout(() => {
                            generateHTML();
                        }, 1000); // Aguardar 1 segundo para o usuário ver a análise
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
                        // Armazenar HTML para abrir em nova janela
                        window.generatedHTML = data.html;
                        
                        // Abrir automaticamente em nova aba
                        openHTMLReport();
                        
                        htmlResultDiv.className = 'result success';
                        htmlResultDiv.innerHTML = `
                            <h3>✅ Relatório HTML Gerado e Aberto:</h3>
                            <p>Relatório estilizado com gráficos e mapas foi aberto automaticamente em uma nova aba!</p>
                            <button onclick="openHTMLReport()" style="background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px;">
                                📊 Abrir Relatório Novamente
                            </button>
                        `;
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
            
            async function downloadCSV() {
                const query = document.getElementById('query').value;
                
                if (!query.trim()) {
                    alert('Por favor, digite uma pergunta primeiro');
                    return;
                }
                
                try {
                    const response = await fetch('/api/download-csv', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ query: query })
                    });
                    
                    if (response.ok) {
                        // Obter o nome do arquivo do header Content-Disposition
                        const contentDisposition = response.headers.get('Content-Disposition');
                        let filename = 'consulta_tpms.csv';
                        if (contentDisposition) {
                            const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                            if (filenameMatch) {
                                filename = filenameMatch[1];
                            }
                        }
                        
                        // Criar blob e fazer download
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                        
                        console.log('✅ CSV baixado com sucesso');
                    } else {
                        const errorData = await response.json();
                        alert(`❌ Erro ao baixar CSV: ${errorData.error || 'Erro desconhecido'}`);
                    }
                } catch (error) {
                    console.error('❌ Erro de conexão:', error);
                    alert(`❌ Erro de conexão: ${error.message}`);
                }
            }
            // Funções do modal de loading
            function showLoadingModal() {
                const modal = document.getElementById('loadingModal');
                modal.style.display = 'flex';
                
                // Resetar progresso
                updateProgress(0, 'Iniciando processamento...');
                resetSteps();
                
                // Simular progresso baseado no fluxo real
                simulateProgress();
            }
            
            function hideLoadingModal() {
                const modal = document.getElementById('loadingModal');
                modal.style.display = 'none';
            }
            
            function updateProgress(percentage, text) {
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                progressFill.style.width = percentage + '%';
                progressText.textContent = text;
            }
            
            function updateStep(stepNumber, status, details = '') {
                const step = document.getElementById(`step${stepNumber}`);
                const statusElement = document.getElementById(`status${stepNumber}`);
                const detailsElement = document.getElementById('loadingDetails');
                
                // Remover classes anteriores
                step.classList.remove('active', 'completed');
                
                if (status === 'active') {
                    step.classList.add('active');
                    statusElement.textContent = '🔄 Processando...';
                } else if (status === 'completed') {
                    step.classList.add('completed');
                    statusElement.textContent = '✅ Concluído';
                } else if (status === 'error') {
                    step.classList.add('error');
                    statusElement.textContent = '❌ Erro';
                }
                
                if (details) {
                    detailsElement.innerHTML = `<small>${details}</small>`;
                }
            }
            
            function resetSteps() {
                for (let i = 1; i <= 7; i++) {
                    const step = document.getElementById(`step${i}`);
                    const statusElement = document.getElementById(`status${i}`);
                    
                    step.classList.remove('active', 'completed', 'error');
                    statusElement.textContent = '⏳ Aguardando...';
                }
            }
            
            function simulateProgress() {
                // Simular o progresso baseado no fluxo real
                setTimeout(() => {
                    updateStep(1, 'active', 'Processando pergunta com IA...');
                    updateProgress(15, 'Processando pergunta...');
                }, 2500);
                
                setTimeout(() => {
                    updateStep(1, 'completed');
                    updateStep(2, 'active', 'Gerando consulta SQL...');
                    updateProgress(30, 'Gerando consulta SQL...');
                }, 4500);
                
                setTimeout(() => {
                    updateStep(2, 'completed');
                    updateStep(3, 'active', 'Executando consulta no banco de dados...');
                    updateProgress(45, 'Executando consulta...');
                }, 7500);
                
                setTimeout(() => {
                    updateStep(3, 'completed');
                    updateStep(4, 'active', 'Gerando CSV para análise...');
                    updateProgress(60, 'Gerando CSV...');
                }, 9500);
                
                setTimeout(() => {
                    updateStep(4, 'completed');
                    updateStep(5, 'active', 'Analisando dados com IA...');
                    updateProgress(75, 'Analisando dados...');
                }, 13500);
                
                setTimeout(() => {
                    updateStep(5, 'completed');
                    updateStep(6, 'active', 'Gerando relatório HTML premium...');
                    updateProgress(90, 'Gerando relatório...');
                }, 15500);
                
                setTimeout(() => {
                    updateStep(6, 'completed');
                    updateStep(7, 'active', 'Abrindo relatório em nova aba...');
                    updateProgress(100, 'Finalizando...');
                }, 26500);
                
                setTimeout(() => {
                    updateStep(7, 'completed');
                    updateProgress(100, 'Processamento concluído!');
                    setTimeout(() => {
                        hideLoadingModal();
                    }, 4000);
                }, 29500);
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

@app.route('/api/download-csv', methods=['POST'])
def api_download_csv():
    """Endpoint para download de CSV com dados da consulta"""
    try:
        if not llm_agent:
            return jsonify({
                'success': False,
                'error': 'Agente LLM não está disponível'
            }), 500
        
        payload = request.get_json() or {}
        query = payload.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query não fornecida'
            }), 400
        
        print(f"📊 Gerando CSV para consulta: {query}")
        
        # Executar a consulta SQL diretamente
        result = llm_agent.query(query)
        
        # Verificar se houve erro na consulta
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': f'Erro na consulta SQL: {result["error"]}'
            }), 500
        
        raw_data = result.get('raw_data', [])
        columns = result.get('columns', [])
        
        if not raw_data:
            return jsonify({
                'success': False,
                'error': 'Nenhum dado encontrado para exportar'
            }), 400
        
        # Gerar CSV
        import csv
        import io
        from datetime import datetime
        
        # Criar buffer de memória para o CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escrever cabeçalho
        if columns:
            writer.writerow(columns)
        else:
            # Se não há colunas definidas, usar as chaves do primeiro registro
            writer.writerow(raw_data[0].keys() if raw_data else [])
        
        # Escrever dados
        for row in raw_data:
            if isinstance(row, dict):
                writer.writerow(row.values())
            else:
                writer.writerow(row)
        
        # Obter conteúdo do CSV
        csv_content = output.getvalue()
        output.close()
        
        # Criar nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"consulta_tpms_{timestamp}.csv"
        
        # Criar resposta com CSV
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        print(f"❌ Erro no /api/download-csv: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
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
