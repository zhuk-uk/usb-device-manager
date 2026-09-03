#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USB Device Manager - Утіліта для управління USB пристроями
Один файл з усією функціональністю та інтерактивним меню
"""

import winreg
import json
import subprocess
import sys
import os
from datetime import datetime
from typing import List, Dict

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    class Fore:
        RED = YELLOW = CYAN = GREEN = ""
    class Style:
        RESET_ALL = ""


class RegistryHandler:
    """Клас для роботи з реєстром Windows"""
    
    USB_REGISTRY_PATHS = [
        r"SYSTEM\CurrentControlSet\Enum\USB",
        r"SYSTEM\CurrentControlSet\Enum\USBSTOR",
        r"SYSTEM\ControlSet001\Enum\USB",
        r"SYSTEM\ControlSet001\Enum\USBSTOR",
    ]
    
    def __init__(self):
        self.devices = []
    
    def get_all_usb_devices(self) -> List[Dict]:
        """Отримує всі USB пристрої з реєстру"""
        devices = []
        
        try:
            for path in self.USB_REGISTRY_PATHS:
                try:
                    hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
                    subkeys, _, _ = winreg.QueryInfoKey(hkey)
                    
                    for i in range(subkeys):
                        subkey_name = winreg.EnumKey(hkey, i)
                        subkey_path = f"{path}\\{subkey_name}"
                        
                        device_info = self._get_device_info(subkey_path, subkey_name)
                        if device_info:
                            devices.append(device_info)
                    
                    winreg.CloseKey(hkey)
                except Exception:
                    continue
        except Exception as e:
            print(f"Помилка при доступі до реєстру: {e}")
        
        self.devices = devices
        return devices
    
    def get_connected_devices(self) -> List[Dict]:
        """Отримує поточно підключені USB пристрої"""
        try:
            ps_command = """Get-WmiObject Win32_USBControllerDevice | 
                          ForEach-Object {[wmi]$_.Dependent} | 
                          Select-Object Name, Description, Manufacturer"""
            
            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            devices = []
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        devices.append({'name': line.strip(), 'connected': True})
            
            return devices
        except Exception as e:
            print(f"Помилка при отриманні підключених пристроїв: {e}")
            return []
    
    def _get_device_info(self, registry_path: str, device_id: str) -> Dict:
        """Отримує інформацію про конкретний пристрій"""
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path)
            
            device_info = {
                'device_id': device_id,
                'friendly_name': '',
                'manufacturer': '',
                'description': '',
                'first_install_date': '',
                'registry_path': registry_path
            }
            
            try:
                value, _ = winreg.QueryValueEx(hkey, 'FriendlyName')
                device_info['friendly_name'] = value
            except:
                pass
            
            try:
                subkeys, _, _ = winreg.QueryInfoKey(hkey)
                for i in range(subkeys):
                    subkey = winreg.EnumKey(hkey, i)
                    if subkey.startswith('Properties'):
                        subkey_path = f"{registry_path}\\{subkey}"
                        self._get_device_dates(subkey_path, device_info)
            except:
                pass
            
            winreg.CloseKey(hkey)
            return device_info
        except Exception:
            return None
    
    def _get_device_dates(self, properties_path: str, device_info: Dict):
        """Отримує дати установки пристрою"""
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, properties_path)
            subkeys, _, _ = winreg.QueryInfoKey(hkey)
            
            for i in range(subkeys):
                subkey = winreg.EnumKey(hkey, i)
                subkey_full_path = f"{properties_path}\\{subkey}"
                
                try:
                    hsubkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_full_path)
                    value, _ = winreg.QueryValueEx(hsubkey, 'InstallDate')
                    device_info['first_install_date'] = str(value)
                    winreg.CloseKey(hsubkey)
                except:
                    pass
            
            winreg.CloseKey(hkey)
        except:
            pass
    
    def remove_device_from_registry(self, device_id: str) -> bool:
        """Видаляє запис про USB пристрій з реєстру"""
        try:
            for path in self.USB_REGISTRY_PATHS:
                full_path = f"{path}\\{device_id}"
                try:
                    winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, full_path)
                    print(f"✅ Пристрій {device_id} успішно видалено з реєстру")
                    return True
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"⚠️ Помилка при видаленні {device_id}: {e}")
            
            print(f"❌ Пристрій {device_id} не знайдено в реєстру")
            return False
        except Exception as e:
            print(f"❌ Помилка: {e}")
            return False


class ReportGenerator:
    """Клас для генерації звітів"""
    
    def __init__(self, devices: List[Dict]):
        self.devices = devices
    
    def export_to_json(self, filename: str) -> bool:
        """Експортує дані про пристрої в JSON файл"""
        try:
            report_data = {
                'export_date': datetime.now().isoformat(),
                'total_devices': len(self.devices),
                'devices': self.devices
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Звіт успішно експортовано в {filename}")
            return True
        except Exception as e:
            print(f"❌ Помилка при експорті: {e}")
            return False
    
    def print_table(self, devices: List[Dict] = None):
        """Виводить пристрої у вигляді таблиці"""
        if devices is None:
            devices = self.devices
        
        if not devices:
            print("❌ Немає пристроїв для відображення")
            return
        
        table_data = []
        for device in devices:
            table_data.append([
                device.get('device_id', 'N/A')[:30],
                device.get('friendly_name', 'N/A')[:30],
                device.get('manufacturer', 'N/A')[:20],
                device.get('first_install_date', 'N/A')[:19],
            ])
        
        headers = ['Device ID', 'Назва', 'Виробник', 'Дата встановлення']
        
        if HAS_TABULATE:
            print("\n" + tabulate(table_data, headers=headers, tablefmt='grid'))
        else:
            print("\n" + " | ".join(headers))
            print("-" * 100)
            for row in table_data:
                print(" | ".join(str(cell) for cell in row))
        
        print(f"\n📊 Всього пристроїв: {len(devices)}\n")
    
    def filter_by_date(self, after_date: str = None, before_date: str = None) -> List[Dict]:
        """Фільтрує пристрої за датою"""
        filtered = self.devices.copy()
        
        if after_date:
            try:
                after_datetime = datetime.strptime(after_date, '%Y-%m-%d')
                filtered = [d for d in filtered 
                          if d.get('first_install_date') and 
                          datetime.fromisoformat(d['first_install_date'][:19]) >= after_datetime]
            except Exception as e:
                print(f"⚠️ Помилка при фільтруванні за датою: {e}")
        
        if before_date:
            try:
                before_datetime = datetime.strptime(before_date, '%Y-%m-%d')
                filtered = [d for d in filtered 
                          if d.get('first_install_date') and 
                          datetime.fromisoformat(d['first_install_date'][:19]) <= before_datetime]
            except Exception as e:
                print(f"⚠️ Помилка при фільтруванні за датою: {e}")
        
        return filtered
    
    def get_summary(self) -> Dict:
        """Отримує зведену статистику"""
        return {
            'total_devices': len(self.devices),
            'export_date': datetime.now().isoformat(),
            'devices_by_manufacturer': self._count_by_manufacturer(),
            'devices_with_dates': len([d for d in self.devices if d.get('first_install_date')])
        }
    
    def _count_by_manufacturer(self) -> Dict[str, int]:
        """Рахує пристрої за виробником"""
        manufacturers = {}
        for device in self.devices:
            manufacturer = device.get('manufacturer', 'Unknown')
            manufacturers[manufacturer] = manufacturers.get(manufacturer, 0) + 1
        return manufacturers
    
    def print_summary(self):
        """Виводить зведену статистику"""
        summary = self.get_summary()
        print("\n" + "="*60)
        print("📋 ЗВЕДЕНА СТАТИСТИКА")
        print("="*60)
        print(f"📱 Всього пристроїв: {summary['total_devices']}")
        print(f"📅 Дата експорту: {summary['export_date']}")
        print(f"✅ Пристроїв з датами: {summary['devices_with_dates']}")
        print("\n🏭 Пристрої за виробниками:")
        for manufacturer, count in summary['devices_by_manufacturer'].items():
            print(f"   - {manufacturer}: {count}")
        print("="*60 + "\n")


class USBManager:
    """Основний клас для ��правління USB пристроями"""
    
    def __init__(self):
        self.registry_handler = RegistryHandler()
        self.devices = []
        self.report_generator = None
    
    def load_all_devices(self) -> List[Dict]:
        """Завантажує всі USB пристрої з реєстру"""
        print("🔍 Сканування реєстру Windows...")
        self.devices = self.registry_handler.get_all_usb_devices()
        self.report_generator = ReportGenerator(self.devices)
        print(f"✅ Знайдено {len(self.devices)} пристроїв\n")
        return self.devices
    
    def load_connected_devices(self) -> List[Dict]:
        """Завантажує поточно підключені USB пристрої"""
        print("🔌 Отримання списку підключених пристроїв...")
        connected = self.registry_handler.get_connected_devices()
        print(f"✅ Знайдено {len(connected)} активних пристроїв\n")
        return connected
    
    def display_all_devices(self):
        """Виводить всі USB пристрої"""
        if not self.devices:
            self.load_all_devices()
        
        if self.report_generator:
            print("\n" + "="*80)
            print("📋 ВСІМА USB ПРИСТРОЇ, ЩО КОЛИ-НЕБУДЬ БУЛИ ПІДКЛЮЧЕНІ")
            print("="*80)
            self.report_generator.print_table()
            self.report_generator.print_summary()
    
    def display_connected_devices(self):
        """Виводить поточно підключені USB пристрої"""
        connected = self.load_connected_devices()
        
        if connected:
            print("="*80)
            print("🔌 ПОТОЧНО ПІДКЛЮЧЕНІ USB ПРИСТРОЇ")
            print("="*80)
            for i, device in enumerate(connected, 1):
                print(f"{i}. {device.get('name', 'Unknown')}")
            print()
        else:
            print("❌ Немає активних USB пристроїв\n")
    
    def remove_device(self, device_id: str) -> bool:
        """Видаляє пристрій з реєстру"""
        print(f"\n⚠️ ВИДАЛЕННЯ ПРИСТРОЮ: {device_id}")
        
        device_info = next((d for d in self.devices if d['device_id'] == device_id), None)
        if device_info:
            print(f"📌 Назва: {device_info.get('friendly_name', 'N/A')}")
            print(f"📌 Виробник: {device_info.get('manufacturer', 'N/A')}")
            print(f"📌 Дата встановлення: {device_info.get('first_install_date', 'N/A')}")
        
        confirmation = input("\n⚠️ Ви впевнені? Введіть 'YES' для підтвердження: ")
        
        if confirmation.upper() == 'YES':
            return self.registry_handler.remove_device_from_registry(device_id)
        else:
            print("❌ Операція скасована\n")
            return False
    
    def export_report(self, filename: str):
        """Експортує звіт про пристрої"""
        if not self.devices:
            self.load_all_devices()
        
        if self.report_generator:
            self.report_generator.export_to_json(filename)
    
    def filter_devices(self, after_date: str = None, before_date: str = None) -> List[Dict]:
        """Фільтрує пристрої за датою"""
        if not self.devices:
            self.load_all_devices()
        
        if self.report_generator:
            filtered = self.report_generator.filter_by_date(after_date, before_date)
            print(f"\n📊 Знайдено {len(filtered)} пристроїв за критеріями")
            self.report_generator.print_table(filtered)
            return filtered
        
        return []
    
    def search_device(self, query: str) -> List[Dict]:
        """Шукає пристрій за назвою, ID або виробником"""
        if not self.devices:
            self.load_all_devices()
        
        query = query.lower()
        results = [d for d in self.devices 
                  if query in d.get('device_id', '').lower() or
                     query in d.get('friendly_name', '').lower() or
                     query in d.get('manufacturer', '').lower()]
        
        if results:
            print(f"\n🔍 Знайдено {len(results)} пристроїв за запитом '{query}'")
            if self.report_generator:
                self.report_generator.print_table(results)
        else:
            print(f"❌ Пристроїв за запитом '{query}' не знайдено\n")
        
        return results


def check_admin():
    """Перевіряє адміністраторські права"""
    try:
        import ctypes
        return ctypes.windll.shell.IsUserAnAdmin()
    except:
        return False


def print_header():
    """Виводить заголовок програми"""
    print(Fore.CYAN + "="*80)
    print(Fore.CYAN + "    🔌 USB DEVICE MANAGER - Менеджер USB Пристроїв 🔌")
    print(Fore.CYAN + "="*80 + Style.RESET_ALL)


def print_menu():
    """Виводить інтерактивне меню"""
    menu = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    📋 МЕНЮ USB DEVICE MANAGER                             ║
╠════════════════════════════════════════════════════════════════════════════╣
║ 1. 📋 Показати всі USB пристрої                                           ║
║ 2. 🔌 Показати підключені пристрої                                        ║
║ 3. 📊 Експортувати звіт (JSON)                                            ║
║ 4. 🔍 Пошук пристрою                                                      ║
║ 5. 🗑️  Видалити пристрій з реєстру                                        ║
║ 6. 📅 Фільтрування за датою                                               ║
║ 7. 📙 Довідка                                                             ║
║ 8. ❌ Вихід                                                               ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
    print(menu)


def print_help():
    """Виводить довідку"""
    help_text = """
