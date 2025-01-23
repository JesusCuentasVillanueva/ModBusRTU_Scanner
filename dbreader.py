import sqlite3
import os
import magic
from tkinter import filedialog
import tkinter as tk

def find_db_files(directory="."):
    """Busca archivos de base de datos en el directorio especificado"""
    db_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_type = magic.from_file(file_path)
                if "SQLite" in file_type:
                    db_files.append(file_path)
                elif any(keyword in file_type.lower() for keyword in ['database', 'mysql', 'postgresql']):
                    print(f"Archivo de base de datos encontrado (no SQLite): {file_path}")
                    print(f"Tipo: {file_type}")
            except Exception:
                continue
    return db_files

def explore_sqlite_db(db_path):
    """Explora una base de datos SQLite"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\nBase de datos: {db_path}")
        print("\nTablas encontradas:")
        for i, table in enumerate(tables, 1):
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"{i}. {table_name} ({count} registros)")

        while True:
            try:
                seleccion = input("\nSeleccione el número de la tabla para ver detalles (0 para salir): ")
                if seleccion == "0":
                    break

                index = int(seleccion) - 1
                if 0 <= index < len(tables):
                    table_name = tables[index][0]
                    print(f"\nDetalles de la tabla: {table_name}")
                    
                    # Mostrar estructura
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    print("\nEstructura:")
                    for col in columns:
                        print(f"  {col[1]} ({col[2]})")
                    
                    # Mostrar primeros registros
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                    rows = cursor.fetchall()
                    
                    if rows:
                        print("\nPrimeros 5 registros:")
                        # Mostrar nombres de columnas
                        column_names = [col[1] for col in columns]
                        print("  |  ".join(column_names))
                        print("-" * (sum(len(name) for name in column_names) + 3 * (len(column_names) - 1)))
                        
                        # Mostrar datos
                        for row in rows:
                            print("  |  ".join(str(value) for value in row))
                    else:
                        print("\nLa tabla está vacía")
                    
                    # Opciones adicionales
                    while True:
                        print("\nOpciones:")
                        print("1. Ver más registros")
                        print("2. Buscar en la tabla")
                        print("3. Volver al listado de tablas")
                        
                        opcion = input("\nSeleccione una opción (1-3): ")
                        
                        if opcion == "1":
                            limit = input("¿Cuántos registros desea ver? (máximo 50): ")
                            try:
                                limit = min(int(limit), 50)
                                cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
                                rows = cursor.fetchall()
                                print("\nRegistros:")
                                print("  |  ".join(column_names))
                                print("-" * (sum(len(name) for name in column_names) + 3 * (len(column_names) - 1)))
                                for row in rows:
                                    print("  |  ".join(str(value) for value in row))
                            except ValueError:
                                print("Por favor, ingrese un número válido")
                        
                        elif opcion == "2":
                            columna = input(f"¿En qué columna desea buscar? ({', '.join(column_names)}): ")
                            if columna in column_names:
                                valor = input("Ingrese el valor a buscar: ")
                                cursor.execute(f"SELECT * FROM {table_name} WHERE {columna} LIKE ? LIMIT 10", (f"%{valor}%",))
                                rows = cursor.fetchall()
                                if rows:
                                    print("\nResultados encontrados:")
                                    print("  |  ".join(column_names))
                                    print("-" * (sum(len(name) for name in column_names) + 3 * (len(column_names) - 1)))
                                    for row in rows:
                                        print("  |  ".join(str(value) for value in row))
                                else:
                                    print("No se encontraron resultados")
                            else:
                                print("Columna no válida")
                        
                        elif opcion == "3":
                            break
                        
                        else:
                            print("Opción no válida")
                else:
                    print("Selección inválida")
            except ValueError:
                print("Por favor, ingrese un número válido")
            except sqlite3.Error as e:
                print(f"Error al consultar la tabla: {e}")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Error al explorar la base de datos: {e}")

def main():
    print("1. Buscar bases de datos automáticamente")
    print("2. Especificar ruta del archivo manualmente")
    print("3. Seleccionar archivo usando explorador")
    
    opcion = input("\nSeleccione una opción (1-3): ")
    
    if opcion == "1":
        print("\nBuscando bases de datos...")
        db_files = find_db_files()
        
        if not db_files:
            print("No se encontraron bases de datos SQLite.")
            return
        
        print("\nBases de datos SQLite encontradas:")
        for i, db_path in enumerate(db_files, 1):
            print(f"{i}. {db_path}")
        
        while True:
            try:
                selection = input("\nSeleccione el número de la base de datos a explorar (0 para salir): ")
                if selection == "0":
                    break
                
                index = int(selection) - 1
                if 0 <= index < len(db_files):
                    explore_sqlite_db(db_files[index])
                else:
                    print("Selección inválida")
            except ValueError:
                print("Por favor, ingrese un número válido")
    
    elif opcion == "2":
        while True:
            ruta = input("\nIngrese la ruta completa del archivo (o 0 para salir): ")
            if ruta == "0":
                break
            
            if os.path.exists(ruta):
                try:
                    file_type = magic.from_file(ruta)
                    if "SQLite" in file_type:
                        explore_sqlite_db(ruta)
                    else:
                        print(f"El archivo no parece ser una base de datos SQLite.")
                        print(f"Tipo detectado: {file_type}")
                except Exception as e:
                    print(f"Error al analizar el archivo: {e}")
            else:
                print("La ruta especificada no existe.")
    
    elif opcion == "3":
        root = tk.Tk()
        root.withdraw()  # Oculta la ventana principal de tkinter
        
        while True:
            print("\nSe abrirá el explorador de archivos...")
            ruta = filedialog.askopenfilename(
                title="Seleccione una base de datos SQLite",
                filetypes=[
                    ("Bases de datos SQLite", "*.db *.sqlite *.sqlite3"),
                    ("Todos los archivos", "*.*")
                ]
            )
            
            if not ruta:  # Si el usuario cancela la selección
                break
            
            try:
                file_type = magic.from_file(ruta)
                if "SQLite" in file_type:
                    explore_sqlite_db(ruta)
                else:
                    print(f"El archivo no parece ser una base de datos SQLite.")
                    print(f"Tipo detectado: {file_type}")
            except Exception as e:
                print(f"Error al analizar el archivo: {e}")
            
            continuar = input("\n¿Desea seleccionar otro archivo? (s/n): ").lower()
            if continuar != 's':
                break
    
    else:
        print("Opción inválida")

if __name__ == "__main__":
    main()
