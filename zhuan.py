import sys
import math
import time
import random
import collections 
from mcrcon import MCRcon
from PIL import Image
import pywavefront
import socket 

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QFormLayout, QLineEdit, QPushButton, QTextEdit,
                             QMessageBox, QFileDialog, QComboBox, QLabel, QGridLayout, QCheckBox) 
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPainter, QColor

# --- 方块与颜色的映射 ---
MINECRAFT_BLOCKS = {
    "minecraft:stone": (125, 125, 125), "minecraft:dirt": (133, 96, 66),
    "minecraft:oak_planks": (162, 130, 78), "minecraft:cobblestone": (123, 123, 123),
    "minecraft:sand": (217, 210, 158), "minecraft:gravel": (134, 130, 126),
    "minecraft:gold_block": (249, 236, 76), "minecraft:iron_block": (230, 230, 230),
    "minecraft:diamond_block": (99, 241, 226), "minecraft:emerald_block": (82, 213, 116),
    "minecraft:redstone_block": (255, 0, 0), "minecraft:lapis_block": (35, 71, 142),
    "minecraft:coal_block": (13, 13, 13), "minecraft:white_wool": (234, 234, 234),
    "minecraft:orange_wool": (240, 118, 19), "minecraft:magenta_wool": (189, 73, 189),
    "minecraft:light_blue_wool": (58, 175, 217), "minecraft:yellow_wool": (254, 216, 61),
    "minecraft:lime_wool": (128, 199, 31), "minecraft:pink_wool": (237, 141, 172),
    "minecraft:gray_wool": (62, 68, 71), "minecraft:light_gray_wool": (142, 142, 134),
    "minecraft:cyan_wool": (21, 137, 145), "minecraft:purple_wool": (126, 61, 181),
    "minecraft:blue_wool": (45, 52, 143), "minecraft:brown_wool": (114, 71, 41),
    "minecraft:green_wool": (94, 124, 22), "minecraft:black_wool": (21, 21, 25),
}
# --- 辅助函数：找到最接近的方块颜色 ---
def find_closest_block(rgb_tuple):
    min_dist, closest_block_name = float('inf'), ""
    r1, g1, b1 = rgb_tuple
    for name, color_tuple in MINECRAFT_BLOCKS.items():
        r2, g2, b2 = color_tuple; dist = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
        if dist < min_dist: min_dist, closest_block_name = dist, name
    return closest_block_name, QColor(*MINECRAFT_BLOCKS[closest_block_name])


# --- AFDC 核心处理函数 (新增) ---
def process_afdc_hollowing(voxels, entry_point):
    """
    基于 3D BFS 的流体动力学空心化分析。
    模拟空气从入口点流入，移除所有非承重的内部体素，只保留外壳和结构。
    """
    if not voxels: 
        return set()
    
    
    if entry_point in voxels:
        print("AFDC 警告：入口点位于实体体素内，跳过空心化。")
        return voxels

    
    queue = collections.deque([entry_point]) 
    visited = {entry_point} 
    
    
    min_coords = [min(v[i] for v in voxels) for i in range(3)]
    max_coords = [max(v[i] for v in voxels) for i in range(3)]

    
    neighbors_offset = [(0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0)]

    while queue:
        x, y, z = queue.popleft()
        
        for dx, dy, dz in neighbors_offset:
            nx, ny, nz = x + dx, y + dy, z + dz
            neighbor = (nx, ny, nz)
            
            
            if not (min_coords[0] - 10 <= nx <= max_coords[0] + 10 and 
                    min_coords[1] - 10 <= ny <= max_coords[1] + 10 and 
                    min_coords[2] - 10 <= nz <= max_coords[2] + 10):
                continue
            
            
            if neighbor not in visited and neighbor not in voxels:
                visited.add(neighbor)
                queue.append(neighbor)

    
    retained_voxels = set()
    for vx, vy, vz in voxels:
        is_surface = False
        
        
        for dx, dy, dz in neighbors_offset:
            neighbor = (vx + dx, vy + dy, vz + dz)
            
            
            if neighbor in visited:
                is_surface = True
                break
        
        # 只有外壳或结构方块才被保留，内部核心方块被移除。
        if is_surface:
            retained_voxels.add((vx, vy, vz))
            
    return retained_voxels


