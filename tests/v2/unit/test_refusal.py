"""The refusal report: everything a job config is refused for, in one list."""
import pytest

from src.v2.errors import JobRefusedError
from src.v2.job.refusal import Refusal, RefusalReport


def _report():
    report = RefusalReport(job_name="orders")
    report.add("component in_1 (FileInputDelimited)", "encoding", "only UTF-8 is read")
    report.add("job", "flows[2].type", "iterate flows are not supported")
    report.add("component in_1 (FileInputDelimited)", "delimeter", "unknown config key")
    return report


def test_empty_report_is_falsy_and_says_nothing_is_refused():
    report = RefusalReport(job_name="orders")
    assert not report
    assert report.format() == "Job 'orders': nothing refused."


def test_report_counts_and_iterates_its_refusals():
    report = _report()
    assert len(report) == 3
    assert [r.key for r in report] == ["encoding", "flows[2].type", "delimeter"]


def test_format_groups_refusals_under_their_owner_in_first_seen_order():
    assert _report().format() == (
        "Job 'orders' cannot run on v2: 3 problems.\n"
        "\n"
        "component in_1 (FileInputDelimited):\n"
        "  - encoding: only UTF-8 is read\n"
        "  - delimeter: unknown config key\n"
        "\n"
        "job:\n"
        "  - flows[2].type: iterate flows are not supported"
    )


def test_format_uses_the_singular_for_one_problem_and_omits_an_empty_key():
    report = RefusalReport(job_name="orders")
    report.add("job", "", "the job has no components")
    assert report.format() == (
        "Job 'orders' cannot run on v2: 1 problem.\n\njob:\n  - the job has no components"
    )


def test_extend_takes_refusals_from_a_check():
    report = RefusalReport(job_name="orders")
    report.extend([Refusal("job", "name", "missing")])
    assert len(report) == 1


def test_raise_if_refused_does_nothing_for_a_clean_report():
    RefusalReport(job_name="orders").raise_if_refused()


def test_raise_if_refused_raises_with_the_report_and_its_text():
    report = _report()
    with pytest.raises(JobRefusedError) as caught:
        report.raise_if_refused()
    assert caught.value.report is report
    assert str(caught.value) == report.format()
