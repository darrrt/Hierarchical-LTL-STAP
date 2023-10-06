
from itertools import product
import networkx as nx
from sympy import symbols
from buchi import BuchiConstructor
from data_structure import Node
from workspace_supermarket import Workspace
import copy

class ProductTs(object):
    essential_phi_type_robot_x = set()
    
    def __init__(self) -> None:
        pass
    
    def construct_ts(self, buchi_graph, workspace):
        prod_ts = nx.DiGraph()
        for x, q in list(product(workspace.graph_workspace.nodes(), buchi_graph.nodes())):
            aps_true = symbols(workspace.get_atomic_prop(x))
            next_xs = list(workspace.graph_workspace.neighbors(x))  # next_xs includes x
            node_label = buchi_graph.nodes[q]['label']
            aps_in_label = BuchiConstructor.get_literals(node_label)
            aps_sub = {ap: True if ap in aps_true else False for ap in symbols(aps_in_label)}
            if node_label.subs(aps_sub) == True:
                for next_x in next_xs:
                    weight = 0 if x == next_x else 1
                    prod_ts.add_edge((x, q), (next_x, q), weight=weight)
            
            next_qs = buchi_graph.succ[q]
            for next_q in next_qs:
                edge_label = buchi_graph.edges[(q, next_q)]['label']
                aps_in_label = BuchiConstructor.get_literals(edge_label)
                aps_sub = {ap: True if ap in aps_true else False for ap in symbols(aps_in_label)}
                if edge_label.subs(aps_sub) == True:    
                    for next_x in next_xs:
                        weight = 0 if x == next_x else 1
                        prod_ts.add_edge((x, q), (next_x, next_q), weight=weight)
                    
        return prod_ts
    
    @staticmethod
    def update_non_leaf_specs(last_predicate, node, task_hierarchy, path_to_root, weight, succ):
        predicate = {symbols(phi): True for phi in task_hierarchy.keys() 
                     if node.phis_progress[phi] in task_hierarchy[phi].buchi_graph.graph['accept'] }
        # print(node.phis_progress, predicate)
        tmp_path_to_root = path_to_root.copy()
        parent = tmp_path_to_root.pop(0)
        buchi_graph = task_hierarchy[parent].buchi_graph
        parent_q = node.phis_progress[parent]
        proceed_to_next_q = False
        for next_q in set(buchi_graph.succ[parent_q]): 
            tmp_node = Node(node.phi, node.type_robot, node.action, node.type_robots_x, 
                            node.phis_progress.copy(), node.world_state, 
                            ProductTs.update_progress_metric(task_hierarchy, node.phis_progress))
            edge_label = buchi_graph.edges[(parent_q, next_q)]['label']
            aps_in_label = BuchiConstructor.get_literals(edge_label)
            aps_sub = {ap: True if ap in predicate else False for ap in symbols(aps_in_label)}
            if edge_label.subs(aps_sub):
                tmp_node.phis_progress[parent] = next_q
                proceed_to_next_q = True
            else:
                continue
            if parent == 'p0':
                succ.append([tmp_node, weight])
            else:
                cur_predicate = []
                if next_q in buchi_graph.graph['accept']:
                    cur_predicate.append(symbols(parent))
                ProductTs.update_non_leaf_specs(cur_predicate, tmp_node, task_hierarchy, tmp_path_to_root, weight, succ)
        
        # do not check self-transition if it can move to next node
        if not proceed_to_next_q:
            tmp_node = Node(node.phi, node.type_robot, node.action, node.type_robots_x, 
                            node.phis_progress.copy(), node.world_state, 
                            ProductTs.update_progress_metric(task_hierarchy, node.phis_progress))
            node_label = buchi_graph.nodes[parent_q]['label']
            aps_in_label = BuchiConstructor.get_literals(node_label)
            aps_sub = {ap: True if ap in predicate else False for ap in symbols(aps_in_label)}
            if node_label.subs(aps_sub):
                tmp_node.phis_progress[parent] = parent_q
            else:
                return
            if parent == 'p0':
                succ.append([tmp_node, weight])
            else:
                cur_predicate = []
                ProductTs.update_non_leaf_specs(cur_predicate, tmp_node, task_hierarchy, tmp_path_to_root, weight, succ)
            
    
    @staticmethod
    def update_phis_progress(phis_progress, task_hierarchy, depth_specs):
        # print(phis_progress)
        phis_truth = dict()
        for depth, specs in depth_specs.items():
            if depth == 0:
                for spec in specs:
                    if 'accept' in phis_progress[spec]:
                        phis_truth[symbols(spec)] = True
                    else:
                        phis_truth[symbols(spec)] = False
                continue
            for spec in specs:
                q_progress = set()
                buchi_graph = task_hierarchy[spec].buchi_graph
                for q in phis_progress[spec]:
                    for next_q in buchi_graph.succ[q]:
                        edge_label = buchi_graph.edges[(q, next_q)]['label']
                        if edge_label.subs(phis_truth):
                            q_progress.add(next_q)
                    node_label = buchi_graph.nodes[q]['label']
                    if node_label.subs(phis_truth):
                            q_progress.add(q)
                phis_progress[spec] = tuple(q_progress)
                for q in phis_progress[spec]:
                    if 'accept' in q:
                        phis_truth[symbols(spec)] = True
                        break
                    else:
                        phis_truth[symbols(spec)] = False
                        
    @staticmethod
    def update_progress_metric(task_hierarchy, phis_progress):
        progress_metric = 0
        for phi, state in phis_progress.items():
            progress_metric_per_phi = 0
            buchi_graph = task_hierarchy[phi].buchi_graph
            for init in buchi_graph.graph['init']:
                progress_metric_per_phi = max(progress_metric_per_phi, 
                                              buchi_graph.graph['dist'][init][state])
            progress_metric += progress_metric_per_phi
        return progress_metric

    @staticmethod
    def produce_succ_inside_ps(node: Node, task_hierarchy, workspace: Workspace, spec_info):
        """find successors for the same agent and same spec

        Args:
            node (Node): _description_
            task_hierarchy (_type_): _description_
            workspace (Workspace): _description_
            spec_info (_type_): _description_

        Returns:
            _type_: _description_
        """
        path_to_root = spec_info.path_to_root
        
        # return if the accepting state has been reached, no need to search inside the ps for the same robot
        # unless accepting state is violated
        for parent in path_to_root[node.phi]:
            parent_buchi_graph = task_hierarchy[parent].buchi_graph
            if node.phis_progress[parent] in parent_buchi_graph.graph['accept']:
                return []
            
        x = node.type_robots_x[node.type_robot]
        aps_true = workspace.get_robot_state_based_observations(x) | node.world_state
        actions = workspace.get_obsevation_based_actions(node.type_robot[0], aps_true)
        return ProductTs.produce_succ_inside_ps_mobile_man(node, task_hierarchy, workspace, spec_info, symbols(aps_true), actions)
    
    @staticmethod
    def produce_succ_inside_ps_mobile_man(node: Node, task_hierarchy, workspace: Workspace, spec_info, aps_true, actions):
        """find successors for the same agent and same spec via navigation

        Args:
            node (Node): _description_
            task_hierarchy (_type_): _description_
            workspace (Workspace): _description_
            spec_info (_type_): _description_
            aps_true (_type_): _description_

        Returns:
            _type_: _description_
        """
        leaf_specs = spec_info.leaf_spec_order.keys()
        path_to_root = spec_info.path_to_root
        buchi_graph = task_hierarchy[node.phi].buchi_graph
        x = node.type_robots_x[node.type_robot]
        q = node.phis_progress[node.phi]
        decomp_set = task_hierarchy[node.phi].decomp_sets
        next_xs = workspace.update_robot_state(x)  # next_xs includes x
        succ = []
        action_weight = 10
        # check the edge label
        next_qs = buchi_graph.succ[q]
        for next_q in next_qs:
            edge_label = buchi_graph.edges[(q, next_q)]['label']
            aps_in_label = BuchiConstructor.get_literals(edge_label)
            aps_sub = {ap: True if ap in aps_true else False for ap in symbols(aps_in_label)}
            if edge_label.subs(aps_sub) == True:    
                # update progress of leaf phis if accepting state or decomp state is reached
                updated_phis_progress = node.phis_progress.copy()
                updated_phis_progress[node.phi] = next_q
                cur_predicate = []
                if next_q in buchi_graph.graph['accept']:
                    cur_predicate.append(symbols(node.phi))
                if next_q in buchi_graph.graph['accept'] or next_q in decomp_set:
                    for next_x in next_xs:
                        updated_type_robots_x = node.type_robots_x.copy()
                        updated_type_robots_x[node.type_robot] = next_x
                        weight = 0 if x == next_x else 1
                        for action in actions:
                            updated_world_state = workspace.update_world_state(next_x, action, node.world_state)
                            man_weight = 0 if action == 'default' else action_weight
                            weight += man_weight
                            # update progress of other parent specs 
                            ProductTs.update_non_leaf_specs(cur_predicate, 
                                                            Node(node.phi, node.type_robot, action, updated_type_robots_x, 
                                                                updated_phis_progress, updated_world_state,
                                                                ProductTs.update_progress_metric(task_hierarchy, updated_phis_progress)), 
                                                            task_hierarchy, path_to_root[node.phi][1:], weight, succ)
                            # update essentail x of type_robot
                            if x == next_x and q != next_q:
                                # NOTE consider transition (phi_1, r, x, q_1) -> (phi_2, r, x, q_2) -> (phi_2, r', x', q_2)
                                ProductTs.essential_phi_type_robot_x.update({(other_phi, node.type_robot, x, other_q) for other_phi in leaf_specs
                                                    for other_q in set(task_hierarchy[other_phi].buchi_graph.graph['init']) | \
                                                        set(task_hierarchy[other_phi].buchi_graph.graph['accept']) | \
                                                            set(task_hierarchy[other_phi].decomp_sets)})
                else:
                    for next_x in next_xs:
                        updated_type_robots_x = node.type_robots_x.copy()
                        updated_type_robots_x[node.type_robot] = next_x
                        weight = 0 if x == next_x else 1
                        for action in actions:
                            updated_world_state = workspace.update_world_state(next_x, action, node.world_state)
                            man_weight = 0 if action == 'default' else action_weight
                            weight += man_weight
                            ProductTs.update_non_leaf_specs(cur_predicate, 
                                                            Node(node.phi, node.type_robot, action, updated_type_robots_x, 
                                                                updated_phis_progress, updated_world_state,
                                                                ProductTs.update_progress_metric(task_hierarchy, updated_phis_progress)), 
                                                            task_hierarchy, path_to_root[node.phi][1:], weight, succ)
        # check the node label if no succ found
        if not succ:
            node_label = buchi_graph.nodes[q]['label']
            aps_in_label = BuchiConstructor.get_literals(node_label)
            aps_sub = {ap: True if ap in aps_true else False for ap in symbols(aps_in_label)}
            if node_label.subs(aps_sub) == True:
                for next_x in next_xs:
                    updated_type_robots_x = node.type_robots_x.copy()
                    updated_type_robots_x[node.type_robot] = next_x
                    weight = 0 if x == next_x else 1
                    for action in actions:
                        # self-loop
                        updated_world_state = workspace.update_world_state(next_x, action, node.world_state)
                        man_weight = 0 if action == 'default' else action_weight
                        weight += man_weight
                        # update progress of other parent specs 
                        ProductTs.update_non_leaf_specs([], 
                                                        Node(node.phi, node.type_robot, action, updated_type_robots_x, 
                                                            node.phis_progress, updated_world_state,
                                                            ProductTs.update_progress_metric(task_hierarchy, node.phis_progress)), 
                                                        task_hierarchy, path_to_root[node.phi][1:], weight, succ)
        return succ
    
    @staticmethod
    def get_locations_for_buchi_state(workspace: Workspace, buchi_graph: nx.DiGraph, buchi_state):
        # @TODO consider various capabilities of robots
        target_aps = set() # target ap that enable the transition to buchi_state
        target_cells = []
        for prec in buchi_graph.pred[buchi_state]:
            # get ap that enable the transition to accept node
            target_aps.update(BuchiConstructor.get_positive_literals(buchi_graph.edges[(prec, buchi_state)]['label']))  
        for target_ap in target_aps:
            target_cells.extend(workspace.regions[target_ap])
        return target_cells

    @staticmethod
    def produce_succ_between_ps_same_phi(node:Node, task_hierarchy, workspace: Workspace, path_to_root):
        """find successor with decomp sets for the same spec between consecutive robots

        Args:
            node (Node): _description_
            task_hierarchy (_type_): _description_
            workspace (Workspace): _description_
            path_to_root (_type_): _description_

        Returns:
            _type_: _description_
        """
        # return if the accepting state has been reached, no need to search inside the ps for the same robot
        for parent in path_to_root[node.phi]:
            parent_buchi_graph = task_hierarchy[parent].buchi_graph
            if node.phis_progress[parent] in parent_buchi_graph.graph['accept']:
                return []
            
        type_robots = list(workspace.type_robot_location.keys())
        # prYellow(leaf_spec)
        hierarchy = task_hierarchy[node.phi]
        decomp_set = hierarchy.decomp_sets | set(hierarchy.buchi_graph.graph['init']) | set(hierarchy.buchi_graph.graph['accept'])
        # q is not a decomp state
        q = node.phis_progress[node.phi]
        if q not in decomp_set:
            return []
        # robot is the last one
        idx = type_robots.index(node.type_robot)
        if idx == len(type_robots) - 1:
            return []
        next_type_robot = type_robots[idx + 1]
        # x is not in desired areas that lead to decomp state; different from IJRR paper
        if (node.phi, node.type_robot, node.type_robots_x[node.type_robot], node.phis_progress[node.phi]) not in ProductTs.essential_phi_type_robot_x or \
        (node.phi, next_type_robot, node.type_robots_x[next_type_robot], node.phis_progress[node.phi]) not in ProductTs.essential_phi_type_robot_x:
            return []
        # if node.q not in hierarchy.buchi_graph.graph['init']:
        #     desired_x = ProductTs.get_locations_for_buchi_state(workspace, hierarchy.buchi_graph, node.q)
        #     if node.x not in desired_x and node.x != node.type_robots_x[node.type_robot]:
        #         return []
        action = 'in-spec'
        succ = [Node(node.phi, next_type_robot, action, node.type_robots_x, node.phis_progress, node.world_state, 
                     ProductTs.update_progress_metric(task_hierarchy, node.phis_progress)), 0]
        return [succ]
    
    def produce_succ_between_ps_same_robot(node: Node, task_hierarchy, workspace: Workspace, leaf_phis_order):
        succ = []
        buchi_graph = task_hierarchy[node.phi].buchi_graph
        x = node.type_robots_x[node.type_robot]
        q = node.phis_progress[node.phi]
        # @TODO It seems no need to connect init with init
        # # for the same robot, connect from one init node of a team model to the init node of another team model with init location
        # if q in buchi_graph.graph['init'] and (node.type_robot, x) in ProductTs.essential_type_robot_x:
        #     # update buchi state
        #     for leaf_phi in leaf_phis_order[node.phi]:
        #         leaf_buchi_graph = task_hierarchy[leaf_phi].buchi_graph
        #         for q in leaf_buchi_graph.graph['init']:
        #             updated_phis_progress = node.phis_progress.copy()
        #             updated_phis_progress[leaf_phi] = q
        #             succ.append([Node(leaf_phi, node.type_robot, node.type_robots_x, updated_phis_progress), 0])
        
        # in case of precedence relation, only connect accept to init
        # in case of independence relation, connect all decomp states except init to init   
        # for the same robot, connect from one accept node of a team model to every init node of another team model with target location
        action = 'inter-spec-i'
        if q in buchi_graph.graph['accept'] and (node.phi, node.type_robot, x, q) in ProductTs.essential_phi_type_robot_x:
            # constrain the set of states that can be accepting product states
            # update buchi state
            for leaf_phi in leaf_phis_order[node.phi]: # only connect when precedence relation exists
                leaf_buchi_graph = task_hierarchy[leaf_phi].buchi_graph
                leaf_q = node.phis_progress[leaf_phi]
                if leaf_q in leaf_buchi_graph.graph['init'] and \
                    (leaf_phi, node.type_robot, x, node.phis_progress[leaf_phi]) in ProductTs.essential_phi_type_robot_x:
                    succ.append([Node(leaf_phi, node.type_robot, action, node.type_robots_x, 
                                      node.phis_progress, node.world_state, 
                                      ProductTs.update_progress_metric(task_hierarchy, node.phis_progress)), 0])

        # for the same robot, if two phis are independent, connect from one decomp node of a team model to the current decomp node (if so) of another team model
        hierarchy = task_hierarchy[node.phi]   
        if (q in hierarchy.decomp_sets or q in buchi_graph.graph['accept'] ) and \
            (node.phi, node.type_robot, x, q) in ProductTs.essential_phi_type_robot_x:
            for leaf_phi in leaf_phis_order[node.phi]:
                if node.phi in leaf_phis_order[leaf_phi]:
                    leaf_buchi_graph = task_hierarchy[leaf_phi].buchi_graph
                    leaf_q = node.phis_progress[leaf_phi]
                    leaf_hierarchy = task_hierarchy[leaf_phi]
                    if leaf_q in (leaf_hierarchy.decomp_sets | set(leaf_hierarchy.buchi_graph.graph['init'])) and \
                        (leaf_phi, node.type_robot, node.type_robots_x[node.type_robot], node.phis_progress[leaf_phi]) in ProductTs.essential_phi_type_robot_x:
                        succ.append([Node(leaf_phi, node.type_robot, action, node.type_robots_x, 
                                          node.phis_progress, node.world_state, 
                                          ProductTs.update_progress_metric(task_hierarchy, node.phis_progress)), 0])
            
        # connect from its accept node of a team model to every decomp node of the first robot's team model with corresponding location                
        action = 'inter-spec-ii'
        type_robots = list(workspace.type_robot_location.keys())
        if q in buchi_graph.graph['accept'] and (node.phi, node.type_robot, x, q) in ProductTs.essential_phi_type_robot_x:
                # constrain the set of states that can be accepting product states
                # update buchi state
                for leaf_phi in leaf_phis_order[node.phi]:
                    leaf_buchi_graph = task_hierarchy[leaf_phi].buchi_graph
                    hierarchy = task_hierarchy[leaf_phi]
                    decomp_set = hierarchy.decomp_sets | set(leaf_buchi_graph.graph['init']) | set(leaf_buchi_graph.graph['accept'])
                    leaf_q = node.phis_progress[leaf_phi]
                    if leaf_q in decomp_set and \
                        (leaf_phi, type_robots[0], node.type_robots_x[type_robots[0]], node.phis_progress[leaf_phi]) in ProductTs.essential_phi_type_robot_x:
                        succ.append([Node(leaf_phi, type_robots[0], action, node.type_robots_x, 
                                          node.phis_progress, node.world_state,
                                          ProductTs.update_progress_metric(task_hierarchy, node.phis_progress)), 0])
        return succ
    
    @staticmethod
    def produce_succ(node: Node, task_hierarchy, workspace: Workspace, spec_info):
        return ProductTs.produce_succ_inside_ps(node, task_hierarchy, workspace, spec_info)  + \
            ProductTs.produce_succ_between_ps_same_phi(node, task_hierarchy, workspace, spec_info.path_to_root) + \
                ProductTs.produce_succ_between_ps_same_robot(node, task_hierarchy, workspace, spec_info.leaf_spec_order)