# --- 自定义画板控件 ---
class GridCanvas(QWidget):
    def __init__(self, width=64, height=64, max_display_size=800, parent=None):
        super().__init__(parent)
        self.grid_width = width; self.grid_height = height
        if self.grid_width > 0 and self.grid_height > 0: self.cell_size = max(1, max_display_size // max(self.grid_width, self.grid_height))
        else: self.cell_size = 1
        self.grid_data = {}; self.current_block_name = "minecraft:stone"; self.current_color = QColor(*MINECRAFT_BLOCKS[self.current_block_name])
        self.setFixedSize(self.grid_width * self.cell_size, self.grid_height * self.cell_size)
    def set_current_brush(self, block_name, color): self.current_block_name = block_name; self.current_color = color
    def paintEvent(self, event):
        painter = QPainter(self); painter.fillRect(self.rect(), Qt.white)
        for (row, col), (block_name, color) in self.grid_data.items(): painter.fillRect(col * self.cell_size, row * self.cell_size, self.cell_size, self.cell_size, color)
        if self.cell_size > 3:
            painter.setPen(QColor(200, 200, 200))
            for x in range(0, self.width(), self.cell_size): painter.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), self.cell_size): painter.drawLine(0, y, self.width(), y)
    def mousePressEvent(self, event): self.handle_mouse_event(event)
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton: self.handle_mouse_event(event)
        if event.buttons() & Qt.RightButton: self.handle_mouse_event(event, erase=True)
    def handle_mouse_event(self, event, erase=False):
        col, row = event.x() // self.cell_size, event.y() // self.cell_size
        if 0 <= row < self.grid_height and 0 <= col < self.grid_width:
            if erase:
                if (row, col) in self.grid_data: del self.grid_data[(row, col)]
            else: self.grid_data[(row, col)] = (self.current_block_name, self.current_color)
            self.update()
    def clear_grid(self): self.grid_data = {}; self.update()
    def load_from_image(self, image_path):
        try:
            img = Image.open(image_path).convert('RGB'); img = img.resize((self.grid_width, self.grid_height), Image.Resampling.LANCZOS)
            self.clear_grid()
            for row in range(self.grid_height):
                for col in range(self.grid_width):
                    pixel_color = img.getpixel((col, row)); block_name, q_color = find_closest_block(pixel_color); self.grid_data[(row, col)] = (block_name, q_color)
            self.update(); return True
        except Exception as e: QMessageBox.critical(self, "图片错误", f"无法加载或处理图片: {e}"); return False


class PaletteWidget(QWidget):
    color_selected = pyqtSignal(str, QColor)
    def __init__(self, parent=None):
        super().__init__(parent); layout = QGridLayout(); layout.setSpacing(2); row, col = 0, 0
        for name, color_tuple in MINECRAFT_BLOCKS.items():
            btn = QPushButton(); btn.setFixedSize(25, 25); btn.setStyleSheet(f"background-color: rgb({color_tuple[0]}, {color_tuple[1]}, {color_tuple[2]});"); btn.setToolTip(name)
            btn.clicked.connect(lambda _, n=name, c=color_tuple: self.color_selected.emit(n, QColor(*c)))
            layout.addWidget(btn, row, col); col += 1
            if col > 7: col, row = 0, row + 1
        self.setLayout(layout)



