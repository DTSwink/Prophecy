"""Remove shape-proven empty arithmetic from a fixed-batch ONNX graph.

The source skeleton has zero optional FK channels. PyTorch represents their
unused cleanup with empty tensors; some ORT kernels reject that arithmetic.
Only tensors whose complete static shape contains an explicit zero are folded.
No nonempty value, network weight, or runtime-dependent branch is changed.
"""
import numpy as np
import onnx


def share_identical_expressions(model):
    """Exact CSE: share equal constants and identical deterministic operations."""
    import hashlib
    aliases, tensors, constants = {}, [], {}

    def resolve(name):
        while name in aliases:
            name = aliases[name]
        return name

    for tensor in model.graph.initializer:
        data = onnx.numpy_helper.to_array(tensor)
        key = (tensor.data_type, tuple(tensor.dims), hashlib.sha256(data.tobytes()).digest())
        if key in constants:
            aliases[tensor.name] = constants[key]
        else:
            constants[key] = tensor.name
            tensors.append(tensor)
    nodes, seen = [], {}
    for node in model.graph.node:
        for index, value in enumerate(node.input):
            node.input[index] = resolve(value)
        key = (node.domain, node.op_type, tuple(node.input),
               tuple(sorted(a.SerializeToString() for a in node.attribute)), len(node.output))
        safe = not (node.op_type.startswith("Random") or node.op_type in ("Dropout", "Multinomial") or
                    any(a.type in (onnx.AttributeProto.GRAPH, onnx.AttributeProto.GRAPHS) for a in node.attribute))
        if safe and key in seen:
            for old, replacement in zip(node.output, seen[key]):
                aliases[old] = replacement
        else:
            nodes.append(node)
            if safe:
                seen[key] = tuple(node.output)
    for output in model.graph.output:
        replacement = resolve(output.name)
        if replacement != output.name:
            nodes.append(onnx.helper.make_node("Identity", [replacement], [output.name]))
    removed = len(model.graph.node) - len(nodes)
    model.graph.ClearField("node")
    model.graph.node.extend(nodes)
    model.graph.ClearField("initializer")
    model.graph.initializer.extend(tensors)
    onnx.checker.check_model(model)
    return removed


def fold_static_empty_tensors(model):
    empty = {}
    for value in model.graph.value_info:
        tensor = value.type.tensor_type
        dims = tensor.shape.dim
        if dims and all(d.HasField("dim_value") for d in dims) and any(d.dim_value == 0 for d in dims):
            empty[value.name] = onnx.numpy_helper.from_array(
                np.empty(tuple(d.dim_value for d in dims), dtype=onnx.helper.tensor_dtype_to_np_dtype(tensor.elem_type)),
                name=value.name)
    produced = set()
    for node in model.graph.node:
        for index, output in enumerate(node.output):
            if output in empty:
                produced.add(output)
                node.output[index] = output + "__unused_empty"
    model.graph.initializer.extend(empty[name] for name in produced)
    required = {v.name for v in model.graph.output}
    retained = []
    for node in reversed(model.graph.node):
        if any(output in required for output in node.output):
            retained.append(node)
            required.update(node.input)
    model.graph.ClearField("node")
    model.graph.node.extend(reversed(retained))
    tensors = [t for t in model.graph.initializer if t.name in required]
    model.graph.ClearField("initializer")
    model.graph.initializer.extend(tensors)
    onnx.checker.check_model(model)
    return len(produced)


def fold_constants_for_unreal(source, destination):
    """Use standard ONNX-only constant folding before UE's reduced ORT build.

    Its kernel set omits uint8 Equal used solely by constant identity matrices.
    BASIC folding removes these constants without introducing provider-specific
    fused operators. The complete resulting rollout is checked separately.
    """
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2] / "Saved/SlashPythonDependencies"))
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    options.optimized_model_filepath = str(destination)
    ort.InferenceSession(str(source), sess_options=options, providers=["CPUExecutionProvider"])
    model = onnx.load(destination)
    print("Shared identical export expressions:", share_identical_expressions(model), flush=True)
    onnx.save(model, destination)


if __name__ == "__main__":
    import sys
    model = onnx.load(sys.argv[1])
    print("Folded", fold_static_empty_tensors(model), "shape-proven empty tensors")
    onnx.save(model, sys.argv[2])
