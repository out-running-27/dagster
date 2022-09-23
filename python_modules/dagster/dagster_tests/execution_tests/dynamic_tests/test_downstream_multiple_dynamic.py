from dagster import op, job, DynamicOut, DynamicOutput

@op(
    out=DynamicOut()
)
def base_upstream(context):
    for i in range(5):
        context.log.info(f"base upstream yielding {i}")
        yield DynamicOutput(i, mapping_key=f"base_{i}")

@op(
    out=DynamicOut()
)
def multiplier_upstream(context):
    for i in range(5):
        context.log.info(f"multiplier upstream yielding {i}")
        yield DynamicOutput(i, mapping_key=f"multiply_by_{i}")

@op(
    out=DynamicOut()
)
def subtract_upstream(context):
    for i in range(5):
        context.log.info(f"subtract upstream yielding 2 for iter {i}")
        yield DynamicOutput(2, mapping_key=f"subtract_{i}")

@op(
    out={"base": DynamicOut(), "exp": DynamicOut()}
)
def yield_two_outs():
    for i in range(5):
        yield DynamicOutput(i, output_name="base", mapping_key=f"base_{i}")
        yield DynamicOutput(i+1, output_name="exp", mapping_key=f"exp_{i+1}")


@op
def upstream_combiner(context, base, multiplier):
    context.log.info(f"upstream combiner combining {base} and {multiplier}")
    return base * multiplier


@op
def multiply_and_subtract(context, base, multiplier, subtract):
    # use a non-commutative operation to test that the outputs get passed to the correct inputs
    return base * multiplier - subtract

@op
def compute_exponent(base, exponent):
    return base ** exponent

@op
def add_two(base):
    return base + 2

@op
def collect_two_and_sum(context, input_1, input_2):
    context.log.info(f"collector got inputs {input_1} and {input_2}")
    return sum([*input_1, *input_2])

@op
def collect_and_sum(context, inputs):
    context.log.info(f"collector got inputs {inputs}")
    return sum(inputs)

@job
def multiple_upstream_dynamic():
    bases = base_upstream()
    multipliers = multiplier_upstream()
    bases.map(upstream_combiner, zip_with=[multipliers])

@job
def zip_three_upstream_dynamic():
    bases = base_upstream()
    multipliers = multiplier_upstream()
    subtractors = subtract_upstream()
    bases.map(multiply_and_subtract, zip_with=[multipliers, subtractors])

@job
def zip_outputs_from_same_op():
    bases, exps = yield_two_outs()
    bases.map(compute_exponent, zip_with=[exps])

@job
def with_collect():
    bases = base_upstream()
    multipliers = multiplier_upstream()
    subtractors = subtract_upstream()
    res = bases.map(multiply_and_subtract, zip_with=[multipliers, subtractors])
    collect_and_sum(res.collect())


@job
def collect_two_dynamic_outputs():
    bases = base_upstream()
    multipliers = multiplier_upstream()
    collect_two_and_sum(bases.collect(), multipliers.collect())

@job
def basic_example():
    bases = base_upstream()
    added = bases.map(add_two)
    collect_and_sum(added.collect())

def test_multiple_upstream():
    result = multiple_upstream_dynamic.execute_in_process()
    assert list(result.output_for_node("upstream_combiner").values()) == [0, 1, 4, 9, 16]

def test_zip_three():
    result = zip_three_upstream_dynamic.execute_in_process()
    assert list(result.output_for_node("multiply_and_subtract").values()) == [-2, -1, 2, 7, 14]


def test_zip_outputs_from_same_op():
    result = zip_outputs_from_same_op.execute_in_process()
    assert list(result.output_for_node("compute_exponent").values()) == [0, 1, 8, 81, 1024]

def test_with_collect():
    result = with_collect.execute_in_process()
    assert result.output_for_node("collect_and_sum") == 20

def test_basic():
    result = basic_example.execute_in_process()

def test_collect_multi():
    result = collect_two_dynamic_outputs.execute_in_process()
    assert result.output_for_node("collect_two_and_sum") == 20


def notes():
    """
        Notes:
        - is zip_with is a bit weird because the list has to be in the order of the params to the function? no way to pass like kwargs
            - could switch to a dict and pass as kwargs in composition.map

        - should maybe rename resolve_step_key_output_name_mapping to something simpler
            - resolve_step_key_output_name_pairs - not shorter but not misleading as to datatype (it's not actually a dict)

        - make sure putting whitelist_for_serdes on the StepKeyOutputNamePair is ok

        - check for inconsistencies between use of resolution_sources (property) and get_resolution_sources() (function)

    """