class Builder2DWorker(QObject):
    progress = pyqtSignal(str); finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, settings, grid_data):
        super().__init__(); self.settings = settings; self.grid_data = grid_data
    def run(self):
        self.progress.emit("--- 开始2D建造任务 ---")
        self.progress.emit(f"目标服务器: {self.settings['ip']}:{self.settings['port']}")
        try:
            self.progress.emit("STEP 1: 准备执行 MCRcon 连接...")
            with MCRcon(self.settings['ip'], self.settings['password'], port=self.settings['port'], timeout=10) as mcr:
                self.progress.emit("✅ STEP 2: MCRcon 连接成功！服务器接受了连接。")
                total, built = len(self.grid_data), 0
                for (row, col), (block_name, _) in self.grid_data.items():
                    if self.settings['orientation'] == "水平 (地面XZ)":
                        mc_x, mc_y, mc_z = self.settings['x'] + col, self.settings['y'], self.settings['z'] + row
                    else:
                        mc_x, mc_y, mc_z = self.settings['x'] + col, self.settings['y'] + (self.settings['grid_h'] - 1 - row), self.settings['z']
                    mcr.command(f"setblock {mc_x} {mc_y} {mc_z} {block_name}")
                    built += 1
                self.progress.emit("✅ STEP 3: 所有 setblock 命令已发送完毕。")
                self.finished.emit("🎉🎉🎉 2D像素画建造任务完成！")
        except socket.timeout:
            self.error.emit("❌❌❌ [致命错误] 连接超时！请检查：\n1. 云服务器的防火墙/安全组是否已开放RCON端口？\n2. IP地址或端口是否填错？")
        except ConnectionRefusedError:
            self.error.emit("❌❌❌ [致命错误] 连接被服务器拒绝！请检查：\n1. IP地址或端口是否填错？\n2. 游戏服务器是否已成功启动？")
        except Exception as e:
            self.error.emit(f"❌❌❌ [致命错误] 发生未知错误: {type(e).__name__} - {e}\n这通常是 RCON 密码错误！")


class Builder3DWorker(QObject):
    progress = pyqtSignal(str); finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, settings, voxel_data):
        super().__init__(); self.settings = settings; self.voxels = voxel_data
    def run(self):
        self.progress.emit("--- 开始3D建造任务 ---")
        self.progress.emit(f"目标服务器: {self.settings['ip']}:{self.settings['port']}")
        try:
            self.progress.emit("STEP 1: 准备执行 MCRcon 连接...")
            with MCRcon(self.settings['ip'], self.settings['password'], port=self.settings['port'], timeout=20) as mcr:
                self.progress.emit("✅ STEP 2: MCRcon 连接成功！服务器接受了连接。")
                total, built = len(self.voxels), 0
                for (mc_x, mc_y, mc_z) in self.voxels:
                    # 3D 建造使用 settings 中的默认方块材质
                    mcr.command(f"setblock {mc_x} {mc_y} {mc_z} {self.settings['block_material']}")
                    built += 1
                self.progress.emit("✅ STEP 3: 所有 setblock 命令已发送完毕。")
                self.finished.emit(f"🎉🎉🎉 3D模型建造任务完成！共放置 {total} 个方块！")
        except socket.timeout:
            self.error.emit("❌❌❌ [致命错误] 连接超时！请检查：\n1. 云服务器的防火墙/安全组是否已开放RCON端口？\n2. IP地址或端口是否填错？")
        except ConnectionRefusedError:
            self.error.emit("❌❌❌ [致命错误] 连接被服务器拒绝！请检查：\n1. IP地址或端口是否填错？\n2. 游戏服务器是否已成功启动？")
        except Exception as e:
            self.error.emit(f"❌❌❌ [致命错误] 发生未知错误: {type(e).__name__} - {e}\n这通常是 RCON 密码错误！")


