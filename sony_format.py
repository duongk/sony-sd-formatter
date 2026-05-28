import os
import sys
import platform
import shutil
import subprocess
import configparser
import re
import time
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QMessageBox, QFileDialog)

# --- THREAD-SAFE WORKER FOR DISK SCANNING ---
class DiskScanWorker(QThread):
    scan_complete = Signal(list)

    def __init__(self, current_os):
        super().__init__()
        self.current_os = current_os

    def run(self):
        drive_options = []
        try:
            if self.current_os == "Windows":
                cmd = ["powershell", "Get-Volume | Where-Object { $_.DriveType -eq 'Removable' } | ForEach-Object { $_.DriveLetter + ':  [' + $_.FileSystemLabel + ']' }"]
                output = subprocess.check_output(cmd, text=True)
                drive_options = [line.strip() for line in output.strip().split('\n') if line.strip()]
            else:
                full_list = subprocess.check_output(["/usr/sbin/diskutil", "list", "physical"], text=True)
                disks = sorted(list(set(re.findall(r"(/dev/disk\d+)", full_list))))
                for disk in disks:
                    if "disk0" in disk: 
                        continue
                    info = subprocess.check_output(["/usr/sbin/diskutil", "info", disk], text=True)
                    size = re.search(r"Disk Size:\s+([\d\.]+\s+\w+)", info)
                    name = re.search(r"Volume Name:\s+(.*)", info)
                    size_str = size.group(1) if size else "Unknown"
                    name_str = name.group(1).strip() if name else "Untitled"
                    drive_options.append(f"[{size_str}, {name_str}]  {disk}")
        except Exception as e:
            drive_options = [f"Error: {str(e)}"]

        self.scan_complete.emit(drive_options)


# --- THREAD-SAFE WORKER FOR THE FORMAT PROCESS ---
class FormatWorker(QThread):
    process_complete = Signal(str, bool)

    def __init__(self, current_os, selected_drive, card_name, media_type, local_lut_dir):
        super().__init__()
        self.current_os = current_os
        self.selected_drive = selected_drive
        self.card_name = card_name
        self.media_type = media_type
        self.local_lut_dir = local_lut_dir

    def run(self):
        msg_out = ""
        is_success = False
        try:
            if self.current_os == "Windows":
                drive_letter = self.selected_drive.split(":")[0].strip()
                mount_point = f"{drive_letter}:\\"
                cmd = f"powershell \"Format-Volume -DriveLetter {drive_letter} -FileSystem exFAT -NewFileSystemLabel {self.card_name} -Confirm:\$false\""
                subprocess.check_call(cmd, shell=True)
            else:
                # Extract the disk identifier
                disk_id = self.selected_drive.split("  ")[-1].replace("/dev/", "").strip()
                mount_point = f"/Volumes/{self.card_name}"

                app_title = "Sony Card Formatter Requires Admin Privileges"
                # We add a backslash before the internal quotes so Python passes literal \" to AppleScript
                # scpt = f'do shell script "diskutil eraseDisk ExFAT {self.card_name} MBR {disk_id}" with administrator privileges'
                scpt = f'do shell script "diskutil eraseDisk ExFAT {self.card_name} MBR {disk_id}" with administrator privileges with prompt "{app_title}"'
    
                process = subprocess.run(["/usr/bin/osascript", "-e", scpt], capture_output=True, text=True)
                if process.returncode != 0:
                    raise Exception(process.stderr.strip())

            time.sleep(3)
            
            if self.media_type == "SD Card":
                target_dir = os.path.join(mount_point, "Private", "Sony", "PRO", "LUT")
            else:
                target_dir = os.path.join(mount_point, "Sony", "PRO", "LUT")
                
            os.makedirs(target_dir, exist_ok=True)

            count = 0
            for root, _, files in os.walk(self.local_lut_dir):
                for f in files:
                    if f.lower().endswith(".cube"):
                        shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
                        count += 1
            msg_out = f"Formatted {self.card_name} and copied {count} LUTs!"
            is_success = True
        except Exception as e:
            msg_out = f"Operation failed:\n{str(e)}"

        self.process_complete.emit(msg_out, is_success)


