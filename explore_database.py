import psycopg2
import json

def explore_database():
    try:
        conn = psycopg2.connect("postgresql://fabioobaid:abo220993@34.125.196.215:5432/tire_data")
        cursor = conn.cursor()
        
        print("=== EXPLORANDO ESTRUTURA DO BANCO DE DADOS ===\n")
        
        # Listar todas as tabelas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"Tabelas encontradas ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        print("\n" + "="*50 + "\n")
        
        # Para cada tabela, mostrar estrutura e alguns dados de exemplo
        for table in tables:
            table_name = table[0]
            print(f"TABELA: {table_name}")
            print("-" * 30)
            
            # Estrutura da tabela
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            
            columns = cursor.fetchall()
            print("Colunas:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
            
            # Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"\nTotal de registros: {count}")
            
            # Mostrar alguns dados de exemplo (limitado a 3 registros)
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                sample_data = cursor.fetchall()
                print("\nExemplo de dados:")
                for i, row in enumerate(sample_data, 1):
                    print(f"  Registro {i}: {row}")
            
            print("\n" + "="*50 + "\n")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Erro ao explorar banco de dados: {e}")

if __name__ == "__main__":
    explore_database()

