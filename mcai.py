# -----------------------------------------------------------------------------
# Minecraft AI Architect - 豆包 ARK 文生图版 v5
#
# 修正:
# 1. 修正了 PyQt5 中 QPainter.drawLine() 的 TypeError（参数过多）。
# 2. 将文生图部分从 DALL-E 3 切换回 火山引擎豆包 ARK（兼容 OpenAI 库）。
# 3. 保持了腾讯云 AI3D SDK (v20250513) 的修正。
# -----------------------------------------------------------------------------
import sys
import math
import time
import random
import os
import requests
from io import BytesIO
from openai import OpenAI

# --- 腾讯云 SDK (使用最新推荐的导入路径 v20250513) ---
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
# 导入路径已修正为最新的 20250513 版本
from tencentcloud.ai3d.v20250513 import ai3d_client, models as ai3d_models 

# --- 其他核心库 ---
from mcrcon import MCRcon
from PIL import Image
import pywavefront
import socket

# --- PyQt5 ---
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QFormLayout, QLineEdit, QPushButton, QTextEdit,
                             QMessageBox, QFileDialog, QComboBox, QLabel, QGridLayout)
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPainter, QColor, QPixmap

# -----------------------------------------------------------------------------
# API 密钥配置
# -----------------------------------------------------------------------------
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "xxxxxx")
# 替换为 火山引擎/豆包 ARK API KEY，用于图片生成
ARK_API_KEY = os.environ.get("ARK_API_KEY", "xxxxxxx")
TENCENTCLOUD_SECRET_ID = os.environ.get("TENCENTCLOUD_SECRET_ID", "<YOUR_TENCENTCLOUD_SECRET_ID>")
TENCENTCLOUD_SECRET_KEY = os.environ.get("TENCENTCLOUD_SECRET_KEY", "<YOUR_TENCENTCLOUD_SECRET_KEY>")
TENCENTCLOUD_REGION = "ap-guangzhou"

# -----------------------------------------------------------------------------
# 核心数据与实用函数 (保持不变)
# -----------------------------------------------------------------------------
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
class GridCanvas(QWidget):
    def __init__(self, width=64, height=64, max_display_size=800, parent=None):
        super().__init__(parent); self.grid_width = width; self.grid_height = height
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
            # 修正: drawLine 只需要 x1, y1, x2, y2 四个参数
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
def find_closest_block(rgb_tuple):
    min_dist, closest_block_name = float('inf'), ""
    r1, g1, b1 = rgb_tuple
    for name, color_tuple in MINECRAFT_BLOCKS.items():
        r2, g2, b2 = color_tuple; dist = math.sqrt((r1 - r2)**2 + (r1 - r2)**2 + (b1 - b2)**2)
        if dist < min_dist: min_dist, closest_block_name = dist, name
    return closest_block_name, QColor(*MINECRAFT_BLOCKS[closest_block_name])
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
    def __init__(self, settings, grid_data): super().__init__(); self.settings = settings; self.grid_data = grid_data
    def run(self):
        try:
            with MCRcon(self.settings['ip'], self.settings['password'], port=self.settings['port'], timeout=10) as mcr:
                self.progress.emit("✅ 2D建造连接成功！")
                total, built = len(self.grid_data), 0
                for (row, col), (block_name, _) in self.grid_data.items():
                    if self.settings['orientation'] == "水平 (地面XZ)": mc_x, mc_y, mc_z = self.settings['x'] + col, self.settings['y'], self.settings['z'] + row
                    else: mc_x, mc_y, mc_z = self.settings['x'] + col, self.settings['y'] + (self.settings['grid_h'] - 1 - row), self.settings['z']
                    mcr.command(f"setblock {mc_x} {mc_y} {mc_z} {block_name}"); built += 1
                    if built % 10 == 0: self.progress.emit(f"({built}/{total}) 正在放置2D方块...")
                    time.sleep(0.05)
                self.finished.emit("🎉🎉🎉 2D像素画建造完毕！")
        except Exception as e: self.error.emit(f"❌ 2D建造错误: {e}")
class Builder3DWorker(QObject):
    progress = pyqtSignal(str); finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, settings, voxel_data): super().__init__(); self.settings = settings; self.voxels = voxel_data
    def run(self):
        try:
            with MCRcon(self.settings['ip'], self.settings['password'], port=self.settings['port'], timeout=20) as mcr:
                self.progress.emit("✅ 3D建造连接成功！")
                total, built = len(self.voxels), 0
                for (mc_x, mc_y, mc_z) in self.voxels:
                    mcr.command(f"setblock {mc_x} {mc_y} {mc_z} {self.settings['block_material']}"); built += 1
                    if built % 20 == 0: self.progress.emit(f"({built}/{total}) 正在放置3D方块...")
                self.finished.emit(f"🎉🎉🎉 3D模型建造完毕！共放置 {total} 个方块！")
        except Exception as e: self.error.emit(f"❌ 3D建造错误: {e}")

