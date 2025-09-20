from pathlib import Path

import networkx as nx

# [TODO]: 一种更高效的方法是交换阶段二和阶段三，但是手写代码容易出错，所以暂不实现
# 具体方法如下：
# 1. 在阶段二中，构建一个排除独立节点和自环节点的反图，使用 Kahn 算法该图进行拓扑排序。
#    1. 如果算法成功完成，则可以直接得到一个有效的拓扑排序，说明不存在环。
#    2. 如果算法在运行中发现入度列表中已经不存在入度为 0 的节点，则这些剩余未处理的节点都在环中。
# 2. 在阶段三中，在正向图中删除前面已经处理过的节点
#    然后使用DFS算法对剩余节点进行遍历，每个连通分量都是一个环。
#    因为该图的入度<=1，所以不存在环交叉。


def graph2operations(
    nodes,
    edges,
    *,
    rm=('rm',),
    cp=('cp',),
    mv=('mv',),
    tmp_name='__mv_tmp',
    is_exchange=False,
    mv_exchange=('mv', '--exchange'),
):
    """
    分析一个特殊的有向图（所有节点入度<=1），并将其结构直接转换为
    一个包含 'rm', 'cp', 'mv' 操作的指令列表。
    """
    # 阶段一：创建图并验证
    DG = nx.DiGraph()
    DG.add_nodes_from(nodes)
    DG.add_edges_from(edges)

    # 验证逻辑：确保所有节点入度 <= 1
    for node, in_degree in DG.in_degree():  # type: ignore
        if in_degree > 1:
            msg = (
                f"输入图不符合要求：节点 '{node}' 的入度为 {in_degree}，超过了1的限制。"
            )
            raise ValueError(msg)

    # 阶段二：节点分类
    isolated_nodes = set(nx.isolates(DG))
    self_loop_nodes = set(nx.nodes_with_selfloops(DG))

    nodes_for_cycle_search = DG.subgraph(
        [n for n in DG.nodes() if n not in isolated_nodes and n not in self_loop_nodes]
    )
    cycles = list(nx.simple_cycles(nodes_for_cycle_search))

    nodes_in_cycles = set()
    for cycle in cycles:
        nodes_in_cycles.update(cycle)

    classified_nodes = isolated_nodes.union(self_loop_nodes).union(nodes_in_cycles)

    # 排除独立节点，自环和环中节点之后，得到普通节点集合
    normal_nodes_set = {n for n in DG.nodes() if n not in classified_nodes}

    # 阶段三：对只有普通节点的子图的反图，进行拓扑排序
    normal_nodes_subgraph = DG.subgraph(normal_nodes_set)
    reversed_normal_nodes_subgraph = normal_nodes_subgraph.reverse(copy=True)  # type: ignore
    reverse_topological_sort = list(nx.topological_sort(reversed_normal_nodes_subgraph))

    # 阶段四：生成操作指令
    operations = []

    # 1. 处理孤立节点 -> rm
    for node in sorted(isolated_nodes):
        # 排序使输出稳定
        operations.append([*rm, node])

    # 2. 处理普通节点（路径） -> mv 或 cp
    # 获取所有节点的出度
    out_degrees = {u: deg for u, deg in DG.out_degree()}
    for dest_node in reverse_topological_sort:
        predecessors = list(DG.predecessors(dest_node))
        if not predecessors:
            # 如果目标节点没有前驱，则跳过
            continue

        src_node = predecessors[0]

        if out_degrees[src_node] > 1:
            # 出度大于1，必须使用 cp
            operations.append([*cp, src_node, dest_node])
            # 将其源节点的出度减 1
            out_degrees[src_node] -= 1
        else:
            # 源节点的出度等于1，直接使用 mv
            operations.append([*mv, src_node, dest_node])

    if not cycles:
        # 如果没有环路，直接返回操作
        return operations

    # 3. 处理环中节点 -> mv (使用临时变量) 或 mv_exchange (使用交换操作， 本质是单趟冒泡排序)
    # 对环路排序，确保每次运行的输出顺序一致
    operations.append(['#', '开始处理环路'])
    sorted_cycles = sorted(cycles, key=lambda x: (len(x), x[0]))
    for idx, cycle in enumerate(sorted_cycles, 1):
        # 增加一个注释，表示这是一个环路
        operations.append(['#', f'处理环路{idx}:', *cycle])

        if not is_exchange:
            # 如果不能进行交换操作，则必须使用临时节点保存环中的最后一个节点
            temp_node = Path(tmp_name).expanduser()
            temp_node = str(temp_node)
            operations.append([*mv, cycle[-1], temp_node])

        # 从倒数第2个节点开始，依次操作到第0个节点
        for i in range(len(cycle) - 2, -1, -1):
            if is_exchange:
                operations.append([*mv_exchange, cycle[i], cycle[i + 1]])
                # 使用交换后，在cycle中同时模拟交换操作
                cycle[i], cycle[i + 1] = cycle[i + 1], cycle[i]
            else:
                operations.append([*mv, cycle[i], cycle[i + 1]])
                # 单向移动，不需要在cycle中模拟交换操作

        if not is_exchange:
            # 恢复临时节点到第一个节点
            operations.append([*mv, temp_node, cycle[0]])
    operations.append(['#', f'共{len(sorted_cycles)}个环路'])
    return operations


if __name__ == '__main__':
    # --- 演示 ---
    all_nodes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
    edge_list = [
        ('a', 'b'),
        ('b', 'c'),
        ('c', 'a'),
        ('c', 'd'),
        ('d', 'e'),
        ('f', 'g'),
        ('g', 'f'),
        ('f', 'h'),
        ('i', 'i'),
    ]

    # all_nodes = ['a']
    # edge_list = [('a', 'b'), ('a', 'c')]

    # --- 直接调用新函数并打印结果 ---
    print('=' * 40)
    print('生成的操作指令 (单一函数版本):')
    print('=' * 40)
    try:
        final_ops = graph2operations(all_nodes, edge_list)
        for op in final_ops:
            print(op)
    except ValueError as e:
        print(f'出现错误: {e}')

    # --- 直接调用新函数并打印结果 ---
    print('=' * 40)
    print('生成的操作指令 (单一函数版本):')
    print('=' * 40)
    try:
        final_ops = graph2operations(all_nodes, edge_list, is_exchange=True)
        for op in final_ops:
            print(op)
    except ValueError as e:
        print(f'出现错误: {e}')
