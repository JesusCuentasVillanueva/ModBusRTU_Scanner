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
        # Configuración exacta de SITRAD
        self.serial_config = {
            'baudrate': 9600,
            'bytesize': serial.EIGHTBITS,
            'parity': serial.PARITY_NONE,
            'stopbits': serial.STOPBITS_ONE,
            'timeout': 1
        }
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
        """Lee datos usando protocolo SITRAD"""
        try:
            self.verify_connection()

            if not 1 <= address <= 32:
                raise ValueError(f"Dirección inválida: {address}")

            # Limpiamos buffer
            self.ser.reset_input_buffer()
            
            # Enviamos comando
            comando = self.create_command(address)
            self.ser.write(comando)
            
            # SITRAD espera un poco más
            time.sleep(0.5)
            
            # Leemos respuesta completa
            response = bytearray()
            timeout = time.time() + 1.0
            
            while time.time() < timeout:
                if self.ser.in_waiting:
                    byte = self.ser.read()
                    response.extend(byte)
                    # SITRAD usa 0x03 (ETX) como fin de mensaje
                    if byte[0] == 0x03:
                        break
                time.sleep(0.05)

            if self.test_mode:
                print(f"Respuesta SITRAD: {response.hex()}")
            
            if len(response) >= 5:  # Mínimo para una respuesta válida
                return self.parse_response(response)
            
            return None

        except Exception as e:
            self.logger.error(f"Error leyendo CONV32 {address}: {e}")
            return None

    def create_command(self, address):
        """Crea el comando exacto que usa SITRAD para CONV32"""
        try:
            # Protocolo SITRAD para CONV32:
            # Byte 1: 0x02 (STX - Start of Text)
            # Byte 2: Dirección
            # Byte 3: 0x72 (Comando de lectura SITRAD)
            # Byte 4: Checksum (XOR de bytes 2 y 3)
            cmd = 0x72  # Comando específico de SITRAD
            checksum = address ^ cmd  # XOR para checksum
            
            comando = bytes([
                0x02,      # STX
                address,   # Dirección
                cmd,      # Comando lectura
                checksum  # Checksum
            ])
            
            if self.test_mode:
                print(f"Comando SITRAD: {comando.hex()}")
            
            return comando
        except Exception as e:
            raise DeviceError(f"Error creando comando SITRAD: {e}")

    def parse_response(self, response):
        """Parsea la respuesta del protocolo SITRAD"""
        try:
            # Formato respuesta SITRAD:
            # Byte 1: 0x02 (STX)
            # Byte 2: Dirección
            # Byte 3: Status
            # Byte 4: Temperatura (valor * 10)
            # Byte 5: Checksum
            # Byte 6: 0x03 (ETX)
            
            if response[0] != 0x02 or response[-1] != 0x03:
                return None
            
            status = response[2]
            if status != 0:
                self.logger.warning(f"Status SITRAD no es 0: {status}")
                return None
            
            # La temperatura viene multiplicada por 10
            temp_raw = response[3]
            temperatura = temp_raw / 10.0
            
            # Verificar checksum
            checksum = response[-2]
            calc_checksum = response[1] ^ response[2] ^ response[3]
            if checksum != calc_checksum:
                self.logger.warning("Error de checksum en respuesta")
                return None
            
            return temperatura

        except Exception as e:
            self.logger.error(f"Error parseando respuesta SITRAD: {e}")
            return None

    def set_test_mode(self, enabled=True):
        """Activa/desactiva el modo de prueba con más información de diagnóstico"""
        self.test_mode = enabled
        if enabled:
            self.logger.setLevel(logging.DEBUG)

    def test_connection(self):
        """Prueba de conexión específica para CONV32"""
        try:
            print("\n=== Prueba de Conexión CONV32 ===")
            print("Configuración:")
            print(f"Puerto: {self.port}")
            print(f"Baudrate: {self.serial_config['baudrate']}")
            print(f"Bits: {self.serial_config['bytesize']}")
            print(f"Paridad: {self.serial_config['parity']}")
            
            self.connect()
            print("✓ Puerto abierto")
            
            # Probamos direcciones típicas
            for addr in [1, 2]:
                print(f"\nProbando CONV32 en dirección {addr}...")
                temp = self.read_device(addr)
                if temp is not None:
                    print(f"✓ Temperatura leída: {temp}°C")
                    return True
                
            print("\n⚠ No se detectó ningún CONV32")
            print("\nVerifique:")
            print("1. Conexiones RS-485:")
            print("   - TX+ / A+ → A+ del CONV32")
            print("   - TX- / B- → B- del CONV32")
            print("2. Alimentación del CONV32")
            print("3. Dirección configurada en el CONV32")
            print("4. Que no haya otros dispositivos usando el puerto")
            return False
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
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

    def setup_sniffer(self):
        """Configura el sniffer para capturar comunicación SITRAD"""
        try:
            print("\n=== Modo Sniffer SITRAD ===")
            print("Instrucciones:")
            print("1. Mantenga este programa ejecutándose")
            print("2. Abra SITRAD y configure el mismo puerto COM")
            print("3. El sniffer capturará la comunicación en ambas direcciones")
            print("\nNotas:")
            print("- Los datos se guardarán en 'sitrad_capture.log'")
            print("- Use Ctrl+C para detener la captura")
            
            self.sniff_mode = True
            self.captured_data = []
            
            # Cerramos conexión existente si hay
            if self.ser and self.ser.is_open:
                self.ser.close()
            
            # Abrimos el puerto en modo monitoreo
            self.ser = serial.Serial(
                port=self.port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            print("\nSniffing iniciado en", self.port)
            print("Esperando comunicación...\n")
            
            # Archivo para guardar la captura
            with open('sitrad_capture.log', 'w') as log_file:
                while True:
                    if self.ser.in_waiting:
                        data = self.ser.read(self.ser.in_waiting)
                        timestamp = datetime.now()
                        self.captured_data.append((timestamp, data))
                        
                        # Formateamos los datos para mejor visualización
                        hex_data = ' '.join([f'{b:02X}' for b in data])
                        ascii_data = ''.join([chr(b) if 32 <= b <= 126 else '.' for b in data])
                        
                        log_entry = f"[{timestamp}] HEX: {hex_data} | ASCII: {ascii_data}"
                        print(log_entry)
                        log_file.write(log_entry + '\n')
                        log_file.flush()  # Forzamos escritura inmediata
                        
                        # Intentamos identificar patrones conocidos
                        self.analyze_packet(data)
                        
                    time.sleep(0.01)  # Pequeña pausa para no saturar CPU
                    
        except KeyboardInterrupt:
            print("\nSniffing detenido")
            self.analyze_captured_data()
        except Exception as e:
            print(f"Error en sniffer: {e}")
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def analyze_packet(self, data):
        """Analiza paquetes en tiempo real buscando patrones"""
        try:
            if len(data) < 4:  # Paquetes muy cortos no nos interesan
                return
            
            # Buscamos patrones conocidos
            if data[0] == 0x02:  # STX - Inicio de transmisión
                print("\n--- Posible comando SITRAD ---")
                if len(data) >= 4:
                    print(f"Dirección: {data[1]}")
                    print(f"Comando: {data[2]:02X}")
                    print(f"Checksum: {data[3]:02X}")
            
            elif data[0] == 0x03:  # ETX - Fin de transmisión
                print("--- Fin de transmisión ---\n")
            
            # Buscamos secuencias de inicialización
            if len(data) > 5 and data[0] == 0xFF:
                print("--- Posible secuencia de inicialización ---")
            
        except Exception as e:
            print(f"Error analizando paquete: {e}")

    def analyze_captured_data(self):
        """Analiza todos los datos capturados al finalizar"""
        try:
            print("\n=== Análisis de Datos Capturados ===")
            if not self.captured_data:
                print("No se capturaron datos")
                return
            
            print(f"Total de paquetes capturados: {len(self.captured_data)}")
            
            # Análisis de comandos únicos
            comandos = set()
            direcciones = set()
            
            for timestamp, data in self.captured_data:
                if len(data) >= 3 and data[0] == 0x02:
                    comandos.add(data[2])
                    direcciones.add(data[1])
            
            print("\nComandos únicos detectados:")
            for cmd in comandos:
                print(f"0x{cmd:02X}")
            
            print("\nDirecciones detectadas:")
            print(sorted(list(direcciones)))
            
            print("\nLos datos completos se guardaron en 'sitrad_capture.log'")
            
        except Exception as e:
            print(f"Error en análisis: {e}")

    def monitor_sitrad_file(self):
        """Monitorea el archivo de datos de SITRAD"""
        try:
            import os
            import json
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            # Ubicación típica de datos de SITRAD
            sitrad_path = os.path.expanduser("~\\AppData\\Local\\Sitrad")
            
            class SitradHandler(FileSystemEventHandler):
                def on_modified(self, event):
                    if event.src_path.endswith('.dat'):
                        with open(event.src_path, 'rb') as f:
                            # Leer datos actualizados de SITRAD
                            data = f.read()
                            # Procesar datos según formato de archivo
                            
            observer = Observer()
            observer.schedule(SitradHandler(), sitrad_path, recursive=False)
            observer.start()
            
            print(f"Monitoreando datos de SITRAD en {sitrad_path}")
            print("Presione Ctrl+C para detener")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
        except Exception as e:
            print(f"Error monitoreando SITRAD: {e}")

class SitradEmulator:
    """Emula el protocolo SITRAD para comunicación con CONV32"""
    
    def __init__(self):
        self.key = None  # Clave de sesión
        self.session_id = None
        
    def generate_session_key(self):
        """Genera clave de sesión como lo hace SITRAD"""
        # Esta parte requeriría ingeniería inversa del protocolo
        pass
        
    def encrypt_command(self, command, address):
        """Encripta comando usando protocolo SITRAD"""
        # Esta parte requeriría conocer el algoritmo de cifrado
        pass
        
    def decrypt_response(self, response):
        """Descifra respuesta del CONV32"""
        # Esta parte requeriría conocer el algoritmo de descifrado
        pass

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
            print("5. Configurar sniffer")
            print("6. Monitorear archivo de SITRAD")
            print("7. Salir")

            opcion = input("\nSeleccione una opción (1-7): ")

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
                reader.setup_sniffer()
            elif opcion == "6":
                reader.monitor_sitrad_file()
            elif opcion == "7":
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
