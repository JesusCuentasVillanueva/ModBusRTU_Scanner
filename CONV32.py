import serial
import time
from datetime import datetime
import sys
import logging
from serial.tools import list_ports

class CONV32Error(Exception):
    """Clase base para excepciones del CONV32"""
    pass

class ConnectionError(CONV32Error):
    """Error de conexión"""
    pass

class DeviceError(CONV32Error):
    """Error de dispositivo"""
    pass

class CONV32Reader:
    def __init__(self, port='COM3', baudrate=9600, log_level=logging.INFO):
        self.port = port
        # Configuraciones comunes para CONV32
        self.serial_configs = [
            {
                'baudrate': 9600,
                'bytesize': serial.EIGHTBITS,
                'parity': serial.PARITY_NONE,
                'stopbits': serial.STOPBITS_ONE,
                'timeout': 1
            },
            {
                'baudrate': 9600,
                'bytesize': serial.EIGHTBITS,
                'parity': serial.PARITY_EVEN,
                'stopbits': serial.STOPBITS_ONE,
                'timeout': 1
            },
            {
                'baudrate': 19200,
                'bytesize': serial.EIGHTBITS,
                'parity': serial.PARITY_NONE,
                'stopbits': serial.STOPBITS_ONE,
                'timeout': 1
            }
        ]
        self.current_config = 0  # Índice de la configuración actual
        self.serial_config = self.serial_configs[self.current_config]
        self.ser = None
        self.setup_logging(log_level)
        self.test_mode = False

    def setup_logging(self, level):
        """Configura el sistema de logging"""
        self.logger = logging.getLogger('CONV32Reader')
        self.logger.setLevel(level)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Handler para archivo
        try:
            file_handler = logging.FileHandler('conv32_reader.log')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            self.logger.warning(f"No se pudo crear archivo de log: {e}")

    @staticmethod
    def list_available_ports():
        """Lista todos los puertos COM disponibles"""
        ports = []
        try:
            ports = [port.device for port in list_ports.comports() if 'COM' in port.device]
            return sorted(ports, key=lambda x: int(''.join(filter(str.isdigit, x))))
        except Exception as e:
            raise ConnectionError(f"Error al listar puertos: {e}")

    def connect(self):
        """Intenta conectar al CONV32"""
        try:
            # Verificar si el puerto existe
            available_ports = self.list_available_ports()
            if self.port not in available_ports:
                raise ConnectionError(f"Puerto {self.port} no encontrado. Puertos disponibles: {available_ports}")

            # Verificar si el puerto está en uso
            if self.ser and self.ser.is_open:
                self.ser.close()

            self.ser = serial.Serial(self.port, **self.serial_config)
            self.logger.info(f"Conectado exitosamente a {self.port}")
            return True

        except serial.SerialException as e:
            raise ConnectionError(f"Error de conexión serial: {e}")
        except Exception as e:
            raise ConnectionError(f"Error inesperado al conectar: {e}")

    def verify_connection(self):
        """Verifica que la conexión esté activa"""
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("No hay conexión activa con el dispositivo")

    def read_device(self, address):
        """Lee datos de un dispositivo específico"""
        try:
            self.verify_connection()

            if not 1 <= address <= 32:
                raise ValueError(f"Dirección inválida: {address}. Debe estar entre 1 y 32")

            # Limpiamos buffer antes de leer
            if self.ser.in_waiting:
                self.ser.reset_input_buffer()

            comando = self.create_command(address)
            self.ser.write(comando)
            
            # Esperamos respuesta con timeout
            timeout = time.time() + 2.0  # 2 segundos de timeout
            response = bytearray()
            
            while time.time() < timeout:
                if self.ser.in_waiting:
                    byte = self.ser.read()
                    response.extend(byte)
                    if len(response) >= 3:  # Esperamos mínimo 3 bytes
                        break
                time.sleep(0.1)

            if len(response) >= 3:
                if self.test_mode:
                    print(f"Datos recibidos: {response.hex()}")
                return self.parse_response(response)
            
            if self.test_mode:
                print(f"No se recibió respuesta completa del dispositivo {address}")
            return None

        except Exception as e:
            self.logger.error(f"Error al leer dispositivo {address}: {e}")
            return None

    def create_command(self, address):
        """Crea el comando de lectura para el CONV32 de Full Gauge"""
        try:
            # Probamos diferentes formatos de comando
            commands = [
                bytes([address, 0x03]),           # Formato básico
                bytes([address, 0x03, 0x00]),     # Con byte adicional
                bytes([address, 0x02]),           # Comando alternativo
                bytes([0xFF, address, 0x03])      # Con prefijo
            ]
            return commands[0]  # Comenzamos con el primer formato
        except Exception as e:
            raise DeviceError(f"Error creando comando de lectura: {e}")

    def parse_response(self, response):
        """Parsea la respuesta del CONV32"""
        try:
            if not response or len(response) < 3:
                raise DeviceError("Respuesta incompleta del CONV32")

            # El CONV32 en modo lectura devuelve:
            # Byte 0: Dirección del dispositivo
            # Byte 1: Valor entero de temperatura
            # Byte 2: Valor decimal / flags
            
            valor_entero = response[1]
            valor_decimal = response[2] & 0x0F  # Los 4 bits menos significativos
            
            # Construimos la temperatura
            temperatura = valor_entero + (valor_decimal / 10.0)
            
            # Verificamos si es negativa (bit más significativo del byte 2)
            if response[2] & 0x80:
                temperatura = -temperatura
            
            # Validación de rango para CONV32
            if not -50 <= temperatura <= 105:
                raise DeviceError(f"Temperatura fuera de rango CONV32: {temperatura}°C")
                
            return temperatura

        except Exception as e:
            self.logger.error(f"Error parseando respuesta CONV32: {e}")
            return None

    def set_test_mode(self, enabled=True):
        """Activa/desactiva el modo de prueba con más información de diagnóstico"""
        self.test_mode = enabled
        if enabled:
            self.logger.setLevel(logging.DEBUG)

    def test_connection(self):
        """Prueba específica para lectura del CONV32 con múltiples configuraciones"""
        try:
            print("\n=== Prueba de Lectura CONV32 ===")
            print("Probando diferentes configuraciones...")

            for i, config in enumerate(self.serial_configs):
                self.serial_config = config
                print(f"\nProbando configuración {i+1}:")
                print(f"Baudrate: {config['baudrate']}")
                print(f"Paridad: {config['parity']}")
                print(f"Bits: {config['bytesize']}")
                
                try:
                    if self.ser and self.ser.is_open:
                        self.ser.close()
                    self.connect()
                    print("✓ Puerto abierto")
                    
                    # Probamos lectura con diferentes direcciones comunes
                    for addr in [1, 2, 3, 0xFF]:
                        print(f"\nProbando dirección: {addr}")
                        temp = self.read_device(addr)
                        if temp is not None:
                            print(f"✓ Temperatura leída: {temp}°C")
                            print("\n¡Configuración exitosa encontrada!")
                            return True
                        
                except Exception as e:
                    print(f"Error con configuración {i+1}: {e}")
                    continue

            print("\n⚠ No se pudo establecer comunicación")
            print("\nSugerencias:")
            print("1. Verifique el cableado RS-485:")
            print("   - A+ del CONV32 → A+ del conversor")
            print("   - B- del CONV32 → B- del conversor")
            print("2. Verifique la alimentación del CONV32")
            print("3. Confirme la dirección del dispositivo en el CONV32")
            print("4. Intente con otro conversor RS-485")
            return False
            
        except Exception as e:
            print(f"\n❌ Error en prueba: {e}")
            return False

    def scan_with_options(self):
        """Escaneo de dispositivos con opciones configurables"""
        print("\n=== Opciones de Escaneo ===")
        print("1. Escaneo rápido (1 intento)")
        print("2. Escaneo normal (3 intentos)")
        print("3. Escaneo profundo (5 intentos, pausa larga)")
        print("4. Escaneo personalizado")
        
        opcion = input("\nSeleccione modo de escaneo (1-4): ")
        
        if opcion == "1":
            return self.scan_devices(retry_count=1)
        elif opcion == "2":
            return self.scan_devices(retry_count=3)
        elif opcion == "3":
            self.logger.info("Iniciando escaneo profundo...")
            time.sleep(1)  # Pausa inicial
            return self.scan_devices(retry_count=5, wait_time=2.0)
        elif opcion == "4":
            reintentos = int(input("Número de reintentos por dispositivo: "))
            pausa = float(input("Tiempo de espera entre intentos (segundos): "))
            return self.scan_devices(retry_count=reintentos, wait_time=pausa)
        else:
            print("Opción inválida, usando modo normal")
            return self.scan_devices()

    def scan_devices(self, retry_count=3, wait_time=1.0):
        """Escanea dispositivos con múltiples configuraciones"""
        self.logger.info("Iniciando escaneo de dispositivos...")
        dispositivos_encontrados = []

        # Probamos cada configuración
        for i, config in enumerate(self.serial_configs):
            if self.test_mode:
                print(f"\nProbando configuración {i+1}...")
                print(f"Baudrate: {config['baudrate']}, Paridad: {config['parity']}")
            
            self.serial_config = config
            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.connect()
                
                # Escaneamos direcciones
                for addr in range(1, 33):
                    if self.test_mode:
                        print(f"Probando dirección {addr}/32...")
                    
                    for intento in range(retry_count):
                        try:
                            if self.ser.in_waiting:
                                self.ser.reset_input_buffer()
                            
                            temp = self.read_device(addr)
                            if temp is not None:
                                dispositivos_encontrados.append((addr, config))
                                self.logger.info(f"Dispositivo encontrado en dirección {addr}: {temp}°C")
                                break
                            elif intento < retry_count - 1:
                                time.sleep(wait_time)
                        except Exception as e:
                            if self.test_mode:
                                print(f"Error en intento {intento + 1}: {e}")
                            
            except Exception as e:
                if self.test_mode:
                    print(f"Error con configuración {i+1}: {e}")
                continue

        return dispositivos_encontrados

    def monitor_temperatures(self, devices, interval=5):
        """Monitoreo continuo con manejo de errores"""
        if not devices:
            raise ValueError("No hay dispositivos para monitorear")

        self.logger.info("Iniciando monitoreo de temperaturas")
        errors_count = 0
        max_errors = 3

        try:
            while True:
                try:
                    self.verify_connection()
                    print(f"\n=== Lecturas {datetime.now().strftime('%H:%M:%S')} ===")
                    
                    for addr, config in devices:
                        try:
                            temp = self.read_device(addr)
                            if temp is not None:
                                print(f"Dispositivo {addr}: {temp}°C")
                                errors_count = 0  # Resetear contador de errores
                            else:
                                self.logger.warning(f"Lectura nula del dispositivo {addr}")
                        except Exception as e:
                            self.logger.error(f"Error leyendo dispositivo {addr}: {e}")
                    
                    time.sleep(interval)

                except ConnectionError as e:
                    errors_count += 1
                    self.logger.error(f"Error de conexión: {e}")
                    if errors_count >= max_errors:
                        raise ConnectionError("Demasiados errores consecutivos")
                    self.logger.info("Intentando reconectar...")
                    time.sleep(5)
                    self.connect()

        except KeyboardInterrupt:
            self.logger.info("Monitoreo interrumpido por el usuario")
        except Exception as e:
            self.logger.error(f"Error fatal en monitoreo: {e}")
            raise

    def close(self):
        """Cierra la conexión de manera segura"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.logger.info("Conexión cerrada correctamente")
        except Exception as e:
            self.logger.error(f"Error al cerrar conexión: {e}")

def main():
    reader = None
    try:
        # Mostrar puertos disponibles
        puertos = CONV32Reader.list_available_ports()
        if not puertos:
            print("No se encontraron puertos COM disponibles")
            return

        print("\n=== CONV32 Scanner ===")
        print("\nPuertos COM disponibles:")
        for i, puerto in enumerate(puertos, 1):
            print(f"{i}. {puerto}")

        # Selección del puerto
        while True:
            try:
                seleccion = int(input("\nSeleccione el número del puerto (1-{}): ".format(len(puertos))))
                if 1 <= seleccion <= len(puertos):
                    puerto_seleccionado = puertos[seleccion - 1]
                    break
                print("Selección inválida")
            except ValueError:
                print("Por favor ingrese un número válido")

        reader = CONV32Reader(port=puerto_seleccionado)

        # Menú de opciones
        while True:
            print("\n=== Menú Principal ===")
            print("1. Probar conexión")
            print("2. Escanear dispositivos")
            print("3. Monitoreo continuo")
            print("4. Activar modo diagnóstico")
            print("5. Salir")

            opcion = input("\nSeleccione una opción (1-5): ")

            if opcion == "1":
                reader.test_connection()
            elif opcion == "2":
                devices = reader.scan_with_options()
                if devices:
                    print(f"\nDispositivos encontrados: {devices}")
                else:
                    print("\nNo se encontraron dispositivos")
            elif opcion == "3":
                devices = reader.scan_devices()
                if devices:
                    print(f"\nIniciando monitoreo de dispositivos: {devices}")
                    reader.monitor_temperatures(devices)
                else:
                    print("\nNo hay dispositivos para monitorear")
            elif opcion == "4":
                reader.set_test_mode(True)
                print("\nModo diagnóstico activado")
            elif opcion == "5":
                break

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if reader:
            reader.close()
        print("\nPrograma finalizado")
        input("Presione Enter para salir...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error crítico: {e}")
        input("Presione Enter para salir...")
