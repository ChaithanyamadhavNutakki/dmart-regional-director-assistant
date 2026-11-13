"""Answer assembly component.

Combines the fixed response templates with evidence and numeric grounding.
Calculation, synthesis, and grounding remain separate helpers so that each
stage can be inspected and maintained independently.
"""

from agent.synthesize import synthesize
from agent.ground import ground


def answer(
    *,
    interpretation,
    calculation_result=None,
    query_result=None,
    weather_result=None,
    synthesis_result=None,
    quoted_constants=None,
):
    """Build a final answer and attach source evidence and grounding metadata.

    When a prebuilt synthesis_result is supplied, it is grounded as-is. This
    supports validation failures and other explicit safe outcomes. Otherwise,
    the fixed answer templates synthesize the response from structured data.
    """
    if synthesis_result is None:
        synthesis_result = synthesize(
            calculation_result=calculation_result,
            interpretation=interpretation,
            query_result=query_result,
            weather_result=weather_result,
        )

    return ground(
        synthesis_result=synthesis_result,
        calculation_result=calculation_result,
        query_result=query_result,
        interpretation=interpretation,
        weather_result=weather_result,
        quoted_constants=quoted_constants,
    )
