from typing import Tuple, List

from engine.env import Env
from engine.errors import YovecError
from engine.node import Node
from engine.number import SimpleNumber
from engine.vector import SimpleVector


EXPORT_PREFIX = '#exported:'


def transpile_yovec(program: Node) -> Node:
    """Transpile a Yovec program to YOLOL.

    The environment holds multiple types of values:
        variable -> (index, SimpleVector)
        external -> True
        exported -> True
    """
    env = Env(overwrite=False)
    index = 0
    children = []
    exported = []
    for line in program.children:
        child = line.children[0]
        if child.kind == 'import':
            env = _transpile_import(env, child)
        elif child.kind == 'export':
            env, (before, after) = _transpile_export(env, child)
            exported.append((before, after))
        elif child.kind == 'vec_let':
            env, index, out_line = _transpile_vec_let(env, index, child)
            children.append(out_line)
        elif child.kind == 'comment':
            pass
        else:
            raise AssertionError('unknown kind for child: {}'.format(child.kind))
    yolol_program = Node(kind='program', children=children)
    _rename_exports(env, yolol_program, exported)
    return yolol_program


def _rename_exports(env: Env, node: Node, exported: List[Tuple[str, str]]):
    """Rename the exported variables (in-place) in a YOLOL program."""
    #TODO: deepcopy program & not inplace?
    if node.kind == 'variable':
        for before, after in exported:
            prefix = 'v{}e'.format(env[before][0])
            if node.value.startswith(prefix):
                node.value = node.value.replace(prefix, after)
                return
    elif node.children is not None:
        for c in node.children:
            _rename_exports(env, c, exported)


def _transpile_import(env: Env, import_: Node) -> Env:
    """Transpile an import statement."""
    assert import_.kind == 'import'
    ident = import_.children[0].children[0].value
    try:
        return env.update(ident, True)
    except KeyError as e:
        raise YovecError('failed to import variable') from e


def _transpile_export(env: Env, export: Node) -> Tuple[Env, Tuple[str, str]]:
    """Transpile an export statement."""
    assert export.kind == 'export'
    before = export.children[0].children[0].value
    after = export.children[1].children[0].value
    try:
        _ = env[before]
    except KeyError:
        raise YovecError('failed to export variable: variable not found: {}'.format(before))
    try:
        env = env.update('{}{}'.format(EXPORT_PREFIX, before), True)
    except KeyError as e:
        raise YovecError('failed to export variable') from e
    return env, (before, after)


def _transpile_vec_let(env: Env, index: int, let: Node) -> Tuple[Env, int, Node]:
    """Transpile a vector let statement to a line."""
    assert let.kind == 'vec_let'
    ident = let.children[0].children[0].value
    env, sv = _transpile_vexpr(env, let.children[1])
    assignments, sv = sv.assign(index)
    try:
        env = env.update(ident, (index, sv))
    except KeyError as e:
        raise YovecError('failed to assign variable') from e
    multi = Node(kind='multi', children=assignments)
    line = Node(kind='line', children=[multi])
    return env, index+1, line


def _transpile_vexpr(env: Env, vexpr: Node) -> Tuple[Env, SimpleVector]:
    """Transpile a vexpr to a simple vector."""
    if vexpr.kind == 'vec_map':
        op = vexpr.children[0]
        env, sv = _transpile_vexpr(env, vexpr.children[1])
        return env, sv.map(op.kind)
    elif vexpr.kind == 'vec_premap':
        op = vexpr.children[0]
        env, sn = _transpile_nexpr(env, vexpr.children[1])
        env, sv = _transpile_vexpr(env, vexpr.children[2])
        return env, sv.premap(op.kind, sn)
    elif vexpr.kind == 'vec_postmap':
        env, sn = _transpile_nexpr(env, vexpr.children[0])
        op = vexpr.children[1]
        env, sv = _transpile_vexpr(env, vexpr.children[2])
        return env, sv.postmap(sn, op.kind)
    elif vexpr.kind == 'concat':
        env, lsv = _transpile_vexpr(env, vexpr.children[0])
        for rsv in vexpr.children[1:]:
            env, rsv = _transpile_vexpr(env, rsv)
            lsv = lsv.concat(rsv)
        return env, lsv
    elif vexpr.kind == 'vec_unary':
        env, sv = _transpile_vexpr(env, vexpr.children[-1])
        for op in reversed(vexpr.children[:-1]):
            sv = sv.vecunary(op.kind)
        return env, sv
    elif vexpr.kind == 'vec_binary':
        env, lsv = _transpile_vexpr(env, vexpr.children[0])
        ops = vexpr.children[1::2]
        rsvs = vexpr.children[2::2]
        for op, rsv in zip(ops, rsvs):
            env, rsv = _transpile_vexpr(env, rsv)
            lsv = lsv.vecbinary(op.kind, rsv)
        return env, lsv
    elif vexpr.kind == 'variable':
        ident = vexpr.children[0].value
        _, sv = env[ident]
        return env, sv
    elif vexpr.kind == 'vector':
        snums = []
        for nexpr in vexpr.children:
            env, sn = _transpile_nexpr(env, nexpr)
            snums.append(sn)
        return env, SimpleVector(snums)
    else:
        raise AssertionError('unknown kind for vexpr: {}'.format(vexpr.kind))


def _transpile_nexpr(env: Env, nexpr: Node) -> Tuple[Env, SimpleNumber]:
    """Transpile a nexpr to a simple number."""
    if nexpr.kind == 'num_unary':
        env, sn = _transpile_nexpr(env, nexpr.children[-1])
        for op in reversed(nexpr.children[:-1]):
            sn = sn.unary(op.kind)
        return env, sn
    elif nexpr.kind == 'num_binary':
        env, lsn = _transpile_nexpr(env, nexpr.children[0])
        ops = nexpr.children[1::2]
        rsns = nexpr.children[2::2]
        for op, rsn in zip(ops, rsns):
            env, rsn = _transpile_nexpr(env, rsn)
            lsn = lsn.binary(op.kind, rsn)
        return env, lsn
    elif nexpr.kind == 'reduce':
        op = nexpr.children[0]
        env, sv = _transpile_vexpr(env, nexpr.children[1])
        return env, sv.reduce(op.kind)
    elif nexpr.kind == 'dot':
        env, lsv = _transpile_vexpr(env, nexpr.children[0])
        env, rsv = _transpile_vexpr(env, nexpr.children[1])
        return env, lsv.dot(rsv)
    elif nexpr.kind == 'len':
        env, sv = _transpile_vexpr(env, nexpr.children[0])
        return env, sv.len()
    elif nexpr.kind == 'external':
        return env, SimpleNumber(nexpr.children[0].value)
    elif nexpr.kind == 'number':
        try:
            return env, SimpleNumber(int(nexpr.children[0].value))
        except ValueError:
            return env, SimpleNumber(float(nexpr.children[0].value))
    else:
        raise AssertionError('unknown kind for nexpr: {}'.format(vexpr.kind))