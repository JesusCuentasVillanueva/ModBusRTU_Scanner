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
    """
    try:
        # Intentar leer los primeros 10 registros holding
        resultado = cliente.read_holding_registers(
            address=0,
            count=10,
            slave=direccion
        )
        
        print(f"\nValores del dispositivo en dirección {direccion}:")
        print("-" * 40)
        
        if resultado and not resultado.isError():
            registros = resultado.registers if hasattr(resultado, 'registers') else resultado
            if registros:
                for i, valor in enumerate(registros):
                    print(f"Registro Holding {i}: {valor}")
            else:
                print("El dispositivo respondió pero no devolvió datos de registros holding")
        else:
            print(f"Error al leer registros holding: {resultado if resultado else 'Sin respuesta'}")
            
        # Pequeña pausa entre lecturas
        time.sleep(0.1)
            
        # Intentar leer registros de entrada
        resultado_input = cliente.read_input_registers(
            address=0,
            count=10,
            slave=direccion
        )
        
        print("\nRegistros de entrada:")
        print("-" * 40)
        
        if resultado_input and not resultado_input.isError():
            registros_input = resultado_input.registers if hasattr(resultado_input, 'registers') else resultado_input
            if registros_input:
                for i, valor in enumerate(registros_input):
                    # Convertir a temperatura si el valor está en el rango esperado
                    if -50 <= valor <= 150:
                        print(f"Registro Input {i}: {valor/10:.1f}°C")
                    else:
                        print(f"Registro Input {i}: {valor}")
            else:
                print("El dispositivo respondió pero no devolvió datos de registros input")
        else:
            print(f"Error al leer registros input: {resultado_input if resultado_input else 'Sin respuesta'}")
                
    except ModbusException as e:
        print(f"Error Modbus al leer registros: {str(e)}")
        print(f"Tipo de error: {type(e).__name__}")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
        print(f"Tipo de error: {type(e).__name__}")

def escanear_dispositivos(puerto_serial, velocidad=9600, timeout=0.2):
    """
    Escanea dispositivos Modbus RTU en el puerto serial especificado.
    
    Args:
        puerto_serial (str): Puerto serial (ejemplo: 'COM1' en Windows, '/dev/ttyUSB0' en Linux)
        velocidad (int): Velocidad en baudios
        timeout (float): Tiempo de espera para cada intento de conexión
    """
    # Configurar cliente Modbus RTU
    cliente = ModbusSerialClient(
        port=puerto_serial,
        baudrate=velocidad,
        timeout=timeout,
        parity='N',
        stopbits=1,
        bytesize=8
    )
    
    if not cliente.connect():
        print(f"Error: No se pudo conectar al puerto {puerto_serial}")
        print("Esto puede deberse a que:")
        print("1. SITRAD aún está abierto y usando el puerto")
        print("2. Otro programa está usando el puerto")
        print("3. El convertidor no está conectado correctamente")
        return []
    
    dispositivos_encontrados = []
    
    print(f"\nIniciando escaneo en {puerto_serial} a {velocidad} baudios...")
    print("Este proceso puede tomar varios minutos. Por favor, espere...\n")
    
    # Escanear direcciones del 1 al 247 (rango válido para Modbus)
    for direccion in range(1, 248):
        try:
            sys.stdout.write(f"\rEscaneando dirección: {direccion}/247")
            sys.stdout.flush()
            
            # Intentar leer el primer registro holding
            resultado = cliente.read_holding_registers(
                address=0,
                count=1,
                slave=direccion
            )
            
            if resultado and not resultado.isError():
                print(f"\n¡Dispositivo encontrado en dirección {direccion}!")
                dispositivos_encontrados.append(direccion)
                # Leer registros cuando se encuentra un dispositivo
                time.sleep(0.2)  # Pausa antes de leer los registros
                leer_registros_dispositivo(cliente, direccion)
                print("\nContinuando escaneo...")
            
        except ModbusException:
            pass
        
        time.sleep(0.15)  # Aumentado el tiempo de pausa entre intentos
    
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
    print("=== Escáner de Dispositivos Modbus RTU para SITRAD ===\n")
    
    # Mostrar información detallada de los puertos
    print("Información de puertos COM detectados:")
    print("-" * 50)
    info_puertos = obtener_info_puertos()
    
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

if __name__ == "__main__":
    main()