🎯 ДОВІДКА ПО ВИКОРИСТАННЮ

📋 Команди командного рядка:
  python usb_device_manager.py --list-all          Показати всі USB пристрої
  python usb_device_manager.py --list-connected    Показати підключені пристрої
  python usb_device_manager.py --export FILE.json  Експортувати звіт
  python usb_device_manager.py --search "query"    Пошук пристрою
  python usb_device_manager.py --remove "DEVICE_ID" Видалити пристрій
  python usb_device_manager.py --after "2024-01-01" Фільтрування після дати
  python usb_device_manager.py --before "2024-12-31" Фільтрування до дати

⚠️  ВАЖЛИВО:
  - Потрібні АДМІНІСТРАТОРСЬКІ ПРАВА
  - Видалення пристроїв з реєстру є необоротною операцією
  - Рекомендується попередньо зробити резервну копію

🔧 ПРИКЛАДИ:
  # Експортувати всі пристрої в JSON
  python usb_device_manager.py --list-all --export devices.json

  # Показати пристрої встановлені після певної дати
  python usb_device_manager.py --list-all --after "2023-01-01"

  # Пошук пристроїв Kingston
  python usb_device_manager.py --search "Kingston"
"""
    print(help_text)


def interactive_mode(manager):
    """Інтерактивний режим роботи"""
    print_header()
    
    while True:
        print_menu()
        choice = input(Fore.YELLOW + "Виберіть опцію (1-8): " + Style.RESET_ALL).strip()
        
        if choice == '1':
            manager.display_all_devices()
        
        elif choice == '2':
            manager.display_connected_devices()
        
        elif choice == '3':
            filename = input("Введіть назву файлу для експорту (за замовченням: devices.json): ").strip()
            filename = filename or "devices.json"
            manager.export_report(filename)
            print()
        
        elif choice == '4':
            query = input("Введіть пошуковий запит: ").strip()
            if query:
                manager.search_device(query)
            else:
                print(Fore.RED + "❌ Пошуковий запит не може бути порожнім\n" + Style.RESET_ALL)
        
        elif choice == '5':
            manager.display_all_devices()
            device_id = input("\nВведіть ID пристрою для видалення: ").strip()
            if device_id:
                manager.remove_device(device_id)
                print()
            else:
                print(Fore.RED + "❌ ID пристрою не може бути порожнім\n" + Style.RESET_ALL)
        
        elif choice == '6':
            after = input("Введіть дату 'з' (YYYY-MM-DD) або залишіть порожним: ").strip()
            before = input("Введіть дату 'по' (YYYY-MM-DD) або залишіть порожним: ").strip()
            manager.filter_devices(after or None, before or None)
        
        elif choice == '7':
            print_help()
        
        elif choice == '8':
            print(Fore.GREEN + "👋 До побачення!" + Style.RESET_ALL)
            break
        
        else:
            print(Fore.RED + "❌ Невірна опція. Будь ласка, виберіть 1-8\n" + Style.RESET_ALL)
        
        if choice != '8':
            input(Fore.CYAN + "Натисніть Enter для продовження..." + Style.RESET_ALL)
            print()


def main():
    """Головна функція"""
    if not check_admin():
        print(Fore.RED + "❌ ПОМИЛКА: Програма потребує АДМІНІСТРАТОРСЬКИХ ПРАВ!")
        print(Fore.YELLOW + "⚠️  Будь ласка, запустіть утіліту як адміністратор." + Style.RESET_ALL)
        sys.exit(1)
    
    import argparse
    parser = argparse.ArgumentParser(
        description='USB Device Manager - Управління USB пристроями',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Приклади використання:
  python usb_device_manager.py --list-all
  python usb_device_manager.py --export devices.json
  python usb_device_manager.py --search "Kingston"
  python usb_device_manager.py --remove "VID_0951&PID_1625"
        """
    )
    
    parser.add_argument('--list-all', action='store_true', 
                       help='Показати всі USB пристрої')
    parser.add_argument('--list-connected', action='store_true',
                       help='Показати підключені USB пристрої')
    parser.add_argument('--export', metavar='FILE',
                       help='Експортувати звіт в JSON файл')
    parser.add_argument('--search', metavar='QUERY',
                       help='Пошук пристрою за назвою, ID або виробником')
    parser.add_argument('--remove', metavar='DEVICE_ID',
                       help='Видалити пристрій з реєстру')
    parser.add_argument('--after', metavar='DATE',
                       help='Фільтрування пристроїв після дати (YYYY-MM-DD)')
    parser.add_argument('--before', metavar='DATE',
                       help='Фільтрування пристроїв до дати (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    manager = USBManager()
    
    if args.list_all or args.list_connected or args.export or args.search or args.remove or args.after or args.before:
        print_header()
        
        if args.list_all:
            manager.display_all_devices()
        
        if args.list_connected:
            manager.display_connected_devices()
        
        if args.after or args.before:
            manager.filter_devices(args.after, args.before)
        
        if args.search:
            manager.search_device(args.search)
        
        if args.remove:
            manager.remove_device(args.remove)
        
        if args.export:
            manager.export_report(args.export)
    else:
        interactive_mode(manager)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n⚠️  Програма перервана користувачем" + Style.RESET_ALL)
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"\n❌ КРИТИЧНА ПОМИЛКА: {e}" + Style.RESET_ALL)
        import traceback
        traceback.print_exc()
        sys.exit(1)
