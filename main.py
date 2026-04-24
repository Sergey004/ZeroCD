#!/usr/bin/env python3
"""
ZeroCD - DIY USB CD-ROM and LAN adapter for Raspberry Pi Zero 2 W
"""

import signal
import sys
import os
import subprocess

from config import ISO_DIR, BACKLIGHT_TIMEOUT_SECONDS, BACKLIGHT_FADE_STEPS, BACKLIGHT_FADE_STEP_MS
from system.logger import setup_logger, get_logger

from ui.display import Display
from ui.menu import Menu
from input.joystick import Joystick, Direction
from usb.iso_manager import ISOManager
from net.wifi import WiFiManager
from usb.gadget import GadgetManager
from usb.image_creator import ImageCreator


class ZeroCDApp:
    def __init__(self):
        self.logger = get_logger("main")
        self.display = None
        self.joystick = None
        self.gadget = None
        self.iso_manager = None
        self.menu = None
        self.wifi = None

        self.iso_list = []
        self.active_iso = None
        self.wifi_enabled = False
        self.usb_connected = False
        self.mtp_enabled = False
        self.running = False
        self.last_activity_time = None
        self.backlight_on = True
        self.in_create_img = False

    def init(self) -> bool:
        self.logger.info("Initializing ZeroCD")
        setup_logger()

        self.iso_manager = ISOManager(ISO_DIR)
        self.iso_list = self.iso_manager.list_isos()
        self.logger.info(f"Found {len(self.iso_list)} ISO files")

        self.display = Display()
        if not self.display.init():
            self.logger.error("Failed to initialize display")
            return False

        self.joystick = Joystick(disp=self.display, callback=self.on_joystick_event)

        if hasattr(self.display, 'GPIO_KEY1_PIN') and self.display.GPIO_KEY1_PIN:
            self.display.GPIO_KEY1_PIN.when_pressed = self.on_key1_event

        self.gadget = GadgetManager()
        if not self.gadget.init():
            self.logger.error("Failed to initialize USB gadget - continuing without USB support")
        else:
            self.logger.info("USB gadget initialized, binding to UDC...")
            if self.gadget.bind():
                self.usb_connected = True
                self.logger.info("USB gadget bound to UDC")
            else:
                self.logger.error("Failed to bind USB gadget to UDC")

        self.display.show_splash()

        self.last_activity_time = self.get_time()
        self.backlight_on = True
        self.display.fade_in(target_duty=50, steps=BACKLIGHT_FADE_STEPS, step_delay_ms=BACKLIGHT_FADE_STEP_MS)

        self.menu = Menu(self.iso_list, self.on_iso_selected)
        if self.iso_list:
            self.active_iso = self.iso_list[0]

        self.wifi = WiFiManager()

        self.logger.info("ZeroCD initialization complete")

        if self.iso_list:
            self.on_iso_selected(self.iso_list[0])

        try:
            import threading
            from web.server import start_webui
            web_thread = threading.Thread(target=start_webui, args=(self,), daemon=True)
            web_thread.start()
            self.logger.info("WebUI background thread started")
        except Exception as e:
            self.logger.error(f"Failed to start WebUI: {e}")

        return True


    def on_iso_selected(self, iso_name: str):
        self.logger.info(f"User selected ISO: {iso_name}")
        iso_path = self.iso_manager.get_iso_path(iso_name)
        if iso_path and self.gadget:
            self.gadget.set_iso(iso_path)
            self.active_iso = iso_name
            self.update_display()

    def on_joystick_event(self, direction: Direction):
        if self.in_create_img:
            self._handle_create_img_input(direction)
            self.update_display()
            self.reset_activity()
            return

        if direction == Direction.UP:
            if self.menu:
                self.menu.prev()
        elif direction == Direction.DOWN:
            if self.menu:
                self.menu.next()
        elif direction == Direction.PRESS:
            self.logger.info("Центральная кнопка нажата — Выбор образа")
            if self.menu:
                self.menu.select()
        elif direction == Direction.RIGHT:
            self.toggle_wifi()
        elif direction == Direction.LEFT:
            self.toggle_mtp()

        self.update_display()
        self.reset_activity()

    def on_key1_event(self):
        self.logger.info("Key1 pressed — entering Create IMG menu")
        if self.menu:
            self.menu.enter_create_img()
            self.in_create_img = True
            self.update_display()
            self.reset_activity()

    def _handle_create_img_input(self, direction: Direction):
        if not self.menu:
            return

        if direction == Direction.UP:
            self.menu.prev()
        elif direction == Direction.DOWN:
            self.menu.next()
        elif direction == Direction.LEFT:
            self.logger.info("Exiting Create IMG menu")
            self.menu.exit_create_img()
            self.in_create_img = False
        elif direction == Direction.PRESS:
            size_mb = self.menu.get_create_img_mb()
            if size_mb > 0:
                self.logger.info(f"Creating IMG: {size_mb}MB")
                name = self.iso_manager.get_next_disk_name()
                result = self.iso_manager.create_image(name, size_mb)
                if result:
                    self.logger.info(f"IMG created: {result}")
                    self.iso_list = self.iso_manager.list_isos()
                    self.menu = Menu(self.iso_list, self.on_iso_selected)
                else:
                    self.logger.error("Failed to create IMG")
                self.menu.exit_create_img()
                self.in_create_img = False

    def reset_activity(self):
        """Reset activity timer and turn on backlight if needed."""
        self.last_activity_time = self.get_time()
        if not self.backlight_on:
            self.backlight_on = True
            self.display.fade_in(target_duty=50, steps=BACKLIGHT_FADE_STEPS, step_delay_ms=BACKLIGHT_FADE_STEP_MS)

    def get_time(self):
        """Get current time in seconds."""
        import time
        return time.time()

    def check_backlight_timeout(self):
        """Check and handle backlight timeout."""
        if not self.backlight_on:
            return
        elapsed = self.get_time() - self.last_activity_time
        if elapsed >= BACKLIGHT_TIMEOUT_SECONDS:
            self.backlight_on = False
            self.display.fade_out(steps=BACKLIGHT_FADE_STEPS, step_delay_ms=BACKLIGHT_FADE_STEP_MS)

    def toggle_wifi(self):
        self.logger.info("WiFi toggle requested")

        if not hasattr(self, 'wifi') or not self.wifi.has_wifi_support():
            self.logger.warning("No WiFi hardware available to toggle.")
            return

        try:
            from net.wifi import WiFiState

            current_state = self.wifi.get_status()

            if current_state == WiFiState.CONNECTED:
                self.logger.info("WiFi is connected. Disconnecting...")
                self.wifi.disconnect()
            elif current_state in (WiFiState.OFF, WiFiState.ERROR):
                self.logger.info("WiFi is disconnected. Connecting...")
                self.wifi.connect()
            elif current_state == WiFiState.AP_MODE:
                self.logger.info("WiFi is in AP mode. Stopping AP and connecting to network...")
                self.wifi.stop_ap_mode()
                self.wifi.connect()
            else:
                self.logger.info(f"WiFi is currently {current_state.value}. Please wait.")

        except Exception as e:
            self.logger.error(f"Error toggling WiFi: {e}")

    def toggle_mtp(self):
        self.logger.info("MTP toggle requested")

        MTP_COMMAND = "umtprd"

        if not self.mtp_enabled:
            self.logger.info("Switching to MTP mode...")

            if self.gadget:
                self.gadget.shutdown()
                self.usb_connected = False

            import time
            time.sleep(0.5)

            self.logger.info("Setting up MTP USB Gadget...")
            os.system("sudo mkdir -p /sys/kernel/config/usb_gadget/mtp")
            os.system("sudo sh -c 'echo 0x1D6B > /sys/kernel/config/usb_gadget/mtp/idVendor'")
            os.system("sudo sh -c 'echo 0x0100 > /sys/kernel/config/usb_gadget/mtp/idProduct'")

            os.system("sudo mkdir -p /sys/kernel/config/usb_gadget/mtp/strings/0x409")
            os.system("sudo sh -c 'echo \"ZeroCD\" > /sys/kernel/config/usb_gadget/mtp/strings/0x409/manufacturer'")
            os.system("sudo sh -c 'echo \"ZeroCD MTP\" > /sys/kernel/config/usb_gadget/mtp/strings/0x409/product'")

            os.system("sudo mkdir -p /sys/kernel/config/usb_gadget/mtp/configs/c.1/strings/0x409")
            os.system("sudo sh -c 'echo \"MTP\" > /sys/kernel/config/usb_gadget/mtp/configs/c.1/strings/0x409/configuration'")

            os.system("sudo mkdir -p /sys/kernel/config/usb_gadget/mtp/functions/ffs.mtp")
            os.system("sudo ln -s /sys/kernel/config/usb_gadget/mtp/functions/ffs.mtp /sys/kernel/config/usb_gadget/mtp/configs/c.1/")

            os.system("sudo mkdir -p /dev/ffs-mtp")
            os.system("sudo mount -t functionfs mtp /dev/ffs-mtp")

            try:
                self.mtp_process = subprocess.Popen(["sudo", MTP_COMMAND])
                self.mtp_enabled = True
                self.logger.info("uMTP-Responder started. Waiting for endpoints...")

                time.sleep(1)

                udc_list = os.listdir("/sys/class/udc/")
                if udc_list:
                    udc = udc_list[0]
                    os.system(f"sudo sh -c 'echo {udc} > /sys/kernel/config/usb_gadget/mtp/UDC'")
                    self.logger.info(f"MTP connected to USB ({udc})")

            except Exception as e:
                self.logger.error(f"Failed to start MTP: {e}")
                self.mtp_enabled = False

        else:
            self.logger.info("Stopping MTP mode and restoring CD-ROM...")

            os.system("sudo sh -c 'echo \"\n\" > /sys/kernel/config/usb_gadget/mtp/UDC'")
            import time
            time.sleep(0.5)

            if hasattr(self, 'mtp_process') and self.mtp_process:
                self.mtp_process.terminate()
                os.system(f"sudo pkill -9 {MTP_COMMAND}")
                self.mtp_enabled = False

            os.system("sudo umount /dev/ffs-mtp")
            os.system("sudo rm /sys/kernel/config/usb_gadget/mtp/configs/c.1/ffs.mtp")
            os.system("sudo rmdir /sys/kernel/config/usb_gadget/mtp/configs/c.1/strings/0x409")
            os.system("sudo rmdir /sys/kernel/config/usb_gadget/mtp/configs/c.1")
            os.system("sudo rmdir /sys/kernel/config/usb_gadget/mtp/functions/ffs.mtp")
            os.system("sudo rmdir /sys/kernel/config/usb_gadget/mtp/strings/0x409")
            os.system("sudo rmdir /sys/kernel/config/usb_gadget/mtp")

            time.sleep(0.5)

            if self.gadget:
                if self.gadget.init():
                    if self.gadget.bind():
                        self.usb_connected = True

            self.logger.info("Refreshing ISO list after MTP session...")
            self.iso_list = self.iso_manager.list_isos()
            self.logger.info(f"Found {len(self.iso_list)} ISO files")

            self.menu = Menu(self.iso_list, self.on_iso_selected)

            if self.active_iso not in self.iso_list:
                self.logger.info("Previous active ISO was removed or renamed.")
                self.active_iso = self.iso_list[0] if self.iso_list else None

            if self.active_iso and self.usb_connected:
                iso_path = self.iso_manager.get_iso_path(self.active_iso)
                if iso_path:
                    self.gadget.set_iso(iso_path)

            self.update_display()
            self.logger.info("CD-ROM mode restored successfully")

    def update_display(self):
        if not self.display:
            return

        if self.in_create_img and self.menu:
            self.display.draw_create_img_menu(
                items=self.menu.get_visible_items(),
                selected_index=self.menu.get_index(),
                scroll_offset=self.menu.get_scroll_offset(),
                free_space_mb=self.iso_manager.get_available_space_mb()
            )
        else:
            self.display.draw_menu(
                items=self.menu.get_visible_items() if self.menu else [],
                selected_index=self.menu.get_index() if self.menu else 0,
                scroll_offset=self.menu.get_scroll_offset() if self.menu else 0,
                active_iso=self.active_iso,
                wifi_on=self.wifi.is_connected() if self.wifi else False,
                usb_bound=self.usb_connected,
                mtp_on=self.mtp_enabled
            )
        if hasattr(self.display, 'update'):
            self.display.update()

    def run(self):
        self.running = True
        self.logger.info("Starting ZeroCD main loop")

        try:
            self.joystick.start_polling(self.on_joystick_event)
            self.logger.info("Joystick polling started")
        except Exception as e:
            self.logger.warning(f"Joystick not available: {e}, USB CD-ROM mode only")

        self.update_display()
        self._run_pi_loop()

    def _run_pi_loop(self):
        """Pi mode: check backlight timeout."""
        import time
        while self.running:
            self.check_backlight_timeout()
            time.sleep(0.5)

    def shutdown(self):
        self.logger.info("Shutting down ZeroCD")
        self.running = False

        if self.joystick:
            self.joystick.stop()

        if self.gadget:
            self.gadget.shutdown()

        if self.wifi and self.wifi_enabled:
            self.wifi.disable()

        if self.display:
            self.display.close()

        self.logger.info("ZeroCD shutdown complete")


def main():
    def signal_handler(signum, frame):
        app = globals().get('app')
        if app:
            app.logger.info(f"Received signal {signum}")
            app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    global app
    app = ZeroCDApp()
    if app.init():
        app.run()
    else:
        app.logger.error("Failed to initialize ZeroCD")
        sys.exit(1)


if __name__ == "__main__":
    main()