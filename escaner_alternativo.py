import minimalmodbus
import serial
import serial.tools.list_ports
import time
import sys

def obtener_puertos_disponibles():
    """Obtiene una lista de puertos COM disponibles"""
    puertos = list(serial.tools.list_ports.comports())
    puertos_com = [puerto.device for puerto in puertos if 'COM' in puerto.device]
    puertos_com.sort(key=lambda x: int(''.join(filter(str.isdigit, x))))
    return puertos_com

def leer_registros_dispositivo(instrumento):
    """Lee los registros importantes del dispositivo encontrado"""
    try:
        # Intentar leer los primeros 10 registros
        print(f"\nValores del dispositivo en dirección {instrumento.address}:")
        print("-" * 40)
        
        # Leer registros holding
        for i in range(10):
            try:
                valor = instrumento.read_register(i)
                print(f"Registro holding {i}: {valor}")
            except:
                continue
        
        # Leer registros de entrada
        print("\nRegistros de entrada:")
        print("-" * 40)
        for i in range(10):
            try:
                valor = instrumento.read_register(i, functioncode=4)  # 4 = Input Registers
                if -50 <= valor <= 150:
                    print(f"Registro {i}: {valor/10:.1f}°C")
                else:
                    print(f"Registro {i}: {valor}")
            except:
                continue
                
    except Exception as e:
        print(f"Error al leer registros: {str(e)}")

def escanear_dispositivos(puerto_serial, velocidad=9600, timeout=0.1):
    """
    Escanea dispositivos Modbus RTU usando minimalmodbus
    """
    dispositivos_encontrados = []
    
    print(f"\nIniciando escaneo en {puerto_serial} a {velocidad} baudios...")
    print("Este proceso puede tomar varios minutos. Por favor, espere...\n")
    
    # Escanear direcciones del 1 al 247
    for direccion in range(1, 248):
        try:
            sys.stdout.write(f"\rEscaneando dirección: {direccion}/247")
            sys.stdout.flush()
            
            # Configurar instrumento
            instrumento = minimalmodbus.Instrument(puerto_serial, direccion)
            instrumento.serial.baudrate = velocidad
            instrumento.serial.timeout = timeout
            instrumento.mode = minimalmodbus.MODE_RTU
            
            # Intentar leer el primer registro
            try:
                instrumento.read_register(0)
                print(f"\n¡Dispositivo encontrado en dirección {direccion}!")
                dispositivos_encontrados.append(direccion)
                # Leer registros cuando se encuentra un dispositivo
                leer_registros_dispositivo(instrumento)
                print("\nContinuando escaneo...")
            except:
                pass
            
        except Exception:
            pass
        
        time.sleep(0.1)
    
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
    print("=== Escáner Alternativo de Dispositivos Modbus RTU ===\n")
    
    # Mostrar información de puertos
    print("Información de puertos COM detectados:")
    print("-" * 50)
    info_puertos = obtener_info_puertos()
    
    if not info_puertos:
        print("No se detectaron puertos COM")
        print("Verifique la conexión del convertidor USB-Serial")
        input("\nPresione Enter para salir...")
        return
    
    for info in info_puertos:
        print(f"\nPuerto: {info['puerto']}")
        print(f"Descripción: {info['descripcion']}")
        if info['fabricante']:
            print(f"Fabricante: {info['fabricante']}")
        if info['vid'] and info['pid']:
            print(f"VID:PID: {info['vid']:04X}:{info['pid']:04X}")
    
    print("\nIMPORTANTE: Asegúrese de que SITRAD esté cerrado")
    continuar = input("¿Desea continuar? (s/n): ")
    if continuar.lower() != 's':
        return

    # Selección del puerto
    puertos_disponibles = obtener_puertos_disponibles()
    print("\nPuertos COM disponibles:")
    for i, puerto in enumerate(puertos_disponibles, 1):
        print(f"{i}. {puerto}")
    
    while True:
        try:
            seleccion = int(input("\nSeleccione el número del puerto (1-{}): ".format(len(puertos_disponibles))))
            if 1 <= seleccion <= len(puertos_disponibles):
                puerto_seleccionado = puertos_disponibles[seleccion - 1]
                break
        except ValueError:
            print("Por favor, ingrese un número válido")
    
    # Selección de velocidad
    velocidades = [9600, 19200]
    print("\nVelocidades disponibles:")
    for i, vel in enumerate(velocidades, 1):
        print(f"{i}. {vel} baudios")
    
    while True:
        try:
            sel_vel = int(input("\nSeleccione la velocidad (1-{}): ".format(len(velocidades))))
            if 1 <= sel_vel <= len(velocidades):
                velocidad = velocidades[sel_vel - 1]
                break
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
        print("1. Verifique la conexión física")
        print("2. Confirme la velocidad de comunicación")
        print("3. Asegúrese que los dispositivos estén energizados")
    
    input("\nPresione Enter para salir...")

if __name__ == "__main__":
    main() 