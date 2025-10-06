# converter_ui.py - 终极的、绝对的、最终的转换工具

import os
import sys
import nbtlib
from nbtlib.tag import *

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QTextEdit, QMessageBox, QFileDialog, QLabel)
from PyQt5.QtCore import Qt

# --- 核心翻译词典 ---
ID_MAPPING = {
    (0, 0): "minecraft:air", (1, 0): "minecraft:stone", (1, 1): "minecraft:granite", (1, 2): "minecraft:polished_granite", (1, 3): "minecraft:diorite", (1, 4): "minecraft:polished_diorite", (1, 5): "minecraft:andesite", (1, 6): "minecraft:polished_andesite", (2, 0): "minecraft:grass_block", (3, 0): "minecraft:dirt", (3, 1): "minecraft:coarse_dirt", (3, 2): "minecraft:podzol", (4, 0): "minecraft:cobblestone", (5, 0): "minecraft:oak_planks", (5, 1): "minecraft:spruce_planks", (5, 2): "minecraft:birch_planks", (5, 3): "minecraft:jungle_planks", (5, 4): "minecraft:acacia_planks", (5, 5): "minecraft:dark_oak_planks", (7, 0): "minecraft:bedrock", (9, 0): "minecraft:water", (11, 0): "minecraft:lava", (12, 0): "minecraft:sand", (12, 1): "minecraft:red_sand", (13, 0): "minecraft:gravel", (14, 0): "minecraft:gold_ore", (15, 0): "minecraft:iron_ore", (16, 0): "minecraft:coal_ore", (17, 0): "minecraft:oak_log", (17, 1): "minecraft:spruce_log", (17, 2): "minecraft:birch_log", (17, 3): "minecraft:jungle_log", (18, 0): "minecraft:oak_leaves", (18, 1): "minecraft:spruce_leaves", (18, 2): "minecraft:birch_leaves", (18, 3): "minecraft:jungle_leaves", (19, 0): "minecraft:sponge", (19, 1): "minecraft:wet_sponge", (20, 0): "minecraft:glass", (21, 0): "minecraft:lapis_ore", (22, 0): "minecraft:lapis_block", (24, 0): "minecraft:sandstone", (24, 1): "minecraft:chiseled_sandstone", (24, 2): "minecraft:cut_sandstone", (30, 0): "minecraft:cobweb", (31, 1): "minecraft:grass", (31, 2): "minecraft:fern", (35, 0): "minecraft:white_wool", (35, 1): "minecraft:orange_wool", (35, 2): "minecraft:magenta_wool", (35, 3): "minecraft:light_blue_wool", (35, 4): "minecraft:yellow_wool", (35, 5): "minecraft:lime_wool", (35, 6): "minecraft:pink_wool", (35, 7): "minecraft:gray_wool", (35, 8): "minecraft:light_gray_wool", (35, 9): "minecraft:cyan_wool", (35, 10): "minecraft:purple_wool", (35, 11): "minecraft:blue_wool", (35, 12): "minecraft:brown_wool", (35, 13): "minecraft:green_wool", (35, 14): "minecraft:red_wool", (35, 15): "minecraft:black_wool", (41, 0): "minecraft:gold_block", (42, 0): "minecraft:iron_block", (43, 0): "minecraft:stone_slab", (43, 1): "minecraft:sandstone_slab", (43, 3): "minecraft:cobblestone_slab", (43, 4): "minecraft:brick_slab", (43, 5): "minecraft:stone_brick_slab", (43, 6): "minecraft:nether_brick_slab", (43, 7): "minecraft:quartz_slab", (44, 0): "minecraft:stone_slab", (44, 1): "minecraft:sandstone_slab", (44, 3): "minecraft:cobblestone_slab", (45, 0): "minecraft:bricks", (47, 0): "minecraft:bookshelf", (48, 0): "minecraft:mossy_cobblestone", (49, 0): "minecraft:obsidian", (50, 5): "minecraft:torch", (53, 0): "minecraft:oak_stairs", (54, 0): "minecraft:chest", (56, 0): "minecraft:diamond_ore", (57, 0): "minecraft:diamond_block", (58, 0): "minecraft:crafting_table", (61, 0): "minecraft:furnace", (67, 0): "minecraft:cobblestone_stairs", (73, 0): "minecraft:redstone_ore", (78, 0): "minecraft:snow", (79, 0): "minecraft:ice", (80, 0): "minecraft:snow_block", (81, 0): "minecraft:cactus", (82, 0): "minecraft:clay", (85, 0): "minecraft:oak_fence", (87, 0): "minecraft:netherrack", (88, 0): "minecraft:soul_sand", (89, 0): "minecraft:glowstone", (95, 0): "minecraft:white_stained_glass", (95, 1): "minecraft:orange_stained_glass", (95, 2): "minecraft:magenta_stained_glass", (95, 3): "minecraft:light_blue_stained_glass", (95, 4): "minecraft:yellow_stained_glass", (95, 5): "minecraft:lime_stained_glass", (95, 6): "minecraft:pink_stained_glass", (95, 7): "minecraft:gray_stained_glass", (95, 8): "minecraft:light_gray_stained_glass", (95, 9): "minecraft:cyan_stained_glass", (95, 10): "minecraft:purple_stained_glass", (95, 11): "minecraft:blue_stained_glass", (95, 12): "minecraft:brown_stained_glass", (95, 13): "minecraft:green_stained_glass", (95, 14): "minecraft:red_stained_glass", (95, 15): "minecraft:black_stained_glass", (97, 0): "minecraft:stone_monster_egg", (98, 0): "minecraft:stone_bricks", (98, 1): "minecraft:mossy_stone_bricks", (98, 2): "minecraft:cracked_stone_bricks", (98, 3): "minecraft:chiseled_stone_bricks", (101, 0): "minecraft:iron_bars", (102, 0): "minecraft:glass_pane", (103, 0): "minecraft:melon", (108, 0): "minecraft:brick_stairs", (109, 0): "minecraft:stone_brick_stairs", (110, 0): "minecraft:mycelium", (112, 0): "minecraft:nether_bricks", (114, 0): "minecraft:nether_brick_stairs", (121, 0): "minecraft:end_stone", (128, 0): "minecraft:sandstone_stairs", (129, 0): "minecraft:emerald_ore", (133, 0): "minecraft:emerald_block", (134, 0): "minecraft:spruce_stairs", (135, 0): "minecraft:birch_stairs", (136, 0): "minecraft:jungle_stairs", (139, 0): "minecraft:cobblestone_wall", (139, 1): "minecraft:mossy_cobblestone_wall", (152, 0): "minecraft:redstone_block", (153, 0): "minecraft:nether_quartz_ore", (155, 0): "minecraft:quartz_block", (155, 1): "minecraft:chiseled_quartz_block", (155, 2): "minecraft:quartz_pillar", (156, 0): "minecraft:quartz_stairs", (159, 0): "minecraft:white_terracotta", (159, 1): "minecraft:orange_terracotta", (159, 2): "minecraft:magenta_terracotta", (159, 3): "minecraft:light_blue_terracotta", (159, 4): "minecraft:yellow_terracotta", (159, 5): "minecraft:lime_terracotta", (159, 6): "minecraft:pink_terracotta", (159, 7): "minecraft:gray_terracotta", (159, 8): "minecraft:light_gray_terracotta", (159, 9): "minecraft:cyan_terracotta", (159, 10): "minecraft:purple_terracotta", (159, 11): "minecraft:blue_terracotta", (159, 12): "minecraft:brown_terracotta", (159, 13): "minecraft:green_terracotta", (159, 14): "minecraft:red_terracotta", (159, 15): "minecraft:black_terracotta", (162, 0): "minecraft:acacia_log", (162, 1): "minecraft:dark_oak_log", (163, 0): "minecraft:acacia_stairs", (164, 0): "minecraft:dark_oak_stairs", (170, 0): "minecraft:hay_block", (172, 0): "minecraft:terracotta", (173, 0): "minecraft:coal_block", (174, 0): "minecraft:packed_ice", (179, 0): "minecraft:red_sandstone", (179, 1): "minecraft:chiseled_red_sandstone", (179, 2): "minecraft:cut_red_sandstone", (180, 0): "minecraft:red_sandstone_stairs", (206, 0): "minecraft:end_bricks", (213, 0): "minecraft:magma_block", (215, 0): "minecraft:bone_block", (251, 0): "minecraft:white_concrete", (251, 1): "minecraft:orange_concrete", (251, 2): "minecraft:magenta_concrete", (251, 3): "minecraft:light_blue_concrete", (251, 4): "minecraft:yellow_concrete", (251, 5): "minecraft:lime_concrete", (251, 6): "minecraft:pink_concrete", (251, 7): "minecraft:gray_concrete", (251, 8): "minecraft:light_gray_concrete", (251, 9): "minecraft:cyan_concrete", (251, 10): "minecraft:purple_concrete", (251, 11): "minecraft:blue_concrete", (251, 12): "minecraft:brown_concrete", (251, 13): "minecraft:green_concrete", (251, 14): "minecraft:red_concrete", (251, 15): "minecraft:black_concrete",
}

class ConverterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(".schematic/.schem to .nbt 转换工具 (终极修复版)")
        self.setGeometry(300, 300, 500, 400)
        central_widget = QWidget(self); self.setCentralWidget(central_widget); layout = QVBoxLayout(central_widget)
        title_label = QLabel("Schematic / Schem 转 NBT 转换器"); title_label.setAlignment(Qt.AlignCenter); title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.select_button = QPushButton("1. 点击选择 .schematic 或 .schem 文件"); self.select_button.setStyleSheet("font-size: 14px; padding: 10px;")
        self.info_label = QLabel("尚未选择文件"); self.info_label.setAlignment(Qt.AlignCenter); self.info_label.setStyleSheet("color: gray; margin-top: 5px;")
        self.convert_button = QPushButton("2. 开始转换！"); self.convert_button.setStyleSheet("font-size: 16px; padding: 12px; background-color: #4CAF50; color: white;"); self.convert_button.setEnabled(False)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        layout.addWidget(title_label); layout.addWidget(self.select_button); layout.addWidget(self.info_label); layout.addWidget(self.convert_button); layout.addWidget(QLabel("转换日志:")); layout.addWidget(self.log_output)
        self.select_button.clicked.connect(self.select_file); self.convert_button.clicked.connect(self.run_conversion); self.source_file_path = None

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "Schematic Files (*.schematic *.schem)")
        if file_path:
            self.source_file_path = file_path; self.info_label.setText(f"已选择: {os.path.basename(file_path)}"); self.info_label.setStyleSheet("color: blue;"); self.convert_button.setEnabled(True); self.log_output.clear(); self.log_output.append(f"准备转换文件: {file_path}")

    def run_conversion(self):
        if not self.source_file_path:
            QMessageBox.warning(self, "错误", "请先选择一个文件！"); return
        base_name = os.path.splitext(self.source_file_path)[0]; dest_file_path = base_name + ".nbt"
        self.log_output.append("\n--- 开始转换 ---"); QApplication.processEvents()
        
        try:
            # --- ★★★ 终极的、绝对的、最终的修复 ★★★ ---
            schematic_data = nbtlib.load(self.source_file_path)
            
            self.log_output.append("✅ 成功读取文件。")

            root = None
            if 'Schematic' in schematic_data:
                self.log_output.append("检测到格式 1: MCEdit (带 'Schematic' 标签)"); root = schematic_data['Schematic']
            elif all(key in schematic_data for key in ['Width', 'Height', 'Length', 'Blocks', 'Data']):
                self.log_output.append("检测到格式 2: MCEdit (无根标签 '散装' 格式)"); root = schematic_data
            elif all(key in schematic_data for key in ['Width', 'Height', 'Length', 'Palette', 'BlockData']):
                self.log_output.append("检测到格式 3: Sponge (.schem) 格式)"); root = schematic_data
            else:
                raise ValueError("无法识别的schematic/schem文件格式。请确保文件未损坏。")

            width = root['Width']; height = root['Height']; length = root['Length']
            self.log_output.append(f"识别到建筑尺寸: 宽(X)={width}, 高(Y)={height}, 长(Z)={length}"); QApplication.processEvents()
            
            voxel_data = {}
            if 'BlockData' in root:
                self.log_output.append("正在从自带调色板解析方块..."); QApplication.processEvents()
                block_data = root['BlockData']; palette_map = {i: str(name) for i, name in root['Palette'].items()}
                for y in range(height):
                    for z in range(length):
                        for x in range(width):
                            index = (y * length + z) * width + x
                            palette_id = block_data[index]
                            block_name_main = palette_map.get(palette_id, "minecraft:air").split('[')[0]
                            if block_name_main != "minecraft:air": voxel_data[(x, y, z)] = block_name_main
            else:
                self.log_output.append("正在使用旧版ID词典翻译方块..."); QApplication.processEvents()
                blocks_array = root['Blocks']; data_array = root['Data']
                for y in range(height):
                    for z in range(length):
                        for x in range(width):
                            index = (y * length + z) * width + x
                            block_id = blocks_array[index]; data_value = data_array[index]
                            block_name = ID_MAPPING.get((block_id, data_value), ID_MAPPING.get((block_id, 0), "minecraft:air"))
                            if block_name != "minecraft:air": voxel_data[(x, y, z)] = block_name

            self.log_output.append(f"✅ 翻译完成！共找到 {len(voxel_data)} 个非空气方块。"); QApplication.processEvents()

            size = [Int(width), Int(height), Int(length)]
            if not voxel_data: palette, blocks = List[Compound]([]), List[Compound]([])
            else:
                unique_blocks = sorted(list(set(voxel_data.values())))
                palette = List([Compound({"Name": String(name)}) for name in unique_blocks])
                block_to_state = {name: i for i, name in enumerate(unique_blocks)}
                blocks = List[Compound]()
                for (pos_tuple, block_name) in voxel_data.items():
                    pos = List[Int]([Int(c) for c in pos_tuple]); state = Int(block_to_state[block_name])
                    blocks.append(Compound({"pos": pos, "state": state}))

            self.log_output.append(f"已创建调色板，包含 {len(palette)} 种方块。")
            nbt_file = nbtlib.File({'DataVersion': Int(3120), 'size': List[Int](size), 'palette': palette, 'blocks': blocks})
            nbt_file.save(dest_file_path, gzipped=True)
            self.log_output.append("\n🎉🎉🎉 转换成功！🎉🎉🎉"); self.log_output.append(f"新的.nbt文件已保存至:"); self.log_output.append(dest_file_path); self.log_output.append("\n--- 转换结束 ---")
            QMessageBox.information(self, "成功", f"文件已成功转换为.nbt！\n\n保存在: {dest_file_path}")

        except Exception as e:
            self.log_output.append(f"\n❌❌❌ 发生致命错误: {e}"); import traceback; self.log_output.append(traceback.format_exc()); QMessageBox.critical(self, "错误", f"转换失败: {e}")

def main():
    app = QApplication(sys.argv)
    window = ConverterWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()