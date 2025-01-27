import sys
import serial
import serial.tools.list_ports
import time

import numpy as np

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QCheckBox,
                             QLineEdit, QMessageBox, QGroupBox, QFormLayout)
from PyQt5.QtGui import QIcon

# PyQtGraph
import pyqtgraph as pg

PROGRAM_VERSION = "1.10"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"pMMG Receiver v{PROGRAM_VERSION}")
        self.resize(1200, 700)

        # ----------- PyQtGraph 전역옵션 (최적화) -----------
        pg.setConfigOptions(
            antialias=False,       # 안티에일리싱 끔 (속도↑)
            useOpenGL=True,        # OpenGL 가속
            foreground='k',        # 라벨 색상 (검정)
            background='w'         # 배경 흰색
        )

        # 시리얼 및 데이터 관련 초기화
        self.serial_port = None
        self.is_reading = False          # 데이터 수신 중인지 여부
        self.rx_buffer = ""              # 누적 수신 버퍼
        self.max_time_ms = 10000         # 그래프 표시 최대 시간(10초)

        # 파일명 자동 관리용 변수
        self.lastBaseName = ""           # 이전에 사용한 파일 베이스이름
        self.lastFileIndex = 0           # 같은 베이스 이름일 때 파일 번호

        # 실시간 버퍼(리스트) - 10초 이상은 trimData()로 제거
        self.data_buffer = {
            'Time': [],
            'Pressure1': [],
            'Pressure2': [],
            'Pressure3': [],
            'Pressure4': [],
            'Pressure5': [],
            'Pressure6': [],
            'Pressure7': [],
            'Pressure8': [],
            'FSR_L': [],
            'FSR_R': []
        }

        # GUI 초기화
        self._initUI()

        # 시리얼 포트 연결 시도
        self._connectSerial()

        # 그래프 갱신용 타이머 (50ms)
        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(50)
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start()

        # 시리얼 읽기용 타이머 (5ms)
        self.read_timer = QTimer(self)
        self.read_timer.setInterval(5)
        self.read_timer.timeout.connect(self.read_data)

    def _initUI(self):
        """GUI 구성"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # ----------- (좌) PyQtGraph Plot 영역 ------------
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Pressure / FSR')
        self.plot_widget.setLabel('bottom', 'Time [ms]')
        self.plot_widget.setTitle('Real-Time Plot')
        self.plot_widget.addLegend()  # 범례
        self.plot_widget.showGrid(x=True, y=True, alpha=0.4)
        main_layout.addWidget(self.plot_widget, stretch=7)

        # 커브(곡선)들 저장할 딕셔너리
        self.curves = {}

        # 데이터 이름/색상/범례표기
        self.plot_config = {
            'Pressure1': ('pMMG1', 'b'),
            'Pressure2': ('pMMG2', 'orange'),
            'Pressure3': ('pMMG3', 'yellow'),
            'Pressure4': ('pMMG4', 'g'),
            'Pressure5': ('pMMG5', 'blue'),
            'Pressure6': ('pMMG6', 'indigo'),
            'Pressure7': ('pMMG7', 'violet'),
            'Pressure8': ('pMMG8', 'brown'),
            'FSR_L'    : ('FSR_L', 'lightblue'),
            'FSR_R'    : ('FSR_R', 'lime'),
        }

        # PlotItem에 커브 생성 (초기에 빈 데이터)
        for key, (label, color) in self.plot_config.items():
            pen = pg.mkPen(color=color, width=1)
            curve = self.plot_widget.plot(name=label, pen=pen)
            curve.setData([], [])
            self.curves[key] = curve

        # ----------- (우) 설정/버튼 영역 ------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(20)
        main_layout.addWidget(right_widget, stretch=3)

        # (1) 체크박스 구역
        checkbox_group = QGroupBox("Select Data to Plot")
        form_chk_layout = QFormLayout(checkbox_group)
        self.checkbox_list = {}

        for key, (label_text, _) in self.plot_config.items():
            cb = QCheckBox(label_text)
            cb.setChecked(True)  # 초기에는 전부 표시
            self.checkbox_list[key] = cb
            form_chk_layout.addRow(cb)

        right_layout.addWidget(checkbox_group)

        # (2) 파일명 입력 구역 (확장자 .txt는 자동으로 붙을 예정)
        file_group = QGroupBox("Output File Name (base)")
        file_layout = QVBoxLayout(file_group)
        self.file_edit = QLineEdit()
        self.file_edit.setText("dataFile")  # 예시 기본값
        file_layout.addWidget(self.file_edit)
        right_layout.addWidget(file_group)

        # (3) 상태 표시 + 버튼 구역
        self.label_state = QLabel("Not connected")
        self.label_state.setStyleSheet("font-weight: bold; color: red;")

        self.btn_start = QPushButton("Start Reading")
        self.btn_start.clicked.connect(self.toggle_reading)

        right_layout.addWidget(self.label_state, alignment=Qt.AlignCenter)
        right_layout.addWidget(self.btn_start)

    def _connectSerial(self):
        """STMicroelectronics로 표시되는 COM 포트를 자동 검색 후 연결 시도"""
        ports = serial.tools.list_ports.comports()
        stm_port = None
        for port in ports:
            if port.manufacturer and "STMicroelectronics" in port.manufacturer:
                stm_port = port.device
                break

        if stm_port:
            try:
                self.serial_port = serial.Serial(stm_port, 921600, timeout=0.1)
                self.label_state.setText("Connected")
                self.label_state.setStyleSheet("font-weight: bold; color: green;")
            except serial.SerialException as e:
                QMessageBox.critical(self, "Serial Error", str(e))
                self.serial_port = None
                self.label_state.setText("Not connected")
                self.label_state.setStyleSheet("font-weight: bold; color: red;")
        else:
            self.serial_port = None
            self.label_state.setText("Not connected")
            self.label_state.setStyleSheet("font-weight: bold; color: red;")

    def toggle_reading(self):
        """Start/Stop Reading 버튼 클릭 시 동작"""
        if not self.serial_port:
            QMessageBox.warning(self, "Warning", "Serial port not connected!")
            return

        if not self.is_reading:
            # --- Start Reading ---
            base_name = self.file_edit.text().strip()
            if not base_name:
                QMessageBox.warning(self, "Warning", "파일 베이스 이름을 입력하세요.")
                return

            # 만약 이전 베이스이름과 다르면 인덱스 리셋
            if base_name != self.lastBaseName:
                self.lastBaseName = base_name
                self.lastFileIndex = 0

            # 파일 인덱스 증가
            self.lastFileIndex += 1
            # 파일명은 baseName_XX.txt 형태 (XX는 2자리)
            filename = f"{self.lastBaseName}_{self.lastFileIndex:02d}.txt"

            try:
                self.file_obj = open(filename, mode='w', encoding='utf-8')
                header = ("Time[ms],Pressure1[kPa],Pressure2[kPa],Pressure3[kPa],"
                          "Pressure4[kPa],Pressure5[kPa],Pressure6[kPa],Pressure7[kPa],"
                          "Pressure8[kPa],FSR_L,FSR_R\n")
                self.file_obj.write(header)
            except Exception as e:
                QMessageBox.critical(self, "File Error", str(e))
                return

            # 새 측정이므로 데이터 버퍼/그래프 리셋
            for key in self.data_buffer:
                self.data_buffer[key].clear()

            # 상태 및 버튼 표시 변경
            self.is_reading = True
            self.label_state.setText("Reading")
            self.label_state.setStyleSheet("font-weight: bold; color: blue;")
            self.btn_start.setText("Stop Reading")

            # 시리얼 리드 타이머 시작
            self.read_timer.start()

        else:
            # --- Stop Reading ---
            self.is_reading = False
            self.label_state.setText("Connected")
            self.label_state.setStyleSheet("font-weight: bold; color: green;")
            self.btn_start.setText("Start Reading")

            # 파일 닫기
            if hasattr(self, 'file_obj'):
                self.file_obj.close()

            # 리드 타이머 정지
            self.read_timer.stop()

    def read_data(self):
        """시리얼 버퍼에 있는 모든 데이터 읽은 뒤 줄 단위로 파싱"""
        if not self.serial_port or not self.is_reading:
            return

        data_bytes = self.serial_port.read_all()
        if not data_bytes:
            return

        self.rx_buffer += data_bytes.decode('utf-8', errors='ignore')

        # 줄 단위로 분할
        lines = self.rx_buffer.split('\n')
        # 마지막 줄은 완성되지 않았을 수 있으므로 버퍼에 보존
        self.rx_buffer = lines.pop(-1)

        for line in lines:
            line = line.strip()
            if not line:
                continue
            data_list = line.split(',')
            if len(data_list) >= 11:
                try:
                    # float 변환
                    time_val   = float(data_list[0].strip())
                    p1_val     = float(data_list[1].strip())
                    p2_val     = float(data_list[2].strip())
                    p3_val     = float(data_list[3].strip())
                    p4_val     = float(data_list[4].strip())
                    p5_val     = float(data_list[5].strip())
                    p6_val     = float(data_list[6].strip())
                    p7_val     = float(data_list[7].strip())
                    p8_val     = float(data_list[8].strip())
                    fsr_l_val  = float(data_list[9].strip())
                    fsr_r_val  = float(data_list[10].strip())

                    # 버퍼에 저장
                    self.data_buffer['Time'].append(time_val)
                    self.data_buffer['Pressure1'].append(p1_val)
                    self.data_buffer['Pressure2'].append(p2_val)
                    self.data_buffer['Pressure3'].append(p3_val)
                    self.data_buffer['Pressure4'].append(p4_val)
                    self.data_buffer['Pressure5'].append(p5_val)
                    self.data_buffer['Pressure6'].append(p6_val)
                    self.data_buffer['Pressure7'].append(p7_val)
                    self.data_buffer['Pressure8'].append(p8_val)
                    self.data_buffer['FSR_L'].append(fsr_l_val)
                    self.data_buffer['FSR_R'].append(fsr_r_val)

                    # 파일에 저장
                    if hasattr(self, 'file_obj'):
                        save_str = (f"{time_val},{p1_val},{p2_val},{p3_val},"
                                    f"{p4_val},{p5_val},{p6_val},{p7_val},"
                                    f"{p8_val},{fsr_l_val},{fsr_r_val}\n")
                        self.file_obj.write(save_str)

                    # 10초 범위를 넘으면 앞부분 제거
                    self._trimData(time_val)

                except ValueError:
                    print(f"Value Error in parsing line: {line}")
            else:
                print(f"Incomplete data: {line}")

    def _trimData(self, current_time_ms):
        """현재 시간이 max_time_ms(기본 10초)를 넘으면 앞부분 데이터를 버림"""
        threshold = current_time_ms - self.max_time_ms
        if threshold < 0:
            return

        time_list = self.data_buffer['Time']
        keep_index = 0
        for i, t in enumerate(time_list):
            if t >= threshold:
                keep_index = i
                break

        if keep_index > 0:
            for key in self.data_buffer:
                self.data_buffer[key] = self.data_buffer[key][keep_index:]

    def update_plot(self):
        """50ms마다 그래프 갱신"""
        if not self.data_buffer['Time']:
            return

        time_vals = np.array(self.data_buffer['Time'], dtype=float)

        # X축 범위 설정 (10초)
        x_min = max(0, time_vals[-1] - self.max_time_ms)
        x_max = max(time_vals[-1], 10)
        self.plot_widget.setXRange(x_min, x_max, padding=0)

        # 체크박스 상태에 따라 곡선 업데이트
        for key in self.curves:
            if self.checkbox_list[key].isChecked():
                y_vals = np.array(self.data_buffer[key], dtype=float)
                # downsample 제거, skipFiniteCheck만 True로 속도 최적화
                self.curves[key].setData(time_vals, y_vals, skipFiniteCheck=True)
            else:
                self.curves[key].setData([], [])

    def closeEvent(self, event):
        """윈도우 종료 시 자원 정리"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        if hasattr(self, 'file_obj') and not self.file_obj.closed:
            self.file_obj.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