# --- MAIN APPLICATION CLASS ---
class SonyFormatterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sony Card Formatter Utility")
        self.setFixedSize(520, 480) # Increased window height slightly to accommodate new options comfortably
        
        # --- OS Detection ---
        sys_type = platform.system().lower()
        sys_plat = sys.platform.lower()
        has_diskutil = os.path.exists("/usr/sbin/diskutil")
        if "darwin" in sys_plat or "darwin" in sys_type or has_diskutil:
            self.current_os = "Darwin"
        else:
            self.current_os = "Windows"

        if self.current_os == "Windows":
            self.user_docs = os.path.join(os.environ["USERPROFILE"], "Documents")
        else:
            self.user_docs = os.path.join(os.path.expanduser("~"), "Documents")
            
        # We start by initializing the app data directory inside Documents
        self.app_data_dir = os.path.join(self.user_docs, "SonyCardFormatter")
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.config_file = os.path.join(self.app_data_dir, "config.ini")
        
        self.load_configuration()
        self.init_ui()
        
        QTimer.singleShot(1000, self.scan_drives)

    def load_configuration(self):
        config = configparser.ConfigParser()
        default_lut_path = os.path.join(self.user_docs, "Camera_LUTs")

        if not os.path.exists(self.config_file):
            config['PATHS'] = {
                'source_lut_directory': default_lut_path,
                'config_save_directory': self.app_data_dir
            }
            config['SETTINGS'] = {'default_volume_name': 'CAM_A', 'default_media_type': 'SD Card'}
            with open(self.config_file, 'w') as cf:
                config.write(cf)
                
        config.read(self.config_file)
        self.local_lut_dir = config.get('PATHS', 'source_lut_directory', fallback=default_lut_path)
        self.app_data_dir = config.get('PATHS', 'config_save_directory', fallback=self.app_data_dir)
        self.config_file = os.path.join(self.app_data_dir, "config.ini") # update full path file reference
        
        self.default_name = config.get('SETTINGS', 'default_volume_name', fallback='CAM_A')
        self.default_media = config.get('SETTINGS', 'default_media_type', fallback='SD Card')
        
        os.makedirs(self.local_lut_dir, exist_ok=True)
        os.makedirs(self.app_data_dir, exist_ok=True)

    def save_configuration(self):
        """Saves current state path options down to the configuration file context."""
        config = configparser.ConfigParser()
        config['PATHS'] = {
            'source_lut_directory': self.ent_lut_dir.text(),
            'config_save_directory': self.app_data_dir
        }
        config['SETTINGS'] = {
            'default_volume_name': self.ent_name.text(),
            'default_media_type': self.cmb_type.currentText()
        }
        try:
            with open(self.config_file, 'w') as cf:
                config.write(cf)
        except Exception as e:
            QMessageBox.warning(self, "Config Error", f"Could not update settings file:\n{str(e)}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # 1. Volume Name Field
        layout.addWidget(QLabel("Custom Card Volume Name:"))
        self.ent_name = QLineEdit()
        self.ent_name.setText(self.default_name)
        self.ent_name.textChanged.connect(self.save_configuration)
        layout.addWidget(self.ent_name)

        # 2. Target Profile Layout
        layout.addWidget(QLabel("Select Media Target:"))
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["SD Card", "CFexpress Type A"])
        self.cmb_type.setCurrentText(self.default_media)
        self.cmb_type.currentTextChanged.connect(self.save_configuration)
        layout.addWidget(self.cmb_type)

        # NEW: Source LUT Folder Picker Layout
        layout.addWidget(QLabel("Look for LUT Files In (.cube):"))
        lut_dir_box = QHBoxLayout()
        self.ent_lut_dir = QLineEdit()
        self.ent_lut_dir.setText(self.local_lut_dir)
        self.ent_lut_dir.setReadOnly(True)
        lut_dir_box.addWidget(self.ent_lut_dir)
        self.btn_browse_lut = QPushButton("Browse...")
        self.btn_browse_lut.clicked.connect(self.browse_lut_directory)
        lut_dir_box.addWidget(self.btn_browse_lut)
        layout.addLayout(lut_dir_box)

        # NEW: Config Save Folder Picker Layout
        layout.addWidget(QLabel("Save config.ini File Directory:"))
        config_dir_box = QHBoxLayout()
        self.ent_config_dir = QLineEdit()
        self.ent_config_dir.setText(self.app_data_dir)
        self.ent_config_dir.setReadOnly(True)
        config_dir_box.addWidget(self.ent_config_dir)
        self.btn_browse_config = QPushButton("Browse...")
        self.btn_browse_config.clicked.connect(self.browse_config_directory)
        config_dir_box.addWidget(self.btn_browse_config)
        layout.addLayout(config_dir_box)

        # 3. Drive Dropdown Layout
        layout.addWidget(QLabel("Select Memory Card:"))
        drive_box = QHBoxLayout()
        self.cmb_drives = QComboBox()
        self.cmb_drives.addItem("Initializing program...")
        drive_box.addWidget(self.cmb_drives, stretch=1)
        
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedWidth(40)
        self.btn_refresh.clicked.connect(self.scan_drives)
        drive_box.addWidget(self.btn_refresh)
        layout.addLayout(drive_box)

        layout.addSpacing(15)

        # 4. Action Execution Run Button
        self.btn_run = QPushButton("FORMAT & LOAD LUTS")
        self.btn_run.setFixedHeight(40)
        self.btn_run.clicked.connect(self.execute_process)
        layout.addWidget(self.btn_run)

    def browse_lut_directory(self):
        """Opens native OS folder picker to choose where the program searches for lookups."""
        selected_dir = QFileDialog.getExistingDirectory(self, "Select LUT Source Directory", self.ent_lut_dir.text())
        if selected_dir:
            self.local_lut_dir = selected_dir
            self.ent_lut_dir.setText(selected_dir)
            self.save_configuration()

    def browse_config_directory(self):
        """Moves config.ini target tracking storage safely across physical directories."""
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Configuration Save Directory", self.ent_config_dir.text())
        if selected_dir:
            old_config_file = self.config_file
            
            # Reassign directory and config coordinates
            self.app_data_dir = selected_dir
            self.ent_config_dir.setText(selected_dir)
            self.config_file = os.path.join(selected_dir, "config.ini")
            
            # Immediately save state variables to the new path destination
            self.save_configuration()
            
            # Clean up old configuration file tracking block if it exists safely
            if old_config_file != self.config_file and os.path.exists(old_config_file):
                try:
                    os.remove(old_config_file)
                except Exception:
                    pass

    def scan_drives(self):
        self.btn_refresh.setEnabled(False)
        self.cmb_drives.clear()
        self.cmb_drives.addItem("Scanning system for drives...")
        
        self.scan_thread = DiskScanWorker(self.current_os)
        self.scan_thread.scan_complete.connect(self.update_drives_ui)
        self.scan_thread.start()

    @Slot(list)
    def update_drives_ui(self, options):
        self.cmb_drives.clear()
        self.btn_refresh.setEnabled(True)
        if not options:
            self.cmb_drives.addItem("No removable drives found")
        else:
            self.cmb_drives.addItems(options)

    def execute_process(self):
        selected = self.cmb_drives.currentText()
        if "No removable" in selected or "Scanning" in selected or "Initializing" in selected:
            QMessageBox.critical(self, "Selection Error", "Please select a valid drive.")
            return

        card_name = "".join(c for c in self.ent_name.text() if c.isalnum() or c == "_")
        if not card_name:
            QMessageBox.critical(self, "Name Error", "Please enter a valid name (A-Z, 0-9, _).")
            return

        reply = QMessageBox.question(self, "Confirm Format", f"WARNING: This will ERASE ALL DATA on:\n\n{selected}\n\nAre you sure?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        self.btn_run.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        
        self.format_thread = FormatWorker(
            self.current_os, selected, card_name, 
            self.cmb_type.currentText(), self.local_lut_dir
        )
        self.format_thread.process_complete.connect(self.post_execute_ui)
        self.format_thread.start()

    @Slot(str, bool)
    def post_execute_ui(self, message, success):
        self.btn_run.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
        self.scan_drives()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SonyFormatterApp()
    window.show()
    sys.exit(app.exec())