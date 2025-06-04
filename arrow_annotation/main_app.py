# -*- coding: utf-8 -*-
"""
napari-arrow_annotation-app : Interactive 3D vector arrow editor for TIFF stacks using Napari

Copyright (c) 2025 Qianxi Liang (Peking University)

This software is licensed under the MIT License.
You may obtain a copy of the License at

    https://opensource.org/licenses/MIT

Author: Qianxi Liang
Affiliation: Peking University
Date: 2025-05-29
Description:
    This is the main application entry point that sets up the GUI,
    connects UI widgets, and integrates vector and TIFF managers.
"""

import os
import numpy as np
import napari
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QLineEdit, QFileDialog, QMenu
)
from vector_arrow import ArrowManager
from tiff_manager import TIFFManager
import glob
import json

with open('config.json', 'r') as f:
    config = json.load(f)
default_path = config['default_path']
available_colors = config['available_colors']
image_pixel_size = tuple(config['image_pixel_size'])
default_colormap = config['default_colormap']
default_arrow_direction = np.array(config['default_arrow_direction'])
default_arrow_length = config['default_arrow_length']
default_arrow_color = config['default_arrow_color']
default_arrow_width = config['default_arrow_width']
default_arrow_opacity = config['default_arrow_opacity']

tif_files = sorted(glob.glob(os.path.join(default_path, '*.tif'))
                   + glob.glob(os.path.join(default_path, '*.tiff')))
default_json_path = os.path.splitext(tif_files[0])[0] + '.json'


