import os
import time
from system.logger import get_logger

class GadgetBuilder:
    def __init__(self, gadget_name="zerocd", config_name="c.1"):
        self.logger = get_logger("usb_builder")
        self.gadget_name = gadget_name
        self.config_name = config_name

    def write_file(self, path: str, content: str):
        for attempt in range(3):
            try:
                with open(path, 'w') as f: f.write(content)
                return
            except OSError as e:
                if e.errno == 16 and attempt < 2: time.sleep(0.5)
                else: raise

    def cleanup(self):
        gadget_path = f"/sys/kernel/config/usb_gadget/{self.gadget_name}"
        if not os.path.exists(gadget_path): return True
        
        try:
            with open(f"{gadget_path}/UDC", 'w') as f: f.write("\n")
            time.sleep(0.5)
        except: pass

        config_path = f"{gadget_path}/configs/{self.config_name}"
        if os.path.exists(config_path):
            try:
                for item in os.listdir(config_path):
                    ipath = os.path.join(config_path, item)
                    if os.path.islink(ipath): os.unlink(ipath)
                if os.path.exists(f"{config_path}/strings/0x409"): os.rmdir(f"{config_path}/strings/0x409")
                os.rmdir(config_path)
            except: pass

        func_path = f"{gadget_path}/functions"
        if os.path.exists(func_path):
            for item in os.listdir(func_path):
                fp = f"{func_path}/{item}"
                try:
                    if 'mass_storage' in item and 'lun.0' in os.listdir(fp):
                        with open(f"{fp}/lun.0/file", 'w') as f: f.write('\n')
                    os.rmdir(fp)
                except: pass

        for p in[f"{gadget_path}/os_desc/c.1", f"{gadget_path}/strings/0x409", gadget_path]:
            try: os.unlink(p) if os.path.islink(p) else os.rmdir(p)
            except: pass

    def build(self, net_mgr, is_cdrom=True, pure_mode=False, apple_mode=False, network_first=False):
        self.cleanup()
        time.sleep(0.5)
        
        gp = f'/sys/kernel/config/usb_gadget/{self.gadget_name}'
        cp = f'{gp}/configs/{self.config_name}'
        os.makedirs(gp, exist_ok=True)

        self.write_file(f'{gp}/bcdDevice', '0x0100')
        self.write_file(f'{gp}/bcdUSB', '0x0200')

        if apple_mode:
            self.write_file(f'{gp}/idVendor', '0x05ac')  
            self.write_file(f'{gp}/idProduct', '0x1500') 
            self.write_file(f'{gp}/bDeviceClass', '0x00')
            self.write_file(f'{gp}/bDeviceSubClass', '0x00')
            self.write_file(f'{gp}/bDeviceProtocol', '0x00')
            mfg, prod, stall = 'Apple Inc.', 'Apple USB SuperDrive', '0'
        elif pure_mode:
            self.write_file(f'{gp}/idVendor', '0x1d6b')  
            self.write_file(f'{gp}/idProduct', '0x0104') 
            self.write_file(f'{gp}/bDeviceClass', '0x00')
            self.write_file(f'{gp}/bDeviceSubClass', '0x00')
            self.write_file(f'{gp}/bDeviceProtocol', '0x00')
            mfg, prod, stall = 'Generic', 'USB Optical Drive', '0'
        else:
            self.write_file(f'{gp}/idVendor', '0x1d6b')
            self.write_file(f'{gp}/idProduct', '0x0112') # Меняем, чтобы обновить кэш Windows
            self.write_file(f'{gp}/bDeviceClass', '0xEF')
            self.write_file(f'{gp}/bDeviceSubClass', '0x02')
            self.write_file(f'{gp}/bDeviceProtocol', '0x01')
            self.write_file(f'{gp}/os_desc/use', '1')
            self.write_file(f'{gp}/os_desc/b_vendor_code', '0xcd')
            self.write_file(f'{gp}/os_desc/qw_sign', 'MSFT100')
            mfg, prod, stall = 'ZeroCD', 'ZeroCD + LAN', '1'

        os.makedirs(f'{gp}/strings/0x409', exist_ok=True)
        self.write_file(f'{gp}/strings/0x409/manufacturer', mfg)
        self.write_file(f'{gp}/strings/0x409/product', prod)
        self.write_file(f'{gp}/strings/0x409/serialnumber', net_mgr.serial)

        os.makedirs(cp, exist_ok=True)
        os.makedirs(f'{cp}/strings/0x409', exist_ok=True)
        self.write_file(f'{cp}/strings/0x409/configuration', 'Storage Only' if (pure_mode or apple_mode) else 'CD-ROM + LAN')
        self.write_file(f'{cp}/MaxPower', '250')

        # Подготовка Storage
        ms_path = f'{gp}/functions/mass_storage.usb0'
        os.makedirs(ms_path, exist_ok=True)
        time.sleep(0.1)
        self.write_file(f'{ms_path}/stall', stall)
        
        lun0 = f'{ms_path}/lun.0'
        os.makedirs(lun0, exist_ok=True)
        time.sleep(0.2)
        self.write_file(f'{lun0}/removable', '1' if is_cdrom else '0')
        self.write_file(f'{lun0}/ro', '1' if is_cdrom else '0')
        self.write_file(f'{lun0}/cdrom', '1' if is_cdrom else '0')
        self.write_file(f'{lun0}/nofua', '0' if is_cdrom else '1')
        inquiry = 'Apple   SuperDrive Drive' if apple_mode else ('ZeroCD  CD-ROM' if is_cdrom else 'ZeroCD  Flash Drive')
        self.write_file(f'{lun0}/inquiry_string', inquiry)

        # Подготовка Network
        rndis_path = f'{gp}/functions/rndis.usb0'
        ecm_path = f'{gp}/functions/ecm.usb0'
        
        if not pure_mode and not apple_mode:
            os.makedirs(rndis_path, exist_ok=True)
            self.write_file(f'{rndis_path}/host_addr', net_mgr.host_mac_rndis)
            self.write_file(f'{rndis_path}/dev_addr', net_mgr.dev_mac_rndis)
            os.makedirs(f'{rndis_path}/os_desc/interface.rndis', exist_ok=True)
            self.write_file(f'{rndis_path}/os_desc/interface.rndis/compatible_id', 'RNDIS')
            self.write_file(f'{rndis_path}/os_desc/interface.rndis/sub_compatible_id', '5162001')

            os.makedirs(ecm_path, exist_ok=True)
            self.write_file(f'{ecm_path}/host_addr', net_mgr.host_mac_ecm)
            self.write_file(f'{ecm_path}/dev_addr', net_mgr.dev_mac_ecm)

        # === ТОТ САМЫЙ ПОРЯДОК ИНТЕРФЕЙСОВ ===
        if pure_mode or apple_mode:
            os.symlink(ms_path, f'{cp}/mass_storage.usb0')
        else:
            if network_first:
                self.logger.info("Linking order: NETWORK FIRST (Optimized for Windows RNDIS)")
                os.symlink(rndis_path, f'{cp}/rndis.usb0')
                os.symlink(ecm_path, f'{cp}/ecm.usb0')
                os.symlink(ms_path, f'{cp}/mass_storage.usb0')
            else:
                self.logger.info("Linking order: STORAGE FIRST (Optimized for BIOS Booting)")
                os.symlink(ms_path, f'{cp}/mass_storage.usb0')
                os.symlink(rndis_path, f'{cp}/rndis.usb0')
                os.symlink(ecm_path, f'{cp}/ecm.usb0')
            
            try: os.symlink(cp, f'{gp}/os_desc/c.1')
            except: pass
            
        return True