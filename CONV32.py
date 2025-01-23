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
        self.serial_config = {
            'baudrate': baudrate,
            'bytesize': serial.EIGHTBITS,
            'parity': serial.PARITY_EVEN,
            'stopbits': serial.STOPBITS_ONE,
            'timeout': 1
        }
        self.ser = None
        self.setup_logging(log_level)

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

            comando = self.create_command(address)
            self.ser.write(comando)
            time.sleep(0.1)

            if self.ser.in_waiting:
                response = self.ser.read(self.ser.in_waiting)
                return self.parse_response(response)
            
            return None

        except ConnectionError as e:
            self.logger.error(f"Error de conexión en dispositivo {address}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error al leer dispositivo {address}: {e}")
            return None

    def create_command(self, address):
        """Crea el comando para el dispositivo"""
        try:
            return bytes([
                address,
                0x02,
                0x00,
                0x00  # Checksum simplificado
            ])
        except Exception as e:
            raise DeviceError(f"Error creando comando: {e}")

    def parse_response(self, response):
        """Parsea la respuesta del dispositivo"""
        try:
            if not response or len(response) < 4:
                raise DeviceError("Respuesta incompleta del dispositivo")

            temperatura = response[2] / 10.0
            
            # Validación básica del valor
            if not -50 <= temperatura <= 150:
                raise DeviceError(f"Temperatura fuera de rango: {temperatura}°C")
                
            return temperatura

        except Exception as e:
            self.logger.error(f"Error parseando respuesta: {e}")
            return None

    def scan_devices(self, retry_count=2):
        """Escanea dispositivos con reintentos"""
        self.logger.info("Iniciando escaneo de dispositivos...")
        dispositivos_encontrados = []

        for addr in range(1, 33):
            self.logger.debug(f"Escaneando dirección: {addr}/32")
            
            for intento in range(retry_count):
                try:
                    temp = self.read_device(addr)
                    if temp is not None:
                        dispositivos_encontrados.append(addr)
                        self.logger.info(f"Dispositivo encontrado en dirección {addr}: {temp}°C")
                        break
                    elif intento < retry_count - 1:
                        time.sleep(0.5)  # Pausa entre reintentos
                except Exception as e:
                    self.logger.debug(f"Intento {intento + 1} fallido para dirección {addr}: {e}")
                    if intento == retry_count - 1:
                        self.logger.warning(f"No se pudo comunicar con dirección {addr}")

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
                    
                    for addr in devices:
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

        print("Puertos COM disponibles:")
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
        reader.connect()

        # Escanear dispositivos
        devices = reader.scan_devices()
        
        if devices:
            print(f"\nDispositivos encontrados: {devices}")
            input("\nPresione Enter para iniciar monitoreo continuo...")
            reader.monitor_temperatures(devices)
        else:
            print("\nNo se encontraron dispositivos")

    except ConnectionError as e:
        print(f"\nError de conexión: {e}")
        print("Verifique:")
        print("1. Que el CONV32 esté conectado")
        print("2. Que SITRAD esté cerrado")
        print("3. Que el puerto COM sea el correcto")
    except Exception as e:
        print(f"\nError inesperado: {e}")
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
