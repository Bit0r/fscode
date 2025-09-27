from pathlib import Path

import networkx as nx
from more_itertools import flatten

# [TODO]: 一种更高效的方法是交换阶段二和阶段三，但是手写代码容易出错，所以暂不实现
# 具体方法如下：
# 1. 在阶段二中，构建一个排除独立节点和自环节点的反图，使用 Kahn 算法该图进行拓扑排序。
#    1. 如果算法成功完成，则可以直接得到一个有效的拓扑排序，说明不存在环。
#    2. 如果算法在运行中发现入度列表中已经不存在入度为 0 的节点，则这些剩余未处理的节点都在环中。
# 2. 在阶段三中，在正向图中删除前面已经处理过的节点
#    然后使用DFS算法对剩余节点进行遍历，每个连通分量都是一个环。
#    因为该图的入度<=1，所以不存在环交叉。


class GraphOperationGenerator:
    """
    分析一个特殊的有向图（所有节点入度<=1），并将其结构直接转换为
    一个包含抽象的 'remove', 'create', 'copy', 'move', 'exchange' 操作的指令列表。

    通过实例化此类来初始化图结构，然后调用 `generate_operations` 方法生成指令。
    """

    def __init__(
        self,
        nodes: list[str],
        edges: list[tuple[str, str]],
        *,
        remove: tuple[str, ...] = ('rm',),
        copy: tuple[str, ...] = ('cp',),
        move: tuple[str, ...] = ('mv',),
        exchange: tuple[str, ...] = ('mv', '--exchange'),
        create: tuple[str, ...] = ('touch',),
    ):
        """
        初始化图并进行基本验证。

        Args:
            nodes: 图中所有节点的列表。
            edges: 图中所有边的列表，以 (u, v) 元组表示从 u 到 v 的边。
            remove: 用于移除操作的命令元组。
            copy: 用于复制操作的命令元组。
            move: 用于移动操作的命令元组。
            exchange: 用于交换操作的命令元组。
            create: 用于创建操作的命令元组。

        Raises:
            ValueError: 如果图中存在入度大于1的节点，或者 '' 节点有入度。
        """
        self.remove_cmd = remove
        self.copy_cmd = copy
        self.move_cmd = move
        self.exchange_cmd = exchange
        self.create_cmd = create

        self.DG = nx.DiGraph()
        self.DG.add_nodes_from(nodes)
        self.DG.add_node('')
        self.DG.add_edges_from(edges)

        self._validate_graph()
        self._classify_nodes()

    def _validate_graph(self):
        """验证图是否符合所有节点入度 <= 1 的要求。"""
        for node, in_degree in self.DG.in_degree:
            if in_degree > 1:
                msg = f"输入图不符合要求：节点 '{node}' 的入度为 {in_degree}，超过了1的限制。"
                raise ValueError(msg)
        if self.DG.in_degree[''] > 0:
            msg = f"输入图不符合要求：节点 '' 的入度为 {self.DG.in_degree['']}，超过了0的限制。"
            raise ValueError(msg)

    def _classify_nodes(self):
        """对图中的节点进行分类：创建、隔离、自环、环内、普通路径。"""
        self.created_nodes = set(self.DG.successors(''))
        # 如果没有创建节点，则将''清除防止后续处理出错
        if not self.created_nodes:
            self.DG.remove_node('')

        self.isolated_nodes = set(nx.isolates(self.DG))
        self.self_loop_nodes = set(nx.nodes_with_selfloops(self.DG))

        classified_nodes = (
            self.isolated_nodes | self.created_nodes | self.self_loop_nodes
        )

        nodes_for_cycle_search = self.DG.subgraph(
            set(self.DG.nodes()) - classified_nodes
        )
        self.cycles = sorted(nx.simple_cycles(nodes_for_cycle_search))

        classified_nodes |= set(flatten(self.cycles))

        # 排除所有特殊节点后，得到普通路径节点集合
        self.normal_nodes_set = set(self.DG.nodes()) - classified_nodes - {''}

    def _generate_remove_operations(self) -> list[list[str]]:
        """生成处理孤立节点的操作 -> remove"""
        return [[*self.remove_cmd, node] for node in sorted(self.isolated_nodes)]

    def _generate_create_operations(self) -> list[list[str]]:
        """生成处理创建节点的操作 -> create"""
        return [[*self.create_cmd, node] for node in sorted(self.created_nodes)]

    def _generate_path_operations(self) -> list[list[str]]:
        """生成处理普通路径节点的操作 -> move 或 copy"""
        operations = []
        normal_nodes_subgraph = self.DG.subgraph(self.normal_nodes_set)
        reversed_subgraph = normal_nodes_subgraph.reverse(copy=True)
        reverse_topological_sort = list(nx.topological_sort(reversed_subgraph))

        out_degrees = dict(self.DG.out_degree)

        for dest_node in reverse_topological_sort:
            predecessors = list(self.DG.predecessors(dest_node))
            if not predecessors:
                continue

            src_node = predecessors[0]

            if out_degrees.get(src_node, 0) > 1:
                operations.append([*self.copy_cmd, src_node, dest_node])
                out_degrees[src_node] -= 1
            else:
                operations.append([*self.move_cmd, src_node, dest_node])

        return operations

    def _generate_cycle_operations(
        self, is_exchange: bool, tmp_name: str
    ) -> list[list[str]]:
        """生成处理环中节点的操作 -> move (使用临时变量) 或 exchange"""
        if not self.cycles:
            return []

        operations = [['#', '开始处理环路']]
        for idx, cycle in enumerate(self.cycles, 1):
            operations.append(['#', f'处理环路{idx}:', *cycle])

            if is_exchange:
                # 使用交换操作，本质是单趟冒泡排序
                for i in range(len(cycle) - 2, -1, -1):
                    operations.append([*self.exchange_cmd, cycle[i], cycle[i + 1]])
            else:
                # 使用临时节点
                temp_node = str(Path(tmp_name).expanduser())
                operations.append([*self.move_cmd, cycle[-1], temp_node])
                for i in range(len(cycle) - 2, -1, -1):
                    operations.append([*self.move_cmd, cycle[i], cycle[i + 1]])
                operations.append([*self.move_cmd, temp_node, cycle[0]])

        operations.append(['#', f'共{len(self.cycles)}个环路'])
        return operations

    def generate_operations(
        self, *, is_exchange: bool = False, tmp_name: str = '__mv_tmp'
    ) -> list[list[str]]:
        """
        生成所有操作指令的最终列表。

        Args:
            is_exchange: 是否使用交换操作处理环路。默认为 False。
            tmp_name: 当不使用交换操作时，用于处理环路的临时名称。

        Returns:
            一个包含所有操作指令的列表。
        """
        return [
            *self._generate_remove_operations(),
            *self._generate_create_operations(),
            *self._generate_path_operations(),
            *self._generate_cycle_operations(is_exchange, tmp_name),
        ]


