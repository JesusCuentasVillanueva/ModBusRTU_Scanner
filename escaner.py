from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
import time
import sys
import serial.tools.list_ports

def obtener_puertos_disponibles():
    """Obtiene una lista de puertos COM disponibles en Windows"""
    puertos = list(serial.tools.list_ports.comports())
    # Filtrar solo puertos COM
    puertos_com = [puerto.device for puerto in puertos if 'COM' in puerto.device]
    # Ordenar los puertos numéricamente (COM1, COM2, etc.)
    puertos_com.sort(key=lambda x: int(''.join(filter(str.isdigit, x))))
    return puertos_com

def leer_registros_dispositivo(cliente, direccion):
    """
    Lee los registros importantes del dispositivo encontrado
    Optimizado para dispositivos SITRAD
    """
    try:
        print(f"\nLeyendo dispositivo en dirección {direccion}...")
        
        # Leer holding registers (registros principales en SITRAD)
        try:
            resultado = cliente.read_holding_registers(
                address=0,
                count=10,
                slave=direccion
            )
            
            print(f"\nRegistros Holding:")
            print("-" * 40)
            
            if resultado and not resultado.isError():
                registros = resultado.registers if hasattr(resultado, 'registers') else resultado
                if registros:
                    for i, valor in enumerate(registros):
                        # SITRAD suele usar el registro 0 para identificación
                        if i == 0:
                            print(f"Registro Holding {i} (ID): {valor}")
                        else:
                            print(f"Registro Holding {i}: {valor}")
                else:
                    print("No hay datos en registros holding")
            else:
                print("No se pudo leer registros holding")
            
            time.sleep(0.2)
            
            # Intentar leer registros de temperatura (input registers)
            resultado_input = cliente.read_input_registers(
                address=0,
                count=10,
                slave=direccion
            )
            
            print("\nRegistros Input (Temperatura):")
            print("-" * 40)
            
            if resultado_input and not resultado_input.isError():
                registros = resultado_input.registers if hasattr(resultado_input, 'registers') else resultado_input
                if registros:
                    for i, valor in enumerate(registros):
                        # SITRAD suele usar valores de temperatura multiplicados por 10
                        if -500 <= valor <= 1500:  # Rango ampliado para SITRAD (-50°C a 150°C)
                            print(f"Registro Input {i}: {valor/10:.1f}°C")
                        else:
                            print(f"Registro Input {i}: {valor}")
                else:
                    print("No hay datos en registros input")
            else:
                print("No se pudo leer registros input")
            
        except ModbusException as e:
            print(f"Error al leer registros: {str(e)}")
            
    except Exception as e:
        print(f"Error al leer dispositivo: {str(e)}")

def escanear_dispositivos(puerto_serial, velocidad=9600, timeout=0.3):
    """
    Escanea dispositivos Modbus RTU en el puerto serial especificado.
    Configuración optimizada para convertidor USB-Serial SITRAD.
    """
    # Configurar cliente Modbus RTU con parámetros específicos para SITRAD
    cliente = ModbusSerialClient(
        port=puerto_serial,
        baudrate=velocidad,
        timeout=timeout,
        parity='E',  # SITRAD usa paridad par (Even)
        stopbits=1,
        bytesize=8,
        retries=2,
        retry_on_empty=True,
        strict=False
    )
    
    if not cliente.connect():
        print(f"Error: No se pudo conectar al puerto {puerto_serial}")
        print("Verificación para convertidor SITRAD:")
        print("1. Asegúrese que SITRAD está completamente cerrado")
        print("2. Desconecte y reconecte el convertidor USB")
        print("3. El LED del convertidor debe estar parpadeando")
        print("4. Verifique que el convertidor aparece en el Administrador de dispositivos")
        return []

    dispositivos_encontrados = []
    
    print(f"\nIniciando escaneo en {puerto_serial} a {velocidad} baudios...")
    print("Configuración: Convertidor SITRAD")
    print("Este proceso puede tomar varios minutos. Por favor, espere...\n")
    
    # Escanear direcciones del 1 al 247 (rango válido para Modbus)
    for direccion in range(1, 248):
        sys.stdout.write(f"\rEscaneando dirección: {direccion}/247")
        sys.stdout.flush()
        
        try:
            # SITRAD principalmente usa registros holding
            resultado = cliente.read_holding_registers(
                address=0,
                count=1,
                slave=direccion
            )
            
            if resultado and not resultado.isError():
                print(f"\n¡Dispositivo encontrado en dirección {direccion}!")
                dispositivos_encontrados.append(direccion)
                time.sleep(0.3)
                leer_registros_dispositivo(cliente, direccion)
                print("\nContinuando escaneo...")
            
        except ModbusException:
            pass
        except Exception as e:
            print(f"\nError en dirección {direccion}: {str(e)}")
            continue
        
        time.sleep(0.1)  # Pausa corta entre direcciones
    
    cliente.close()
    return dispositivos_encontrados

