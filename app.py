# app.py (真正的最终版 - NBT光速生成)
import sys
import math
import os
from PIL import Image, ImageDraw
import pywavefront
import nbtlib

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QFormLayout, QLineEdit, QPushButton, QTextEdit,
                             QMessageBox, QFileDialog, QComboBox, QLabel, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter

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

# --- 辅助函数和UI控件 ---
class GridCanvas(QWidget):
    def __init__(self, width=64, height=64, max_display_size=800, parent=None):
        super().__init__(parent); self.grid_width = width; self.grid_height = height; self.cell_size = max(1, max_display_size // max(self.grid_width, self.grid_height)) if self.grid_width > 0 and self.grid_height > 0 else 1; self.grid_data = {}; self.current_block_name = "minecraft:stone"; self.current_color = QColor(*MINECRAFT_BLOCKS[self.current_block_name]); self.setFixedSize(self.grid_width * self.cell_size, self.grid_height * self.cell_size)
    def set_current_brush(self, block_name, color): self.current_block_name = block_name; self.current_color = color
    def paintEvent(self, event):
        painter = QPainter(self); painter.fillRect(self.rect(), Qt.white)
        for (row, col), (block_name, color) in self.grid_data.items(): painter.fillRect(col * self.cell_size, row * self.cell_size, self.cell_size, self.cell_size, color)
        if self.cell_size > 3:
            painter.setPen(QColor(200, 200, 200)); [painter.drawLine(x, 0, x, self.height()) for x in range(0, self.width(), self.cell_size)]; [painter.drawLine(0, y, self.width(), y) for y in range(0, self.height(), self.cell_size)]
    def mousePressEvent(self, event): self.handle_mouse_event(event)
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton: self.handle_mouse_event(event)
        if event.buttons() & Qt.RightButton: self.handle_mouse_event(event, erase=True)
    def handle_mouse_event(self, event, erase=False):
        col, row = event.x() // self.cell_size, event.y() // self.cell_size
        if 0 <= row < self.grid_height and 0 <= col < self.grid_width:
            if erase: self.grid_data.pop((row, col), None)
            else: self.grid_data[(row, col)] = (self.current_block_name, self.current_color)
            self.update()
    def clear_grid(self): self.grid_data = {}; self.update()
    def load_from_image(self, image_path):
        try:
            img = Image.open(image_path).convert('RGB').resize((self.grid_width, self.grid_height), Image.Resampling.LANCZOS)
            self.clear_grid()
            for row in range(self.grid_height):
                for col in range(self.grid_width):
                    pixel_color = img.getpixel((col, row)); block_name, q_color = find_closest_block(pixel_color); self.grid_data[(row, col)] = (block_name, q_color)
            self.update(); return True
        except Exception as e: QMessageBox.critical(self, "图片错误", f"无法加载或处理图片: {e}"); return False

def find_closest_block(rgb_tuple):
    min_dist, closest_block_name = float('inf'), ""
    r1, g1, b1 = rgb_tuple
    for name, color_tuple in MINECRAFT_BLOCKS.items():
        r2, g2, b2 = color_tuple; dist = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
        if dist < min_dist: min_dist, closest_block_name = dist, name
    return closest_block_name, QColor(*MINECRAFT_BLOCKS[closest_block_name])

class PaletteWidget(QWidget):
    color_selected = pyqtSignal(str, QColor)
    def __init__(self, parent=None):
        super().__init__(parent); layout = QGridLayout(); layout.setSpacing(2); row, col = 0, 0
        for name, color_tuple in MINECRAFT_BLOCKS.items():
            btn = QPushButton(); btn.setFixedSize(25, 25); btn.setStyleSheet(f"background-color: rgb({color_tuple[0]}, {color_tuple[1]}, {color_tuple[2]});"); btn.setToolTip(name)
            btn.clicked.connect(lambda checked, n=name, c_tuple=color_tuple: self.color_selected.emit(n, QColor(*c_tuple)))
            layout.addWidget(btn, row, col); col += 1
            if col > 7: col, row = 0, row + 1
        self.setLayout(layout)

# --- 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("我的世界 - NBT光速建造工具 (最终修复版)")
        self.setGeometry(100, 100, 1400, 900); self.voxel_data = None
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QHBoxLayout(central_widget)
        left_panel = QVBoxLayout()
        canvas_settings_group = QGroupBox("2D画布/3D模型尺寸设置"); canvas_settings_layout = QHBoxLayout()
        self.grid_w_input = QLineEdit("64"); self.grid_h_input = QLineEdit("64"); self.max_size_input = QLineEdit("64")
        resize_btn = QPushButton("应用尺寸"); resize_btn.clicked.connect(self.resize_canvas)
        canvas_settings_layout.addWidget(QLabel("画布宽度:")); canvas_settings_layout.addWidget(self.grid_w_input); canvas_settings_layout.addWidget(QLabel("画布高度:")); canvas_settings_layout.addWidget(self.grid_h_input); canvas_settings_layout.addWidget(QLabel("3D最大尺寸:")); canvas_settings_layout.addWidget(self.max_size_input); canvas_settings_layout.addWidget(resize_btn)
        canvas_settings_group.setLayout(canvas_settings_layout)
        canvas_tools_layout = QHBoxLayout()
        clear_btn = QPushButton("清空画板"); clear_btn.clicked.connect(lambda: self.canvas.clear_grid()); load_img_btn = QPushButton("加载图片"); load_img_btn.clicked.connect(self.load_image); self.load_obj_btn = QPushButton("加载并转换 .obj 模型 (彩色)"); self.load_obj_btn.clicked.connect(self.load_and_voxelize_obj)
        canvas_tools_layout.addWidget(clear_btn); canvas_tools_layout.addWidget(load_img_btn); canvas_tools_layout.addWidget(self.load_obj_btn)
        self.canvas_container_layout = QVBoxLayout(); self.canvas = GridCanvas(width=64, height=64); self.canvas_container_layout.addWidget(self.canvas, alignment=Qt.AlignCenter)
        left_panel.addWidget(canvas_settings_group); left_panel.addLayout(canvas_tools_layout); left_panel.addLayout(self.canvas_container_layout); left_panel.addStretch(1)
        right_panel = QVBoxLayout()
        palette_group = QGroupBox("方块调色板"); self.palette = PaletteWidget(); self.palette.color_selected.connect(lambda n, c: self.canvas.set_current_brush(n, c)); palette_layout = QVBoxLayout(); palette_layout.addWidget(self.palette); palette_group.setLayout(palette_layout)
        info_group = QGroupBox("使用说明"); info_layout = QVBoxLayout()
        self.orientation_combo = QComboBox(); self.orientation_combo.addItems(["水平 (地面XZ)", "垂直 (墙面XY)"]); info_layout.addWidget(QLabel("2D像素画生成方向:"))
        info_layout.addWidget(self.orientation_combo)
        self.x_input = QLineEdit("~ ~ ~"); self.x_input.setReadOnly(True); info_layout.addWidget(QLabel("游戏内放置坐标:"))
        info_layout.addWidget(self.x_input)
        info_group.setLayout(info_layout)
        log_group = QGroupBox("实时日志"); self.log_output = QTextEdit(); self.log_output.setReadOnly(True); log_layout = QVBoxLayout(); log_layout.addWidget(self.log_output); log_group.setLayout(log_layout)
        self.generate_button = QPushButton("生成 .nbt 结构文件"); self.generate_button.setStyleSheet("font-size: 18px; padding: 12px; background-color: #4CAF50; color: white;")
        self.generate_button.clicked.connect(self.generate_nbt_file)
        right_panel.addWidget(palette_group); right_panel.addWidget(info_group); right_panel.addWidget(self.generate_button); right_panel.addWidget(log_group)
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
        self.log_output.append(f"✅ 画布尺寸已更新为 {width}x{height}。"); self.voxel_data = None; self.canvas.grid_data = {}

    def load_image(self):
        self.voxel_data = None; file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.log_output.clear(); self.log_output.append(f"正在加载图片: {file_path}")
            if self.canvas.load_from_image(file_path): self.log_output.append("✅ 图片已成功转换为2D像素画！")

    def load_and_voxelize_obj(self):
        self.canvas.clear_grid()
        file_path, _ = QFileDialog.getOpenFileName(self, "选择OBJ模型", "", "OBJ Files (*.obj)")
        if not file_path: return
        self.log_output.clear(); self.log_output.append(f"正在加载模型: {file_path}..."); QApplication.processEvents()
        try:
            max_dim = int(self.max_size_input.text())
            self.log_output.append("STEP 1: 解析模型几何体与材质..."); QApplication.processEvents()
            scene = pywavefront.Wavefront(file_path, collect_faces=True, create_materials=True)
            all_vertices = list(scene.vertices)
            if not all_vertices: self.log_output.append("❌ 错误：模型无顶点数据！"); return
            min_coord = [min(v[i] for v in all_vertices) for i in range(3)]; max_coord = [max(v[i] for v in all_vertices) for i in range(3)]
            model_dims = [max_coord[i] - min_coord[i] for i in range(3)]; model_max_dim = max(model_dims) if any(d > 0 for d in model_dims) else 0
            if model_max_dim == 0: self.log_output.append("❌ 错误：模型尺寸为0！"); return
            scale_factor = (max_dim - 1) / model_max_dim if model_max_dim > 0 else 0
            material_colors = {name: tuple(int(c * 255) for c in mat.diffuse[:3]) if mat.diffuse and len(mat.diffuse) >= 3 else (128, 128, 128) for name, mat in scene.materials.items()}
            self.log_output.append(f"模型缩放比例: {scale_factor:.2f}")
            self.log_output.append("STEP 2: 开始逐层切片并渲染..."); QApplication.processEvents()
            final_voxel_data = {}
            for y in range(max_dim):
                scan_y = min_coord[1] + (y / scale_factor if scale_factor != 0 else 0)
                slice_image = Image.new('RGB', (max_dim, max_dim), (0, 0, 0)); draw = ImageDraw.Draw(slice_image)
                for name, material in scene.materials.items():
                    mat_color = material_colors.get(name, (128, 128, 128))
                    if not material.vertices: continue
                    for i in range(0, len(material.vertices), 9):
                        if i + 8 >= len(material.vertices): continue
                        verts_3d = [tuple(material.vertices[i+j:i+j+3]) for j in range(0, 9, 3)]; y_coords = [v[1] for v in verts_3d]
                        if min(y_coords) > scan_y or max(y_coords) < scan_y: continue
                        intersection_points_3d = []
                        for j in range(3):
                            p1, p2 = verts_3d[j], verts_3d[(j + 1) % 3]
                            if p1[1] == scan_y: intersection_points_3d.append(p1)
                            if (p1[1] < scan_y and p2[1] > scan_y) or (p2[1] < scan_y and p1[1] > scan_y):
                                if p2[1] - p1[1] == 0: continue
                                t = (scan_y - p1[1]) / (p2[1] - p1[1]); ix, iz = p1[0] + t * (p2[0] - p1[0]), p1[2] + t * (p2[2] - p1[2]); intersection_points_3d.append((ix, scan_y, iz))
                        if len(intersection_points_3d) >= 2:
                            poly_2d = [(int((p[0] - min_coord[0]) * scale_factor), int((p[2] - min_coord[2]) * scale_factor)) for p in intersection_points_3d]
                            if len(poly_2d) >= 2: draw.polygon(poly_2d, fill=mat_color, outline=mat_color)
                for x in range(max_dim):
                    for z in range(max_dim):
                        pixel_color = slice_image.getpixel((x, z))
                        if pixel_color != (0, 0, 0):
                            block_name, _ = find_closest_block(pixel_color); final_voxel_data[(x, y, z)] = block_name
                if (y + 1) % 8 == 0 or y == max_dim - 1: self.log_output.append(f"  -> 已处理 {y+1}/{max_dim} 层..."); QApplication.processEvents()
            self.voxel_data = final_voxel_data
            self.log_output.append(f"✅ 模型成功转换为体素！共生成 {len(self.voxel_data)} 个方块。")
        except Exception as e:
            import traceback; self.log_output.append(f"❌ 处理模型时发生错误: {e}\n{traceback.format_exc()}"); self.voxel_data = None
    
    def generate_nbt_file(self):
        voxel_data_to_save = {}
        if self.voxel_data:
            voxel_data_to_save = self.voxel_data; self.log_output.append("检测到3D模型数据...")
        elif self.canvas.grid_data:
            self.log_output.append("检测到2D画布数据，正在转换为3D体素...")
            grid_h = self.canvas.grid_height
            for (row, col), (block_name, _) in self.canvas.grid_data.items():
                if self.orientation_combo.currentText() == "水平 (地面XZ)": voxel_data_to_save[(col, 0, row)] = block_name
                else: voxel_data_to_save[(col, grid_h - 1 - row, 0)] = block_name
        else:
            QMessageBox.warning(self, "无数据", "没有可生成的模型或像素画！"); return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "保存NBT结构文件", "", "NBT Files (*.nbt)")
        if not file_path:
            self.log_output.append("已取消保存。"); return

        self.log_output.append(f"准备生成NBT文件，共 {len(voxel_data_to_save)} 个方块..."); QApplication.processEvents()

        try:
            if not voxel_data_to_save: raise ValueError("数据为空")
            min_coords = [min(coords[i] for coords in voxel_data_to_save.keys()) for i in range(3)]
            max_coords = [max(coords[i] for coords in voxel_data_to_save.keys()) for i in range(3)]
            size = [max_coords[i] - min_coords[i] + 1 for i in range(3)]
            unique_blocks = sorted(list(set(voxel_data_to_save.values())))
            palette = nbtlib.List([nbtlib.Compound({"Name": nbtlib.String(name)}) for name in unique_blocks])
            block_to_state = {name: i for i, name in enumerate(unique_blocks)}
            self.log_output.append(f"已创建调色板，包含 {len(palette)} 种方块。")
            
            blocks = nbtlib.List[nbtlib.Compound]() # 预先定义列表类型
            for (x, y, z), block_name in voxel_data_to_save.items():
                rel_pos = nbtlib.List[nbtlib.Int]([x - min_coords[0], y - min_coords[1], z - min_coords[2]])
                state = nbtlib.Int(block_to_state[block_name])
                blocks.append(nbtlib.Compound({"pos": rel_pos, "state": state}))
            self.log_output.append("已生成方块数据列表...")
            
            nbt_file = nbtlib.File({'DataVersion': nbtlib.Int(3120), 'size': nbtlib.List[nbtlib.Int](size), 'palette': palette, 'blocks': blocks})
            
            # --- ★★★ 终极API修复在这里 ★★★ ---
            nbt_file.save(file_path, gzipped=True) # 使用 .save() 方法

            self.log_output.append("\n🎉🎉🎉 NBT文件已成功生成！ 🎉🎉🎉")
            self.log_output.append(f"文件路径: {file_path}")
            self.log_output.append("\n--- 【下一步操作】 ---")
            self.log_output.append("1. 将这个.nbt文件上传到你服务器的 'world/generated/minecraft/structures/' 文件夹内。")
            self.log_output.append("   (如果'structures'文件夹不存在，请手动创建它)")
            structure_name = os.path.splitext(os.path.basename(file_path))[0]
            self.log_output.append(f"2. 在游戏里，站在你想要放置建筑的地方，然后执行以下命令:")
            self.log_output.append(f"/place template minecraft:{structure_name}")
            self.log_output.append("--- --- --- --- --- --- ---")
        except Exception as e:
            self.log_output.append(f"❌ 生成NBT文件时发生错误: {e}")
            import traceback; self.log_output.append(traceback.format_exc())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())