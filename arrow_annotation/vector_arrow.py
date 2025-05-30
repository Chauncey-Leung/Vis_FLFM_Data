# -*- coding: utf-8 -*-
"""
vector_arrow.py : VectorArrow and ArrowManager classes for Napari visualization

Copyright (c) 2025 Qianxi Liang (Peking University)

This software is licensed under the MIT License.
You may obtain a copy of the License at

    https://opensource.org/licenses/MIT

Author: Qianxi Liang
Affiliation: Peking University
Date: 2025-05-29
Description:
    This module defines a VectorArrow class for managing a single vector arrow,
    and an ArrowManager class for managing a collection of vector arrows
    in coordination with a QTableWidget for user interaction.
"""

import numpy as np
from qtpy.QtWidgets import QDoubleSpinBox, QComboBox, QPushButton
import numpy as np
import json
import os
class VectorArrow:
    def __init__(self, viewer, start, direction, color, width, opacity):
        self.viewer = viewer
        self.start = start
        self.direction = direction
        self.color = color
        self.width = width
        self.opacity = opacity
        self.layer = self._create_layer()

    def _create_layer(self):
        data = np.array([[self.start, self.direction]])
        layer = self.viewer.add_vectors(
            data,
            edge_color=self.color,
            edge_width=self.width,
            opacity=self.opacity,
            vector_style='arrow',
            name=f"arrow_{id(self)}"
        )
        return layer

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if k == 'color':
                self.layer.edge_color = v
                self.color = v
            elif k == 'width':
                self.layer.edge_width = v
                self.width = v
            elif k == 'opacity':
                self.layer.opacity = v
                self.opacity = v


class ArrowManager:
    def __init__(self, viewer, table):
        self.viewer = viewer
        self.table = table
        self.arrows = []

    def add_arrow(self, start, direction, color='red', width=3, opacity=1.0):
        arrow = VectorArrow(self.viewer, start, direction, color, width, opacity)
        self.arrows.append(arrow)
        self.refresh_table()

    def delete_arrow(self, row):
        arrow = self.arrows.pop(row)
        self.viewer.layers.remove(arrow.layer)
        self.refresh_table()

    def clear_arrows(self):
        for arrow in self.arrows:
            self.viewer.layers.remove(arrow.layer)
        self.arrows.clear()
        self.refresh_table()

    def refresh_table(self):
        # from qtpy.QtWidgets import QDoubleSpinBox, QComboBox, QPushButton
        # import numpy as np
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.arrows))

        for i, arrow in enumerate(self.arrows):
            vec = arrow.layer.data[0]
            start, direction = vec
            end = start + direction

            for j, val in enumerate(end):
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(-9999, 9999)
                spin.setValue(val)
                spin.setFixedWidth(60)
                spin.valueChanged.connect(lambda _, row=i: self.update_vector_from_table(row))
                self.table.setCellWidget(i, j, spin)

            for j, val in enumerate(direction):
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(-9999, 9999)
                spin.setValue(val)
                spin.setFixedWidth(60)
                spin.valueChanged.connect(lambda _, row=i: self.update_vector_from_table(row))
                self.table.setCellWidget(i, 3 + j, spin)

            color_box = QComboBox()
            from main_app import available_colors
            color_box.addItems(available_colors)
            color_box.setCurrentText(arrow.color)
            color_box.currentTextChanged.connect(lambda _, row=i: self.update_color_from_table(row))
            self.table.setCellWidget(i, 6, color_box)

            length_spin = QDoubleSpinBox()
            length_spin.setDecimals(2)
            length_spin.setRange(0.1, 1000)
            length_spin.setValue(np.linalg.norm(direction))
            length_spin.setFixedWidth(50)
            length_spin.valueChanged.connect(lambda _, row=i: self.update_length_from_table(row))
            self.table.setCellWidget(i, 7, length_spin)

            width_spin = QDoubleSpinBox()
            width_spin.setDecimals(2)
            width_spin.setRange(0.1, 50)
            width_spin.setValue(arrow.width)
            width_spin.setFixedWidth(50)
            width_spin.valueChanged.connect(lambda _, row=i: self.update_width_from_table(row))
            self.table.setCellWidget(i, 8, width_spin)

            opacity_spin = QDoubleSpinBox()
            opacity_spin.setDecimals(2)
            opacity_spin.setRange(0.0, 1.0)
            opacity_spin.setSingleStep(0.05)
            opacity_spin.setValue(arrow.opacity)
            opacity_spin.setFixedWidth(55)
            opacity_spin.valueChanged.connect(lambda _, row=i: self.update_opacity_from_table(row))
            self.table.setCellWidget(i, 9, opacity_spin)

            del_btn = QPushButton("Delete")
            del_btn.setFixedWidth(60)
            del_btn.clicked.connect(lambda _, row=i: self.delete_arrow(row))
            self.table.setCellWidget(i, 10, del_btn)

        self.table.blockSignals(False)

    def update_vector_from_table(self, row):
        # import numpy as np
        end = np.array([self.table.cellWidget(row, j).value() for j in range(3)])
        direction = np.array([self.table.cellWidget(row, j).value() for j in range(3, 6)])
        start = end - direction
        arrow = self.arrows[row]
        arrow.layer.data = np.array([[start, direction]])

    def update_color_from_table(self, row):
        color_box = self.table.cellWidget(row, 6)
        color = color_box.currentText()
        self.arrows[row].update(color=color)

    def update_length_from_table(self, row):
        # import numpy as np
        new_length = self.table.cellWidget(row, 7).value()
        arrow = self.arrows[row]
        vec = arrow.layer.data[0]
        direction = vec[1] / np.linalg.norm(vec[1])
        end = vec[0] + vec[1]
        new_start = end - direction * new_length
        new_vec = np.array([[new_start, direction * new_length]])
        arrow.layer.data = new_vec

    def update_width_from_table(self, row):
        new_width = self.table.cellWidget(row, 8).value()
        self.arrows[row].update(width=new_width)

    def update_opacity_from_table(self, row):
        new_opacity = self.table.cellWidget(row, 9).value()
        self.arrows[row].update(opacity=new_opacity)

    def save_to_file(self, path):
        # import json
        # import numpy as np
        data = []
        for arrow in self.arrows:
            vec = arrow.layer.data[0]
            start, direction = vec
            end = start + direction
            data.append({
                'end': end.tolist(),
                'direction': direction.tolist(),
                'edge_color': arrow.color,
                'edge_width': arrow.width,
                'length': np.linalg.norm(direction),
                'opacity': arrow.opacity
            })
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, path):
        # import json
        # import numpy as np
        # import os
        self.clear_arrows()
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            for item in data:
                end = np.array(item['end'])
                direction = np.array(item['direction'])
                self.add_arrow(
                    start=end - direction,
                    direction=direction,
                    color=item.get('edge_color', 'red'),
                    width=item.get('edge_width', 3),
                    opacity=item.get('opacity', 1.0)
                )
