"""
 Copyright (c) 2017-2018 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import networkx as nx

from extensions.front.mxnet.ssd_pattern_remove_flatten import SsdPatternRemoveFlatten
from extensions.front.mxnet.ssd_pattern_remove_reshape import SsdPatternRemoveReshape
from mo.front.common.replacement import FrontReplacementSubgraph
from mo.graph.graph import create_edge
from mo.ops.reshape import Reshape


class SsdPatternFlattenSoftmaxActivation(FrontReplacementSubgraph):
    enabled = True

    def run_before(self):
        return [SsdPatternRemoveFlatten, SsdPatternRemoveReshape]

    def pattern(self):
        return dict(
            nodes=[
                ('softmax_activation', dict(op='Softmax')),
                ('multi_box_detection', dict(op='_contrib_MultiBoxDetection'))
            ],
            edges=[
                ('softmax_activation', 'multi_box_detection', {'in': 1})
            ]
        )

    def replace_sub_graph(self, graph: nx.MultiDiGraph, match: dict):
        """
        Need to find the pattern: SoftmaxActivation -> DetectionOutput
        DetectionOutput in IE expects flattened input from SoftMax, that is why there is the need to add
        Flatten layer

        Parameters
        ----------
        graph : nx.MultiDiGraph
           Graph with loaded model.
         match : dict
           Patterns which were found in graph structure.
        """
        softmax_activation = match['softmax_activation']
        multi_box_detection = match['multi_box_detection']
        softmax_activation['axis'] = -1
        edge_data = graph.get_edge_data(softmax_activation.id, multi_box_detection.id)
        out_port = edge_data[0]['out']
        in_port = edge_data[0]['in']
        graph.remove_edge(softmax_activation.id, multi_box_detection.id)
        symbol_node = dict(
            op='Flatten',
            name=multi_box_detection.name + '/Reshape_',
            dim=[0, -1],
            axis=1,
            end_axis=-1
        )
        new_reshape_op = Reshape(graph, {'symbol_dict': symbol_node})
        new_reshape_node = new_reshape_op.create_node([softmax_activation])
        new_reshape_node['dim'] = [0, -1]
        create_edge(new_reshape_node, multi_box_detection, in_port=in_port, out_port=out_port)
