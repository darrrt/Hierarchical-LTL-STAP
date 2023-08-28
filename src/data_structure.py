from collections import namedtuple

Hierarchy = namedtuple('Hierarchy', ['level', 'phi', 'buchi_graph', 'decomp_sets', 'hass_graph', 'element2edge'])
PrimitiveSubtask = namedtuple('PrimitiveSubtask', ['element_in_poset'])
CompositeSubtask = namedtuple('CompositeSubtask', ['subtask2element'])
PrimitiveSubtaskId = namedtuple('PrimitiveSubtaskId', ['parent', 'element'])

class Node:
    def __init__(self, phi, type_robot, x, q, type_robots_x, phis_progress):
        # specific spec
        self.phi = phi
        # specific type_robot 
        self.type_robot = type_robot
        # state of type_robot
        self.x = x
        # buchi state of the NBA of specific spec
        self.q = q
        # snapshot of type_robots distribution: dict[type_robot] = x
        self.type_robots_x = type_robots_x
        # progress of leaf specs: dict[spec] = q
        self.phis_progress = phis_progress
        
    # Implementing __eq__ is necessary to compare objects for equality
    def __eq__(self, other):
        if isinstance(other, Node):
            return self.phi == other.phi and self.hash_dict(self.type_robots_x) == self.hash_dict(other.type_robots_x) and \
                    self.hash_dict(self.phis_progress) == self.hash_dict(other.phis_progress)
        return False
    
    def __lt__(self, other):
        if isinstance(other, Node):
            num_self_accept = len([q for q in self.phis_progress.values() if 'accept' in q ])
            num_other_accept = len([q for q in other.phis_progress.values() if 'accept' in q ])
            return num_self_accept < num_other_accept
        return NotImplemented
    
    # Implementing __hash__ method to make instances usable as keys in dictionaries
    def __hash__(self):
        return hash((self.phi, self.hash_dict(self.type_robots_x), self.hash_dict(self.phis_progress)))
    
    def hash_dict(self, d):
        return hash(tuple(sorted(d.items())))
    
    def __str__(self):
        return f"{self.phi} {self.type_robot} {self.x} {self.q} {self.type_robots_x} {self.phis_progress}"