from kb.query.facts import is_fact, trim_secondary, states


def fact(i, text, doc="a"):
    return {"id": f"F{i}", "text": text, "doc_id": doc}


def test_results_limits_and_conditions_are_facts_but_background_is_not():
    assert is_fact("For the Chebyshev Tensors built in the direct way, a mesh of 14 _,_ 400 points was used.")
    assert is_fact("The evaluation time was measured at 2 milliseconds per evaluation (in Matlab).")
    assert is_fact("Out of these, only 20 _,_ 000 were randomly chosen to be evaluated.")
    assert is_fact("They were obtained using a standard PC computer, with _i_ 7 cores; no parallelisation nor GPUs were used.")
    assert is_fact("Chebyshev Tensors do not extrapolate outside the domain.")
    assert not is_fact("A grid of 7 points per dimension was chosen for the Chebyshev Tensor.")
    assert not is_fact("Section 3 describes the method in detail.")


def test_setup_presentation_and_same_figure_repeats_are_trimmed_but_other_cases_stay():
    facts = [fact(1, "From the 10,000 grid points evaluated, 8,000 were used for training and 2,000 for testing."),
             fact(2, "The 1,000 parameter combinations were obtained by randomly sampling the parameter domain."),
             fact(3, "The vertical line on both plots corresponds to the 99% quantile."),
             fact(4, "Calibration with the tensor is around 40,000 times faster than the pricing function."),
             fact(5, "As a result, calibration via the tensor is around 40,000 times faster than the original pricing function."),
             fact(6, "The evaluation time for the TT-format tensor, in Matlab, was 1 millisecond."),
             fact(7, "The evaluation time of the TT-format tensor was measured at 2 milliseconds per evaluation in Matlab."),
             fact(8, "Therefore, it is preferable to use optimisation algorithms that admit domain restrictions."),
             fact(9, "Bank B calibration is around 40,000 times faster than the pricing function.", doc="b")]
    kept, trimmed = trim_secondary(facts)
    assert [f["id"] for f, _ in trimmed] == ["F1", "F2", "F3", "F5"]
    assert [why for _, why in trimmed] == ["train/test split", "procedure", "plot description", "repeat of F4"]
    # A second case with other figures (1 ms vs 2 ms), the source's own guidance and another document's figure stay.
    assert {"F6", "F7", "F8", "F9"} <= {f["id"] for f in kept}


def test_a_statement_carries_a_fact_only_with_all_its_figures():
    f = fact(1, "The maximum rank of the TT-format Chebyshev Tensor was 12 and its memory footprint 20 KB.")
    assert states("The TT tensor had maximum rank 12 and a 20 KB footprint.", f)
    assert not states("The TT tensor had a 20 KB footprint.", f)