# --- AI生成工作线程 (已修正 AI3D API 方法并替换 DALL-E 为豆包 ARK) ---
class AIGenerationWorker(QObject):
    progress = pyqtSignal(str)
    image_ready = pyqtSignal(QPixmap)
    voxels_ready = pyqtSignal(set)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, user_prompt, max_3d_size):
        super().__init__()
        self.user_prompt = user_prompt
        self.max_3d_size = max_3d_size

    def run(self):
        try:
            self.progress.emit("STEP 1/5: 正在调用 DeepSeek 优化提示词...")
            optimized_prompt = self._call_deepseek_api(self.user_prompt)
            self.progress.emit(f"✅ 提示词优化完成！")

            self.progress.emit("STEP 2/5: 正在调用 火山豆包 ARK 生成效果图...")
            image_url = self._call_ark_image_api(optimized_prompt) # 使用新的 豆包 ARK 方法
            self.progress.emit(f"✅ 效果图生成成功！")
            
            image_data = requests.get(image_url).content
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            self.image_ready.emit(pixmap)

            self.progress.emit("STEP 3/5: 正在调用 腾讯混元3D 生成模型 (此过程可能需要几分钟)...")
            model_url = self._call_hunyuan_3d_api(optimized_prompt)
            self.progress.emit(f"✅ 3D模型生成成功！URL: {model_url[:50]}...")

            self.progress.emit("STEP 4/5: 正在下载并解析3D模型...")
            model_content = requests.get(model_url).content
            scene = pywavefront.Wavefront(BytesIO(model_content), collect_faces=True, parse=True)
            self.progress.emit("✅ 3D模型解析成功！")

            self.progress.emit("STEP 5/5: 正在对模型进行体素化...")
            voxels = self._voxelize_scene(scene, self.max_3d_size)
            self.progress.emit(f"✅ 体素化完成！共生成 {len(voxels)} 个方块。")
            
            self.voxels_ready.emit(voxels)
            self.finished.emit("🎉 AI 生成流程全部完成！现在可以点击'在游戏中建造'按钮了！")

        except Exception as e:
            self.error.emit(f"❌ AI 生成流程失败: {e}")

    def _call_deepseek_api(self, prompt):
        # Base URL for DeepSeek
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的建筑设计师，请将用户的想法，优化为一段详细、具体的、用于指导文生图模型生成高质量建筑效果图的英文提示词。只返回英文提示词。"},
                {"role": "user", "content": prompt},
            ], stream=False
        )
        return response.choices[0].message.content

    # --- 替换为：使用兼容 OpenAI 接口的 火山豆包 ARK API ---
    def _call_ark_image_api(self, prompt):
        # 使用 ARK_API_KEY，并指定豆包的 base_url
        client = OpenAI(
            api_key=ARK_API_KEY,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
        
        # 调用豆包 Seedream 3.0 模型
        resp = client.images.generate(
            model="doubao-seedream-3-0-t2i-250415",
            prompt=prompt,
            size="1024x1024", # 豆包和 DALL-E 3 兼容的尺寸
            n=1,
        )
        
        if resp.data and resp.data[0].url:
            return resp.data[0].url
            
        raise Exception("火山豆包 ARK 文生图未能返回图片URL (请检查您的 ARK_API_KEY 是否有效)")
    # --- 豆包 ARK 方法结束 ---

    # --- 腾讯云 AI3D 方法 (保持 v20250513 修正) ---
    def _call_hunyuan_3d_api(self, prompt):
        cred = credential.Credential(TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY)
        client = ai3d_client.Ai3dClient(cred, TENCENTCLOUD_REGION, ClientProfile(HttpProfile(endpoint="ai3d.tencentcloudapi.com")))
        
        # 1. 使用新的提交任务 Request
        submit_req = ai3d_models.SubmitHunyuanTo3DJobRequest()
        submit_req.TextTo3DPrompt = prompt # 新 API 使用 TextTo3DPrompt 字段
        submit_req.ResultFormat = "obj"    # OBJ 格式

        # 2. 调用新的提交任务方法
        submit_resp = client.SubmitHunyuanTo3DJob(submit_req)
        job_id = submit_resp.JobId
        
        # 3. 循环查询任务状态
        for i in range(120): # 最多等待 120 * 5 = 600 秒 (10 分钟)
            self.progress.emit(f"  -> 正在查询3D任务状态... ({i*5}秒)")
            
            # 使用新的查询任务 Request
            query_req = ai3d_models.QueryHunyuanTo3DJobRequest(); 
            query_req.JobId = job_id
            
            # 4. 调用新的查询任务方法
            query_resp = client.QueryHunyuanTo3DJob(query_req)
            
            # 5. 检查状态字段 (假设 JobStatus 为新版本使用的状态字段)
            if query_resp.JobStatus == "SUCCEED":
                if query_resp.ModelUrl: return query_resp.ModelUrl
                raise Exception("腾讯3D任务成功但未返回模型URL (请检查文档确认字段名)")
            elif query_resp.JobStatus == "FAILED":
                raise Exception(f"腾讯3D任务失败: {query_resp.StatusDesc}")
            time.sleep(5)
            
        raise Exception("腾讯3D任务超时 (10分钟)")

    def _voxelize_scene(self, scene, max_dim):
        all_vertices = scene.vertices
        if not all_vertices: raise Exception("解析出的3D模型无顶点数据")
        min_x, max_x = min(v[0] for v in all_vertices), max(v[0] for v in all_vertices)
        min_y, max_y = min(v[1] for v in all_vertices), max(v[1] for v in all_vertices)
        min_z, max_z = min(v[2] for v in all_vertices), max(v[2] for v in all_vertices)
        scale_x, scale_y, scale_z = max_x - min_x, max_y - min_y, max_z - min_z
        model_max_dim = max(scale_x, scale_y, scale_z)
        if model_max_dim == 0: raise Exception("模型尺寸为0")
        scale_factor = max_dim / model_max_dim
        voxels = set()
        for mesh in scene.meshes.values():
            for face in mesh.faces:
                v1, v2, v3 = scene.vertices[face[0]], scene.vertices[face[1]], scene.vertices[face[2]]
                for _ in range(100):
                    u, v = random.random(), random.random()
                    if u + v > 1: u, v = 1 - u, 1 - v
                    p = (v1[0] + u * (v2[0] - v1[0]) + v * (v3[0] - v1[0]),
                         v1[1] + u * (v2[1] - v1[1]) + v * (v3[1] - v1[1]),
                         v1[2] + u * (v2[2] - v1[2]) + v * (v3[2] - v1[2]))
                    vx, vy, vz = int((p[0] - min_x) * scale_factor), int((p[1] - min_y) * scale_factor), int((p[2] - min_z) * scale_factor)
                    voxels.add((vx, vy, vz))
        return voxels

# --- 主窗口 (保持不变) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft AI Architect (豆包 ARK 文生图版)")
        self.setGeometry(100, 100, 1500, 900)
        self.voxel_data = None
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        left_panel = QVBoxLayout()
        canvas_settings_group = QGroupBox("画布设置"); canvas_settings_layout = QHBoxLayout()
        self.grid_w_input = QLineEdit("64"); self.grid_h_input = QLineEdit("64")
        resize_btn = QPushButton("应用尺寸"); resize_btn.clicked.connect(self.resize_canvas)
        canvas_settings_layout.addWidget(QLabel("宽度:")); canvas_settings_layout.addWidget(self.grid_w_input); canvas_settings_layout.addWidget(QLabel("高度:")); canvas_settings_layout.addWidget(self.grid_h_input); canvas_settings_layout.addWidget(resize_btn)
        canvas_settings_group.setLayout(canvas_settings_layout)
        canvas_tools_layout = QHBoxLayout()
        clear_btn = QPushButton("清空画板"); clear_btn.clicked.connect(lambda: self.canvas.clear_grid()); load_img_btn = QPushButton("加载图片"); load_img_btn.clicked.connect(self.load_image)
        canvas_tools_layout.addWidget(clear_btn); canvas_tools_layout.addWidget(load_img_btn)
        self.canvas_container_layout = QVBoxLayout(); self.canvas = GridCanvas(width=64, height=64)
        self.canvas_container_layout.addWidget(self.canvas, alignment=Qt.AlignCenter)
        left_panel.addWidget(canvas_settings_group); left_panel.addLayout(canvas_tools_layout); left_panel.addLayout(self.canvas_container_layout); left_panel.addStretch(1)
        right_panel = QVBoxLayout()
        ai_group = QGroupBox("AI 自然语言生成"); ai_layout = QVBoxLayout()
        self.ai_prompt_input = QLineEdit("a small lovely wooden cabin")
        self.ai_generate_btn = QPushButton("开始AI生成！"); self.ai_generate_btn.setStyleSheet("font-weight: bold; color: blue;")
        self.preview_label = QLabel("AI生成的效果图将显示在这里"); self.preview_label.setAlignment(Qt.AlignCenter); self.preview_label.setFixedSize(256, 256); self.preview_label.setStyleSheet("border: 1px solid gray;")
        ai_layout.addWidget(QLabel("输入你的建筑想法 (建议英文):")); ai_layout.addWidget(self.ai_prompt_input); ai_layout.addWidget(self.ai_generate_btn); ai_layout.addWidget(self.preview_label)
        ai_group.setLayout(ai_layout)
        self.ai_generate_btn.clicked.connect(self.start_ai_generation)
        palette_group = QGroupBox("2D 像素画-方块调色板"); self.palette = PaletteWidget()
        self.palette.color_selected.connect(lambda n, c: self.canvas.set_current_brush(n, c))
        palette_layout = QVBoxLayout(); palette_layout.addWidget(self.palette); palette_group.setLayout(palette_layout)
        model_group = QGroupBox("本地 3D模型加载 (OBJ)"); model_layout = QVBoxLayout(); form_layout = QFormLayout()
        self.max_size_input = QLineEdit("64"); self.block_material_combo = QComboBox(); self.block_material_combo.addItems(MINECRAFT_BLOCKS.keys())
        form_layout.addRow("最大尺寸 (方块):", self.max_size_input); form_layout.addRow("建造方块材质:", self.block_material_combo)
        self.load_obj_btn = QPushButton("加载本地 .obj 模型"); self.load_obj_btn.clicked.connect(self.load_and_voxelize_obj)
        model_layout.addLayout(form_layout); model_layout.addWidget(self.load_obj_btn); model_group.setLayout(model_layout)
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
        right_panel.addWidget(ai_group); right_panel.addWidget(palette_group); right_panel.addWidget(model_group); right_panel.addWidget(server_group); right_panel.addWidget(build_group); right_panel.addWidget(self.build_button); right_panel.addWidget(log_group)
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
                    for _ in range(100):
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
        reply = QMessageBox.question(self, '3D建造确认', f"将建造一个由 {len(self.voxel_data)} 个方块组成的3D模型。\n这会非常耗时！确定吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: self.log_output.append("3D建造任务已取消。"); return
        try: settings = {'ip': self.ip_input.text(), 'port': int(self.port_input.text()), 'password': self.password_input.text(), 'x': int(self.x_input.text()), 'y': int(self.y_input.text()), 'z': int(self.z_input.text()), 'block_material': self.block_material_combo.currentText()}
        except ValueError: QMessageBox.critical(self, "输入错误", "端口和坐标必须是整数！"); return
        self.log_output.clear(); self.log_output.append("准备启动3D建造..."); self.build_button.setEnabled(False); self.build_button.setText("正在建造3D模型...")
        offset_voxels = {(vx + settings['x'], vy + settings['y'], vz + settings['z']) for vx, vy, vz in self.voxel_data}
        self.thread = QThread(); self.worker = Builder3DWorker(settings, offset_voxels); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.finished.connect(self.on_build_complete); self.worker.error.connect(self.on_build_complete); self.worker.progress.connect(self.log_output.append); self.thread.start()
    def on_build_complete(self, message):
        self.log_output.append(message); self.build_button.setEnabled(True); self.build_button.setText("在游戏中建造！")
        if hasattr(self, 'thread') and self.thread.isRunning(): self.thread.quit(); self.thread.wait()
    def start_ai_generation(self):
        user_prompt = self.ai_prompt_input.text()
        if not user_prompt: QMessageBox.warning(self, "提示为空", "请输入你的建筑想法！"); return
        try: max_3d_size = int(self.max_size_input.text())
        except ValueError: QMessageBox.critical(self, "输入错误", "3D模型的最大尺寸必须是整数！"); return
        self.log_output.clear(); self.log_output.append("准备启动AI生成工作流...")
        self.ai_generate_btn.setEnabled(False); self.ai_generate_btn.setText("AI生成中...")
        self.build_button.setEnabled(False)
        self.thread = QThread()
        self.worker = AIGenerationWorker(user_prompt, max_3d_size)
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.log_output.append)
        self.worker.image_ready.connect(self.display_preview_image)
        self.worker.voxels_ready.connect(self.on_voxels_generated)
        self.worker.finished.connect(self.on_ai_complete)
        self.worker.error.connect(self.on_ai_complete)
        self.thread.start()
    def display_preview_image(self, pixmap): self.preview_label.setPixmap(pixmap.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    def on_voxels_generated(self, voxels): self.voxel_data = voxels
    def on_ai_complete(self, message):
        self.log_output.append(message)
        self.ai_generate_btn.setEnabled(True); self.ai_generate_btn.setText("开始AI生成！")
        self.build_button.setEnabled(True)
        if hasattr(self, 'thread') and self.thread.isRunning(): self.thread.quit(); self.thread.wait()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())