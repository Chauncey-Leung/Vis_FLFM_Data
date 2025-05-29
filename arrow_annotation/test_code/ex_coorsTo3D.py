"""现在先只是尝试箭头合并"""
import numpy as np
import napari
import tifffile

# 假设原图像是 uint16 类型的三维图像
# Img shape: (Z=17, Y=923, X=921)
volume = tifffile.imread('recon_ss_single_0007.tiff')   # 你可以替换成实际数据

# 假设你要标注的细胞位置在图像中的坐标为：(z=8, y=400, x=450)
# end_point = np.array([8, 400, 450])
# direction = np.array([4, 30, 20]) * 0.1 # 箭头方向（你可以自己设）
# start_point = end_point - direction

direction = np.array([0, 50, 50])            # 箭头方向和长度
unit_direction = direction / np.linalg.norm(direction)

target_point = np.array([40, 420, 470])      # 箭头末端（箭头指向的地方）
start_point = target_point - unit_direction * 25

# 构造 Napari 所需的 vectors 数据 (N, 2, 3)
# 第一个维度是箭头数量（这里是1个箭头）
arrow_data = np.array([[start_point, target_point - start_point]])

# 可视化
viewer = napari.Viewer(ndisplay=3)
layer = viewer.add_image(volume,
                         colormap='green',
                         scale=(5, 0.91, 0.91),
                         rendering='mip')
viewer.add_points([target_point], name="Target", size=10, face_color='blue')
viewer.add_points([start_point], name="Start", size=10, face_color='orange')
viewer.add_vectors(
    arrow_data,
    edge_color='red',
    name='Arrow',
    vector_style='arrow',
    edge_width=3,
    length=1,         # 显示缩放因子
    opacity=1.0
    # ,
    # scale=(5, 0.91, 0.91)
)

napari.run()
