
"""Visualizador completo do banco de dados de memória"""

import sqlite3
from datetime import datetime

print("\n" + "="*80)
print("   BANCO DE DADOS DE MEMÓRIA PERSISTENTE")
print("="*80 + "\n")

try:
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Estatísticas gerais
    cursor.execute("SELECT COUNT(*) FROM conversation_history")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM conversation_history")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM conversation_history")
    total_sessions = cursor.fetchone()[0]
    
    print("📊 ESTATÍSTICAS GERAIS")
    print("-"*80)
    print(f"Total de interações: {total}")
    print(f"Total de usuários: {total_users}")
    print(f"Total de sessões: {total_sessions}")
    
    # Listar usuários
    print("\n\n USUÁRIOS CADASTRADOS")
    print("-"*80)
    cursor.execute("""
        SELECT user_id, COUNT(*) as consultas, MAX(timestamp) as ultima_consulta
        FROM conversation_history
        GROUP BY user_id
        ORDER BY COUNT(*) DESC
    """)
    
    for row in cursor.fetchall():
        user_id, consultas, ultima = row
        print(f"\n {user_id}")
        print(f"   Consultas: {consultas}")
        print(f"   Última atividade: {ultima}")
    
    # Últimas 10 interações
    print("\n\n📝 ÚLTIMAS 10 INTERAÇÕES")
    print("-"*80)
    cursor.execute("""
        SELECT user_id, session_id, question, sql_query, timestamp
        FROM conversation_history
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        user_id, session_id, question, sql_query, timestamp = row
        print(f"\n{i}. [{timestamp}]")
        print(f"    Usuário: {user_id}")
        print(f"    Sessão: {session_id[:16]}...")
        print(f"    Pergunta: {question}")
        if sql_query:
            print(f"    SQL: {sql_query[:60]}...")
    
    # Análise por sessão
    print("\n\n🔍 ANÁLISE POR SESSÃO")
    print("-"*80)
    cursor.execute("""
        SELECT session_id, user_id, COUNT(*) as interacoes, 
               MIN(timestamp) as inicio, MAX(timestamp) as fim
        FROM conversation_history
        GROUP BY session_id
        ORDER BY MIN(timestamp) DESC
        LIMIT 5
    """)
    
    for row in cursor.fetchall():
        session_id, user_id, interacoes, inicio, fim = row
        print(f"\n Sessão: {session_id[:24]}...")
        print(f"    Usuário: {user_id}")
        print(f"    Interações: {interacoes}")
        print(f"    Período: {inicio} → {fim}")
    
    # Perguntas mais comuns
    print("\n\n PERGUNTAS MAIS COMUNS")
    print("-"*80)
    cursor.execute("""
        SELECT question, COUNT(*) as vezes
        FROM conversation_history
        GROUP BY question
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        pergunta, vezes = row
        print(f"{i}. {pergunta} ({vezes}x)")
    
    conn.close()
    
    print("\n" + "="*80)
    print("   ANÁLISE COMPLETA DA MEMÓRIA")
    print("="*80 + "\n")

except sqlite3.OperationalError:
    print("  Banco de dados 'memory.db' não encontrado.")
    print("\nExecute primeiro:")
    print("  python src/langgraph_workflow.py")
    print("\nPara gerar dados na memória.\n")

except Exception as e:
    print(f"❌ Erro: {e}\n")