if __name__ == '__main__':
    all_nodes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
    edge_list = [
        ('a', 'b'),
        ('b', 'c'),
        ('c', 'a'),  # 环: a -> b -> c -> a
        ('c', 'd'),  # 分支
        ('d', 'e'),  # 路径
        ('f', 'g'),
        ('g', 'f'),  # 环: f -> g -> f
        ('f', 'h'),  # 分支
        ('i', 'i'),  # 自环 (会被分类，但不会生成操作)
        ('', 'x'),  # 创建
        ('', 'y'),  # 创建
        # 'j' 是孤立节点
    ]

    # --- 实例化并生成操作 ---
    op_generator = GraphOperationGenerator(all_nodes, edge_list)

    # 1. 使用临时变量处理环路 (is_exchange=False)
    print('=' * 40)
    print('生成的操作指令 (使用临时变量):')
    print('=' * 40)
    final_ops_mv = op_generator.generate_operations(is_exchange=False)
    for op in final_ops_mv:
        print(op)

    # 2. 使用交换操作处理环路 (is_exchange=True)
    print('\n' + '=' * 40)
    print('生成的操作指令 (使用交换操作):')
    print('=' * 40)
    final_ops_exchange = op_generator.generate_operations(is_exchange=True)
    for op in final_ops_exchange:
        print(op)