def obtener_info_puertos():
    """Obtiene información detallada de los puertos COM disponibles"""
    puertos = list(serial.tools.list_ports.comports())
    info_puertos = []
    
    for puerto in puertos:
        if 'COM' in puerto.device:
            info = {
                'puerto': puerto.device,
                'descripcion': puerto.description,
                'fabricante': puerto.manufacturer,
                'vid': puerto.vid,
                'pid': puerto.pid
            }
            info_puertos.append(info)
    
    return info_puertos

def main():
    try:
        print("=== Escáner de Dispositivos Modbus RTU para SITRAD ===\n")
        
        # Mostrar información detallada de los puertos
        print("Información de puertos COM detectados:")
        print("-" * 50)
        try:
            info_puertos = obtener_info_puertos()
        except Exception as e:
            print(f"\nError al obtener información de puertos: {str(e)}")
            print("Verifique los permisos de acceso a puertos COM")
            input("\nPresione Enter para salir...")
            return
        
        if info_puertos:
            for info in info_puertos:
                print(f"\nPuerto: {info['puerto']}")
                print(f"Descripción: {info['descripcion']}")
                if info['fabricante']:
                    print(f"Fabricante: {info['fabricante']}")
                if info['vid'] and info['pid']:
                    print(f"VID:PID: {info['vid']:04X}:{info['pid']:04X}")
        else:
            print("No se detectaron puertos COM")
            print("Posibles soluciones:")
            print("1. Instale el driver correcto para su convertidor USB-Serial")
            print("2. Verifique que el convertidor esté conectado")
            print("3. Pruebe con otro puerto USB")
            input("\nPresione Enter para salir...")
            return
        
        print("=== Escáner de Dispositivos Modbus RTU para SITRAD ===\n")
        print("IMPORTANTE: Antes de continuar:")
        print("1. Cierre el programa SITRAD")
        print("2. Anote el puerto COM y velocidad que usa SITRAD")
        print("3. Después de usar el escáner, podrá volver a abrir SITRAD\n")
        
        continuar = input("¿Ha cerrado SITRAD? (s/n): ")
        if continuar.lower() != 's':
            print("\nPor favor, cierre SITRAD antes de continuar.")
            input("\nPresione Enter para salir...")
            return

        # Obtener puertos COM disponibles
        puertos_disponibles = obtener_puertos_disponibles()
        
        if not puertos_disponibles:
            print("Error: No se encontraron puertos COM disponibles")
            print("Verifique que el convertidor esté conectado y SITRAD esté cerrado")
            input("\nPresione Enter para salir...")
            return
        
        print("Puertos COM disponibles:")
        for i, puerto in enumerate(puertos_disponibles, 1):
            print(f"{i}. {puerto}")
        print("\nNOTA: Seleccione el mismo puerto COM que usa SITRAD")
        
        # Selección del puerto
        while True:
            try:
                seleccion = int(input("\nSeleccione el número del puerto (1-{}): ".format(len(puertos_disponibles))))
                if 1 <= seleccion <= len(puertos_disponibles):
                    puerto_seleccionado = puertos_disponibles[seleccion - 1]
                    break
                else:
                    print("Por favor, seleccione un número válido")
            except ValueError:
                print("Por favor, ingrese un número válido")
        
        # Velocidades comunes en SITRAD
        velocidades = [9600, 19200]
        print("\nSeleccione la velocidad:")
        for i, vel in enumerate(velocidades, 1):
            print(f"{i}. {vel} baudios")
        
        while True:
            try:
                sel_vel = int(input("\nSeleccione la velocidad (1-{}): ".format(len(velocidades))))
                if 1 <= sel_vel <= len(velocidades):
                    velocidad = velocidades[sel_vel - 1]
                    break
                else:
                    print("Por favor, seleccione un número válido")
            except ValueError:
                print("Por favor, ingrese un número válido")
        
        # Escanear dispositivos
        dispositivos = escanear_dispositivos(puerto_seleccionado, velocidad)
        
        print("\n" + "="*40)
        if dispositivos:
            print("\nDispositivos encontrados en las siguientes direcciones:")
            for direccion in dispositivos:
                print(f"- Dirección: {direccion}")
        else:
            print("\nNo se encontraron dispositivos.")
            print("Sugerencias:")
            print("1. Verifique que sea el mismo puerto COM que usa SITRAD")
            print("2. Confirme que la velocidad seleccionada coincida con SITRAD")
            print("3. Asegúrese que los dispositivos estén encendidos")
        
        input("\nPresione Enter para salir...")

    except Exception as e:
        print("\n¡Se ha producido un error inesperado!")
        print(f"Error: {str(e)}")
        print("\nPor favor, verifique:")
        print("1. Que tiene permisos de administrador")
        print("2. Que los drivers USB están correctamente instalados")
        print("3. Que no hay otros programas usando los puertos COM")
        input("\nPresione Enter para salir...")
        return

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPrograma interrumpido por el usuario.")
    except Exception as e:
        print(f"\nError crítico: {str(e)}")
    finally:
        print("\nCerrando programa...")
        input("Presione Enter para salir...")