# --- 主窗口类 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("我的世界 - 2D/3D 建造工具 (AFDC 增强版)")
        self.setGeometry(100, 100, 1400, 900); self.voxel_data = None
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QHBoxLayout(central_widget)
        
        
        left_panel = QVBoxLayout()
        canvas_settings_group = QGroupBox("画布设置"); canvas_settings_layout = QHBoxLayout()
        self.grid_w_input = QLineEdit("64"); self.grid_h_input = QLineEdit("64")
        resize_btn = QPushButton("应用尺寸"); resize_btn.clicked.connect(self.resize_canvas)
        canvas_settings_layout.addWidget(QLabel("宽度:")); canvas_settings_layout.addWidget(self.grid_w_input); canvas_settings_layout.addWidget(QLabel("高度:")); canvas_settings_layout.addWidget(self.grid_h_input); canvas_settings_layout.addWidget(resize_btn)
        canvas_settings_group.setLayout(canvas_settings_layout)
        canvas_tools_layout = QHBoxLayout()
        clear_btn = QPushButton("清空画板"); clear_btn.clicked.connect(lambda: self.canvas.clear_grid()); load_img_btn = QPushButton("加载图片"); load_img_btn.clicked.connect(self.load_image)
        canvas_tools_layout.addWidget(clear_btn); canvas_tools_layout.addWidget(load_img_btn)
        self.canvas_container_layout = QVBoxLayout()
        self.canvas = GridCanvas(width=64, height=64)
        self.canvas_container_layout.addWidget(self.canvas, alignment=Qt.AlignCenter)
        left_panel.addWidget(canvas_settings_group); left_panel.addLayout(canvas_tools_layout); left_panel.addLayout(self.canvas_container_layout); left_panel.addStretch(1)
        
        
        right_panel = QVBoxLayout()

        
        palette_group = QGroupBox("2D 像素画-方块调色板"); self.palette = PaletteWidget()
        self.palette.color_selected.connect(lambda n, c: self.canvas.set_current_brush(n, c))
        palette_layout = QVBoxLayout(); palette_layout.addWidget(self.palette); palette_group.setLayout(palette_layout)
        
        
        model_group = QGroupBox("3D 模型建造 (OBJ)"); model_layout = QVBoxLayout(); form_layout = QFormLayout()
        self.max_size_input = QLineEdit("64"); self.block_material_combo = QComboBox(); self.block_material_combo.addItems(MINECRAFT_BLOCKS.keys())
        form_layout.addRow("最大尺寸 (方块):", self.max_size_input); form_layout.addRow("建造方块材质:", self.block_material_combo)
        self.load_obj_btn = QPushButton("加载并转换 .obj 模型"); self.load_obj_btn.clicked.connect(self.load_and_voxelize_obj)
        model_layout.addLayout(form_layout); 
        
        # --- AFDC 空间优化设置 (新增 UI) ---
        afdc_group = QGroupBox("AFDC 空间优化 (体素流体力学)"); afdc_layout = QFormLayout(afdc_group)
        self.afdc_checkbox = QCheckBox("启用空心化与支撑优化 (AFDC)"); self.afdc_checkbox.setChecked(True)
        afdc_layout.addWidget(self.afdc_checkbox)
        h_layout = QHBoxLayout()
        self.afdc_x_input = QLineEdit("0"); self.afdc_y_input = QLineEdit("0"); self.afdc_z_input = QLineEdit("0")
        h_layout.addWidget(QLabel("X:")); h_layout.addWidget(self.afdc_x_input)
        h_layout.addWidget(QLabel("Y:")); h_layout.addWidget(self.afdc_y_input)
        h_layout.addWidget(QLabel("Z:")); h_layout.addWidget(self.afdc_z_input)
        afdc_layout.addRow("入口体素坐标 (相对模型原点):", h_layout)
        
        model_layout.addWidget(afdc_group) # 将
        model_layout.addWidget(self.load_obj_btn);
        model_group.setLayout(model_layout)

        
        server_group = QGroupBox("服务器连接"); server_layout = QFormLayout()
        self.ip_input = QLineEdit("127.0.0.1"); self.port_input = QLineEdit("25575"); self.password_input = QLineEdit(); self.password_input.setEchoMode(QLineEdit.Password)
        server_layout.addRow("服务器 IP:", self.ip_input); server_layout.addRow("RCON 端口:", self.port_input); server_layout.addRow("RCON 密码:", self.password_input)
        server_group.setLayout(server_layout)
        
        
        build_group = QGroupBox("建造设置"); build_layout = QFormLayout()
        self.x_input = QLineEdit("0"); self.y_input = QLineEdit("64"); self.z_input = QLineEdit("0")
        self.orientation_combo = QComboBox(); self.orientation_combo.addItems(["水平 (地面XZ)", "垂直 (墙面XY)"])
        build_layout.addRow("起始坐标 X:", self.x_input); build_layout.addRow("起始坐标 Y:", self.y_input); build_layout.addRow("起始坐标 Z:", self.z_input); build_layout.addRow("2D建造方向:", self.orientation_combo)
        build_group.setLayout(build_layout)
        
        
        log_group = QGroupBox("实时日志"); self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        log_layout = QVBoxLayout(); log_layout.addWidget(self.log_output); log_group.setLayout(log_layout)
        
        
        self.build_button = QPushButton("在游戏中建造！"); self.build_button.setStyleSheet("font-size: 18px; padding: 12px; background-color: #4CAF50; color: white;")
        self.build_button.clicked.connect(self.start_build)
        
       
        right_panel.addWidget(palette_group); right_panel.addWidget(model_group); right_panel.addWidget(server_group); right_panel.addWidget(build_group); right_panel.addWidget(self.build_button); right_panel.addWidget(log_group)
        main_layout.addLayout(left_panel, 3); main_layout.addLayout(right_panel, 1)

    
    def resize_canvas(self):
        try:
            width, height = int(self.grid_w_input.text()), int(self.grid_h_input.text())
            if not (8 <= width <= 256 and 8 <= height <= 256): QMessageBox.warning(self, "尺寸无效", "宽度和高度建议在 8 到 256 之间。"); return
        except ValueError: QMessageBox.critical(self, "输入错误", "宽度和高度必须是整数！"); return
        while self.canvas_container_layout.count():
            child = self.canvas_container_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.canvas = GridCanvas(width, height); self.palette.color_selected.connect(self.canvas.set_current_brush); self.canvas_container_layout.addWidget(self.canvas, alignment=Qt.AlignCenter)
        self.log_output.append(f"✅ 画布尺寸已更新为 {width}x{height}。"); self.voxel_data = None
    
    def load_image(self):
        self.voxel_data = None; file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.log_output.clear(); self.log_output.append(f"正在加载图片: {file_path}")
            if self.canvas.load_from_image(file_path): self.log_output.append("✅ 图片已成功转换为像素画！")
    
    def load_and_voxelize_obj(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择OBJ模型", "", "OBJ Files (*.obj)");
        if not file_path: return
        self.log_output.clear(); self.log_output.append(f"正在加载模型: {file_path}..."); QApplication.processEvents()
        try:
            max_dim = int(self.max_size_input.text()); scene = pywavefront.Wavefront(file_path, collect_faces=True, parse=True); all_vertices = scene.vertices
            if not all_vertices: self.log_output.append("❌ 错误：模型无顶点数据！"); return
            min_x, max_x = min(v[0] for v in all_vertices), max(v[0] for v in all_vertices); min_y, max_y = min(v[1] for v in all_vertices), max(v[1] for v in all_vertices); min_z, max_z = min(v[2] for v in all_vertices), max(v[2] for v in all_vertices)
            scale_x, scale_y, scale_z = max_x - min_x, max_y - min_y, max_z - min_z; model_max_dim = max(scale_x, scale_y, scale_z)
            if model_max_dim == 0: self.log_output.append("❌ 错误：模型尺寸为0！"); return
            scale_factor = max_dim / model_max_dim
            self.log_output.append(f"模型缩放比例: {scale_factor:.2f}"); self.log_output.append("正在体素化，请稍候..."); QApplication.processEvents()
            voxels = set()
            for name, mesh in scene.meshes.items():
                for face in mesh.faces:
                    v1, v2, v3 = scene.vertices[face[0]], scene.vertices[face[1]], scene.vertices[face[2]]
                    for _ in range(100): # 增加采样点，提高精度
                        u, v = random.random(), random.random()
                        if u + v > 1: u, v = 1 - u, 1 - v
                        p = (v1[0] + u * (v2[0] - v1[0]) + v * (v3[0] - v1[0]), v1[1] + u * (v2[1] - v1[1]) + v * (v3[1] - v1[1]), v1[2] + u * (v2[2] - v1[2]) + v * (v3[2] - v1[2]))
                        vx, vy, vz = int((p[0] - min_x) * scale_factor), int((p[1] - min_y) * scale_factor), int((p[2] - min_z) * scale_factor)
                        voxels.add((vx, vy, vz))
            self.voxel_data = voxels; self.log_output.append(f"✅ 模型转换完成！共生成 {len(self.voxel_data)} 个方块。")
        except Exception as e: self.log_output.append(f"❌ 处理模型时发生错误: {e}"); self.voxel_data = None
    
    def start_build(self):
        
        if self.voxel_data is not None: self.start_3d_build()
        else: self.start_2d_build()
    
    def start_2d_build(self):
        if not self.canvas.grid_data: QMessageBox.warning(self, "画板为空", "画板上没有任何内容可以建造！"); return
        reply = QMessageBox.question(self, '2D建造确认', f"将建造 {len(self.canvas.grid_data)} 个方块，确定吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: self.log_output.append("2D建造任务已取消。"); return
        try: settings = {'ip': self.ip_input.text(), 'port': int(self.port_input.text()), 'password': self.password_input.text(), 'x': int(self.x_input.text()), 'y': int(self.y_input.text()), 'z': int(self.z_input.text()), 'orientation': self.orientation_combo.currentText(), 'grid_h': self.canvas.grid_height}
        except ValueError: QMessageBox.critical(self, "输入错误", "端口和坐标必须是整数！"); return
        self.log_output.clear(); self.log_output.append("准备启动2D建造..."); self.build_button.setEnabled(False); self.build_button.setText("正在建造中...")
        self.thread = QThread(); self.worker = Builder2DWorker(settings, self.canvas.grid_data); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.finished.connect(self.on_build_complete); self.worker.error.connect(self.on_build_complete); self.worker.progress.connect(self.log_output.append); self.thread.start()
    
    def start_3d_build(self):
        if not self.voxel_data: QMessageBox.warning(self, "无模型数据", "请先加载并转换一个OBJ模型！"); return
        
        processed_voxels = self.voxel_data.copy() 
        
        # --- AFDC 逻辑：空心化处理 ---
        if self.afdc_checkbox.isChecked():
            try:
                entry_point = (
                    int(self.afdc_x_input.text()),
                    int(self.afdc_y_input.text()),
                    int(self.afdc_z_input.text())
                )
            except ValueError:
                QMessageBox.critical(self, "输入错误", "AFDC入口坐标必须是整数！"); return

            self.log_output.append(">>> 启动 AFDC 结构分析...")
            original_count = len(self.voxel_data)
            
            processed_voxels = process_afdc_hollowing(self.voxel_data, entry_point)
            
            reduction = original_count - len(processed_voxels)
            if original_count > 0:
                 self.log_output.append(f">>> AFDC 分析完成。体素数量从 {original_count} 减少到 {len(processed_voxels)} (减少 {reduction/original_count:.2%})")
            else:
                 self.log_output.append(">>> AFDC 分析完成。模型体素为空。")
        # ----------------------------

        reply = QMessageBox.question(self, '3D建造确认', f"将建造一个由 {len(processed_voxels)} 个方块组成的3D模型。\n这会非常耗时！确定吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: self.log_output.append("3D建造任务已取消。"); return

        try: settings = {'ip': self.ip_input.text(), 'port': int(self.port_input.text()), 'password': self.password_input.text(), 'x': int(self.x_input.text()), 'y': int(self.y_input.text()), 'z': int(self.z_input.text()), 'block_material': self.block_material_combo.currentText()}
        except ValueError: QMessageBox.critical(self, "输入错误", "端口和坐标必须是整数！"); return
        
        self.log_output.clear(); self.log_output.append("准备启动3D建造..."); self.build_button.setEnabled(False); self.build_button.setText("正在建造3D模型...")
        
        
        offset_voxels = {(vx + settings['x'], vy + settings['y'], vz + settings['z']) for vx, vy, vz in processed_voxels}
        
        self.thread = QThread(); self.worker = Builder3DWorker(settings, offset_voxels); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.finished.connect(self.on_build_complete); self.worker.error.connect(self.on_build_complete); self.worker.progress.connect(self.log_output.append); self.thread.start()
    
    def on_build_complete(self, message):
        self.log_output.append(message); self.build_button.setEnabled(True); self.build_button.setText("在游戏中建造！")
        if hasattr(self, 'thread') and self.thread.isRunning(): self.thread.quit(); self.thread.wait()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())