class MainApp:
    def __init__(self):
        self.viewer = napari.Viewer(ndisplay=3)
        self.ray_info = {'first': None, 'second': None}

        self.table = self._init_table()
        self.save_path_input = QLineEdit()
        self.load_path_input = QLineEdit()
        self.view_path_input = QLineEdit()
        self.snapshot_dir = os.path.join(default_path, 'snapshots')
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self.arrow_manager = ArrowManager(self.viewer, self.table)
        self.tiff_manager = TIFFManager(self.viewer,
                                        default_path,
                                        default_json_path,
                                        self.load_vectors)

        self._init_ui()
        self.tiff_manager.load_current()
        # self._add_volume_bounding_box()
        self._add_enhanced_frame_and_grid(grid_interval=60)

        self.viewer.layers.selection.clear()
        self.viewer.layers.selection.add(self.tiff_manager.image_layer)

        self.tiff_manager.image_layer.mouse_double_click_callbacks.clear()
        self.tiff_manager.image_layer.mouse_double_click_callbacks.append(self.handle_right_click)

    def _init_table(self):
        table = QTableWidget()
        table.setColumnCount(11)
        table.setHorizontalHeaderLabels([
            'End Z', 'End Y', 'End X',
            'Dir Z', 'Dir Y', 'Dir X',
            'Color', 'Length', 'Width', 'Opacity', 'Delete'
        ])
        for i in range(6):
            table.setColumnWidth(i, 60)
        table.setColumnWidth(6, 70)
        table.setColumnWidth(7, 50)
        table.setColumnWidth(8, 50)
        table.setColumnWidth(9, 55)
        table.setColumnWidth(10, 65)
        return table

    def _init_ui(self):
        save_btn = QPushButton("Save Vectors")
        load_btn = QPushButton("Load Vectors")
        clear_btn = QPushButton("Clear Vectors")
        prev_btn = QPushButton("Prev TIFF")
        next_btn = QPushButton("Next TIFF")
        sync_view_btn = QPushButton("Synchronous view")
        change_path_btn = QPushButton("Select Folder")
        snap_btn = QPushButton("Snapshot")

        self.save_path_input.setText(default_json_path)
        self.load_path_input.setText(default_json_path)
        self.view_path_input.setText(os.path.join(self.snapshot_dir, 'example_view.npz'))

        controls = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(change_path_btn)

        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.save_path_input)
        hlayout1.addWidget(save_btn)
        layout.addLayout(hlayout1)

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.load_path_input)
        hlayout2.addWidget(load_btn)
        layout.addLayout(hlayout2)

        hlayout3 = QHBoxLayout()
        hlayout3.addWidget(self.view_path_input)
        hlayout3.addWidget(sync_view_btn)
        layout.addLayout(hlayout3)

        layout.addWidget(clear_btn)

        hlayout4 = QHBoxLayout()
        hlayout4.addWidget(prev_btn)
        hlayout4.addWidget(next_btn)
        layout.addLayout(hlayout4)

        layout.addWidget(snap_btn)
        layout.addWidget(self.table)

        controls.setLayout(layout)
        controls.setMinimumWidth(680)
        self.viewer.window.add_dock_widget(controls, area='right')

        save_btn.clicked.connect(self.save_vectors)
        load_btn.clicked.connect(self.load_vectors_from_input)
        clear_btn.clicked.connect(self.arrow_manager.clear_arrows)
        # prev_btn.clicked.connect(self.tiff_manager.prev)
        prev_btn.clicked.connect(self.prev_tif)
        # next_btn.clicked.connect(self.tiff_manager.next)
        next_btn.clicked.connect(self.next_tif)
        change_path_btn.clicked.connect(self.change_default_path)
        snap_btn.clicked.connect(self.save_snapshot_and_view)
        sync_view_btn.clicked.connect(self.restore_view_from_textbox)

    def prev_tif(self):
        self.save_vectors()
        self.arrow_manager.clear_arrows()
        self.tiff_manager.prev()
        current_json = self.tiff_manager.json_path
        self.save_path_input.setText(current_json)

        self._clear_enhanced_grid()
        self._add_enhanced_frame_and_grid(grid_interval=60)

        self.tiff_manager.image_layer.mouse_double_click_callbacks.clear()
        self.tiff_manager.image_layer.mouse_double_click_callbacks.append(self.handle_right_click)
        self.viewer.layers.selection.clear()
        self.viewer.layers.selection.add(self.tiff_manager.image_layer)

    def next_tif(self):
        self.save_vectors()
        self.arrow_manager.clear_arrows()
        self.tiff_manager.next()
        current_json = self.tiff_manager.json_path
        self.save_path_input.setText(current_json)

        self._clear_enhanced_grid()
        self._add_enhanced_frame_and_grid(grid_interval=60)

        self.tiff_manager.image_layer.mouse_double_click_callbacks.clear()
        self.tiff_manager.image_layer.mouse_double_click_callbacks.append(self.handle_right_click)
        self.viewer.layers.selection.clear()
        self.viewer.layers.selection.add(self.tiff_manager.image_layer)

    def save_vectors(self):
        path = self.save_path_input.text()
        self.arrow_manager.save_to_file(path)

    def load_vectors(self, path):
        self.arrow_manager.load_from_file(path)

    def load_vectors_from_input(self):
        self.load_vectors(self.load_path_input.text())
        self.tiff_manager.image_layer.mouse_double_click_callbacks.clear()
        self.tiff_manager.image_layer.mouse_double_click_callbacks.append(self.handle_right_click)
        self.viewer.layers.selection.clear()
        self.viewer.layers.selection.add(self.tiff_manager.image_layer)

    def change_default_path(self):
        new_path = QFileDialog.getExistingDirectory(None, "Select Folder", default_path)
        if new_path:
            tif_files = sorted(glob.glob(os.path.join(new_path, '*.tif'))
                               + glob.glob(os.path.join(new_path, '*.tiff')))
            first_tif = os.path.splitext(tif_files[0])[0]

            self.tiff_manager.folder_path = new_path
            self.tiff_manager.reload_file_list()
            self.save_path_input.setText(os.path.join(new_path, f'{first_tif}.json'))
            self.load_path_input.setText(os.path.join(new_path, f'{first_tif}.json'))
            self.tiff_manager.load_current()

            self._clear_enhanced_grid()
            self._add_enhanced_frame_and_grid(grid_interval=60)

            self.viewer.layers.selection.clear()
            self.viewer.layers.selection.add(self.tiff_manager.image_layer)

            self.tiff_manager.image_layer.mouse_double_click_callbacks.clear()
            self.tiff_manager.image_layer.mouse_double_click_callbacks.append(self.handle_right_click)
            self.snapshot_dir = os.path.join(new_path, 'snapshots')
            os.makedirs(self.snapshot_dir, exist_ok=True)
            # self.save_path_input.setText(current_json)
            # self.load_path_input.setText(current_json)

    def save_snapshot_and_view(self):
        base_name = os.path.basename(self.tiff_manager.get_current_file_name())
        # snapshot_path = os.path.join(self.snapshot_dir, f'{base_name}_snapshot.png')
        snapshot_path = os.path.join(self.snapshot_dir,
                                     f'{os.path.splitext(base_name)[0]}_snapshot.png')
        # view_path = os.path.join(self.snapshot_dir, f'{base_name}_view.npz')
        view_path = os.path.join(self.snapshot_dir,
                                 f'{os.path.splitext(base_name)[0]}_view.npz')
        self.viewer.screenshot(snapshot_path, canvas_only=True, scale=4)
        np.savez(view_path,
                 dims_point=self.viewer.dims.point,
                 cam_center=self.viewer.camera.center,
                 cam_angles=self.viewer.camera.angles,
                 cam_zoom=self.viewer.camera.zoom)
        print(f"Saved images and perspectives: {snapshot_path}")

    def restore_view_from_textbox(self):
        path = self.view_path_input.text()
        if os.path.exists(path):
            params = np.load(path)
            for i, val in enumerate(params['dims_point']):
                self.viewer.dims.set_point(i, val)
            self.viewer.camera.center = params['cam_center']
            self.viewer.camera.angles = params['cam_angles']
            self.viewer.camera.zoom = params['cam_zoom']
            print(f"View restored：{path}")

    def handle_right_click(self, layer, event):
        if event.button != 2:
            return

        pos, direction = self.get_camera_ray(event)
        menu = QMenu()
        act1 = menu.addAction("First Click")
        act2 = menu.addAction("Second Click")
        action = menu.exec_(event.native.globalPos())
        if action == act1:
            self.ray_info['first'] = (pos, direction)
        elif action == act2:
            self.ray_info['second'] = (pos, direction)

        if self.ray_info['first'] and self.ray_info['second']:
            p1, d1 = self.ray_info['first']
            p2, d2 = self.ray_info['second']
            mid = self.triangulate_rays(p1, d1, p2, d2)

            # image_pixel_size = (5, 0.91, 0.91)
            # default_arrow_length = 25
            # default_arrow_direction =  np.array([0, 1, 1])
            # default_arrow_color = 'red'
            # default_arrow_width = 3
            # default_arrow_opacity = 1.0
            target_point = mid[[2, 1, 0]]
            direction = np.array([0, 1, 1])
            unit_direction = direction / np.linalg.norm(direction)
            start_point = target_point - unit_direction * default_arrow_length

            if mid is not None:
                self.arrow_manager.add_arrow(
                    start=start_point,
                    direction=unit_direction * default_arrow_length,
                    color=default_arrow_color,
                    width=default_arrow_width,
                    opacity=default_arrow_opacity)

                self.viewer.layers.selection.clear()
                self.viewer.layers.selection.add(self.tiff_manager.image_layer)

            self.ray_info['first'] = None
            self.ray_info['second'] = None

    def get_camera_ray(self, event):
        """
        Get the function of a space line: p0 + t * dir t \in (-\infty, +\infty)
        based on the location where the mouse is clicked
        :return near: the coordinate of p0 (x,y,z)
        :return dir / np.linalg.norm(dir): the normalized direction of the line (x,y,z)
        """
        view = self.viewer.window.qt_viewer.view
        transform = view.scene.transform
        pos = np.array(event.pos)
        p_near = np.array([*pos, 0, 1])
        p_far = np.array([*pos, 1, 1])
        near = transform.imap(p_near)[:3]
        far = transform.imap(p_far)[:3]
        dir = far - near
        return near, dir / np.linalg.norm(dir)

    def triangulate_rays(self, p1, d1, p2, d2):
        """
        Get the coordinates of the closest point between two non-coplanar lines
        """
        w0 = p1 - p2
        a, b, c = np.dot(d1, d1), np.dot(d1, d2), np.dot(d2, d2)
        d, e = np.dot(d1, w0), np.dot(d2, w0)
        denom = a * c - b * b
        if np.isclose(denom, 0): return None
        t, s = (b * e - c * d) / denom, (a * e - b * d) / denom
        return (p1 + t * d1 + p2 + s * d2) / 2

    # def _add_volume_bounding_box(self):
    #     from main_app import image_pixel_size
    #     image = self.image_layer
    #     if image is None:
    #         return
    #     else:
    #         if image.ndim != 3:
    #             return
    #
    #         z, y, x = image.data.shape
    #         box_vertices = np.array([
    #             [0, 0, 0],
    #             [0, 0, x],
    #             [0, y, 0],
    #             [0, y, x],
    #             [z, 0, 0],
    #             [z, 0, x],
    #             [z, y, 0],
    #             [z, y, x],
    #         ])
    #         box_vertices = box_vertices * list(image_pixel_size)
    #
    #         # 立方体边缘12条线
    #         edges = [
    #             [box_vertices[i], box_vertices[j]] for i, j in [
    #                 (0, 1), (0, 2), (1, 3), (2, 3),  # bottom face
    #                 (4, 5), (4, 6), (5, 7), (6, 7),  # top face
    #                 (0, 4), (1, 5), (2, 6), (3, 7)  # vertical edges
    #             ]
    #         ]
    #
    #         # 添加 Shapes 图层
    #         self.viewer.add_shapes(
    #             data=edges,
    #             shape_type='line',
    #             edge_color='white',
    #             edge_width=1,
    #             name='3D Bounding Box',
    #             blending='translucent',
    #             opacity=0.4
    #         )

    def _add_enhanced_frame_and_grid(self, grid_interval=10):
        """添加优化版的边框和网格，用于增强3D感知"""
        image = self.tiff_manager.image_layer
        if image.ndim != 3:
            return

        scale = np.array(image.scale)
        shape = np.array(image.data.shape)
        z, y, x = shape * scale

        # === 1. 立方体 8 顶点 ===
        verts = np.array([
            [0, 0, 0], [0, 0, x], [0, y, 0], [0, y, x],
            [z, 0, 0], [z, 0, x], [z, y, 0], [z, y, x]
        ])
        # 12条边
        edges = [[verts[i], verts[j]] for i, j in [
            (0, 1), (0, 2), (1, 3), (2, 3),
            (4, 5), (4, 6), (5, 7), (6, 7),
            (0, 4), (1, 5), (2, 6), (3, 7)
        ]]
        self.viewer.add_shapes(
            data=edges,
            shape_type='line',
            edge_color='white',
            edge_width=1,
            opacity=0.1,
            name='Bounding Box',
            blending='additive'
        )

        # === 2. 网格线：只绘底面和顶面两个 XY 面 ===
        grid_lines = []
        z_plane = z
        for xi in np.arange(0, x + 1e-3, grid_interval):
            grid_lines.append([[z_plane, 0, xi], [z_plane, y, xi]])
        for yi in np.arange(0, y + 1e-3, grid_interval):
            grid_lines.append([[z_plane, yi, 0], [z_plane, yi, x]])

        for x_plane in [0, x]:
            for zi in np.arange(0, z + 1e-3, grid_interval):
                grid_lines.append([[zi, 0, x_plane], [zi, y, x_plane]])
            for yi in np.arange(0, y + 1e-3, grid_interval):
                grid_lines.append([[0, yi, x_plane], [z, yi, x_plane]])

        for y_plane in [0, y]:
            for zi in np.arange(0, z + 1e-3, grid_interval):
                grid_lines.append([[zi, y_plane, 0], [zi, y_plane, x]])
            for xi in np.arange(0, x + 1e-3, grid_interval):
                grid_lines.append([[0, y_plane, xi], [z, y_plane, xi]])

        self.viewer.add_shapes(
            data=grid_lines,
            shape_type='line',
            edge_color='white',
            edge_width=0.8,
            opacity=0.04,
            name='Grid XY Planes',
            blending='translucent'
        )

    def _clear_enhanced_grid(self):
        for name in ['Bounding Box', 'Grid XY Planes']:
            if name in self.viewer.layers:
                self.viewer.layers.remove(name)

if __name__ == '__main__':
    app = MainApp()
    napari.run()
