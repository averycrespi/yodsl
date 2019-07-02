from typing import Tuple

from engine.env import Env
from engine.node import Node
from engine.yovec.vector import SimpleVector
from engine.yovec.number import SimpleNumber


def transpile(program: Node) -> Node:
    """Transpile a Yovec program to YOLOL."""
    env = Env(overwrite=False)
    index = 0
    children = []
    for line in program.children:
        child = line.children[0]
        if child.kind == 'import':
            env = _transpile_import(env, child)
        elif child.kind == 'export':
            _transpile_export(env, child)
        elif child.kind == 'let':
            env, index, out_line = _transpile_let(env, index, child)
            children.append(out_line)
        else:
            pass #TODO: raise error
    return Node(kind='program', children=children)


def _transpile_import(env: Env, import_: Node) -> Env:
    """Transpile an import statement."""
    assert import_.kind == 'import'
    ident = import_.children[0].children[0].value
    return env.update(ident, True)


def _transpile_export(env: Env, export: Node):
    """Transpile an export statement."""
    assert export.kind == 'export'
    ident = import_.children[0].children[0].value
    _ = env[ident]


def _transpile_let(env: Env, index: int, let: Node) -> Tuple[Env, int, Node]:
    """Transpile a let statement to a line."""
    assert let.kind == 'let'
    ident = let.children[0].children[0].value
    env, sv = _transpile_vexpr(env, let.children[1])
    env = env.update(ident, (index, sv))
    multi = Node(kind='multi', children=sv.assign(index))
    line = Node(kind='line', children=[multi])
    return env, index+1, line


def _transpile_vexpr(env: Env, vexpr: Node) -> Tuple[Env, SimpleVector]:
    """Transpile a vexpr to a simple vector."""
    if vexpr.kind == 'premap':
        op = vexpr.children[0].kind
        env, sn = _transpile_nexpr(env, vexpr.children[1])
        env, sv = _transpile_vexpr(env, vexpr.children[2])
        return env, sv.premap(op, sn)
    elif vexpr.kind == 'postmap':
        env, sn = _transpile_nexpr(env, vexpr.children[0])
        op = vexpr.children[1].kind
        env, sv = _transpile_vexpr(env, vexpr.children[2])
        return env, sv.postmap(sn, op)
    elif vexpr.kind == 'vecunary':
        op = vexpr.children[0].kind
        env, sv = _transpile_vexpr(env, vexpr.children[1])
        return env, sv.vecunary(op)
    elif vexpr.kind == 'vecbinary':
        env, svl = _transpile_vexpr(env, vexpr.children[0])
        op = vexpr.children[1].kind
        env, svr = _transpile_vexpr(env, vexpr.children[2])
        return env, svl.vecbinary(op, svr)
    elif vexpr.kind == 'variable':
        ident = vexpr.children[0].value
        _, sv = env[ident]
        return env, sv
    elif vexpr.kind == 'vector':
        snums = []
        for nexpr in vexpr.children:
            env, sn = _transpile_nexpr(env, nexpr)
        return env, SimpleVector(snums)
    else:
        pass #TODO: raise error


def _transpile_nexpr(env: Env, nexpr: Node) -> Tuple[Env, SimpleNumber]:
    """Transpile a nexpr to a simple number."""
    if nexpr.kind == 'unary':
        op = nexpr.children[0].kind
        env, sn = _transpile_nexpr(env, nexpr.children[1])
        return env, sn.unary(op)
    elif nexpr.kind == 'binary':
        env, snl = _transpile_nexpr(env, nexpr.children[0])
        op = nexpr.children[1].kind
        env, snr = _transpile_nexpr(env, nexpr.children[2])
        return env, snl.binary(op, snr)
    elif nexpr.kind == 'reduce':
        op = nexpr.children[0].kind
        env, sv = _transpile_vexpr(env, nexpr.children[1])
        return env, sv.reduce(op)
    elif nexpr.kind == 'dot':
        env, sv = _transpile_vexpr(env, nexpr.children[0])
        return sv.dot()
    elif nexpr.kind == 'cross':
        env, sv = _transpile_vexpr(env, nexpr.children[0])
        return sv.cross()
    elif nexpr.kind == 'len':
        env, sv = _transpile_vexpr(env, nexpr.children[0])
        return sv.len()
    elif nexpr.kind in ('external', 'number'):
        return env, SimpleNumber(nexpr.children[0].value)
    else:
        pass #TODO: raise error
