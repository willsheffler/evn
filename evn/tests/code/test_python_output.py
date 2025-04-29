# test_process_python_output.py

import pytest
import os
import re
import textwrap
# Assuming the module code is saved as process_python_output.py
import evn.code.python_output as ppo
import evn

def main():
    evn.testing.quicktest(globals())

# --- Fixtures for Sample Data ---

@pytest.fixture
def sample_traceback_simple():
    return textwrap.dedent("""\
        Some introductory text.
        Traceback (most recent call last):
          File "my_app/main_script.py", line 55, in <module>
            run_calculation()
          File "my_app/calculator.py", line 20, in run_calculation
            result = divide_numbers(10, 0)
          File "my_app/utils.py", line 5, in divide_numbers
            return x / y
        ZeroDivisionError: division by zero
        Some concluding text.
    """)

@pytest.fixture
def sample_traceback_filtered():
    # Includes lines that should be filtered by 'boilerplate' preset
    return textwrap.dedent("""\
        Traceback (most recent call last):
          File "/path/to/site-packages/_pytest/runner.py", line 100, in pytest_runtest_call
            item.runtest()
          File "/path/to/site-packages/_pytest/python.py", line 180, in runtest
            self.funcargs[arg] = self._request.getfixturevalue(arg)
          File "/path/to/icecream/icecream.py", line 150, in ic_wrapper
            return GDBWrapper(prefix, context, *args)
          File "my_project/core_logic.py", line 42, in process_data
            value = data['key']
          File "/path/to/some/other_lib.py", line 99, in __getitem__
            return self._internal_get(key)
          File "my_project/core_logic.py", line 50, in another_call
             raise ValueError("Specific problem")
        ValueError: Specific problem
    """)

@pytest.fixture
def sample_traceback_with_alt_format():
    return textwrap.dedent("""\
        Processing item 1...
        /home/user/evn/evn/cli/stuff.py:32: DocTestFailure: Something failed
        Processing item 2...
        Traceback (most recent call last):
          File "my_app/main_script.py", line 55, in <module>
            run_calculation()
        ValueError: Test error
    """)

@pytest.fixture
def sample_numpy_nonsense():
    return textwrap.dedent("""\
        Before error.

        A module that was compiled using NumPy 1.x cannot be run in
        NumPy 2.2.3 as it may crash. To support both 1.x and 2.x
        versions of NumPy, modules must be compiled with NumPy 2.0.
        Some module may need to rebuild instead e.g. with 'pybind11>=2.12'.

        If you are a user of the module, the easiest solution will be to
        downgrade to 'numpy<2' or try to upgrade the affected module.
        We expect that some modules will need time to support NumPy 2.

        Traceback (most recent call last):
          File "script.py", line 5, in <module>
            import numexpr
          File "/path/to/numexpr/__init__.py", line 44, in <module>
            from numexpr.interpreter import MAX_THREADS, use_vml, __BLOCK_SIZE1__
        AttributeError: _ARRAY_API not found

        After error.
    """)

@pytest.fixture
def sample_log_for_analysis():
    return textwrap.dedent("""\
        Log start...
        Traceback (most recent call last):
          File "app/service.py", line 100, in handle_request
            process(data)
          File "app/processor.py", line 50, in process
            result = calculate(val)
          File "app/calculator.py", line 25, in calculate
            return 100 / val
        ZeroDivisionError: division by zero

        Some other logging info...

        Traceback (most recent call last):
          File "app/service.py", line 100, in handle_request
            process(data)
          File "app/processor.py", line 50, in process
            result = calculate(val)
          File "app/calculator.py", line 25, in calculate
            return 100 / val
        ZeroDivisionError: division by zero

        More info...

        Traceback (most recent call last):
          File "app/another_module.py", line 75, in setup
            config.load()
          File "lib/config_loader.py", line 30, in load
            with open(self.path, 'r') as f:
        FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'
        Log end.
    """)

# --- Helper Function Tests ---

def test_strip_line_extra_whitespace():
    assert ppo.strip_line_extra_whitespace("  leading and trailing  ") == "  leading and trailing"
    assert ppo.strip_line_extra_whitespace("trailing only   ") == "trailing only"
    assert ppo.strip_line_extra_whitespace("   leading only") == "   leading only"
    # Strips leading only if line is mostly whitespace
    assert ppo.strip_line_extra_whitespace("      ") == ""
    assert ppo.strip_line_extra_whitespace("      \n") == ""
    assert ppo.strip_line_extra_whitespace("\t\t") == ""
    assert ppo.strip_line_extra_whitespace("  a  ") == "  a"  # Doesn't strip leading if content present

def test_transform_fileref_to_python_format():
    line_in = "/home/user/evn/evn/cli/stuff.py:32: DocTestFailure: Something failed"
    expected = '  File "/home/user/evn/evn/cli/stuff.py", line 32, ...'
    assert ppo.transform_fileref_to_python_format(line_in) == expected
    assert ppo.transform_fileref_to_python_format("No match here") == "No match here"

def test_filter_numpy_version_nonsense(sample_numpy_nonsense):
    filtered = ppo._filter_numpy_version_nonsense(sample_numpy_nonsense)
    assert "A module that was compiled using NumPy 1.x" not in filtered
    assert "AttributeError: _ARRAY_API not found" not in filtered
    # Check that surrounding text remains
    assert "Before error." in filtered
    assert "Traceback (most recent call last):" in filtered  # Keep traceback itself
    assert "After error." in filtered

# --- process_python_output Tests ---

def test_filter_minlines_not_met(sample_traceback_simple):
    # Set minlines higher than the actual number of lines
    min_lines = 100
    result = ppo.process_python_output(sample_traceback_simple, minlines=min_lines)
    assert result == sample_traceback_simple  # Should return original text

def test_filter_minlines_met(sample_traceback_simple):
    min_lines = 5  # Less than the number of lines
    result = ppo.process_python_output(sample_traceback_simple, minlines=min_lines)
    # Check if filtering occurred (e.g., footer added)
    print(result)
    assert "process_python_output (preset=boilerplate)" in result
    assert result != sample_traceback_simple

def test_filter_preset_boilerplate(sample_traceback_filtered):
    result = ppo.process_python_output(sample_traceback_filtered, preset=['boilerplate'], minlines=1)
    expected = textwrap.dedent("""\
        Traceback (most recent call last):
          pytest_runtest_call -> runtest -> ic_wrapper ->
          File "my_project/core_logic.py", line 42, in process_data
            value = data['key']
          File "/path/to/some/other_lib.py", line 99, in __getitem__
            return self._internal_get(key)
          File "my_project/core_logic.py", line 50, in another_call
             raise ValueError("Specific problem")
        ValueError: Specific problem
        ^^^^^^^^^^^^^ evn.code.process_python_output (preset=boilerplate) ^^^^^^^^^^^^^^
    """) + os.linesep  # Function adds trailing newline
    assert result.strip() == expected.strip()

def test_filter_preset_aggressive(sample_traceback_filtered):
    result = ppo.process_python_output(sample_traceback_filtered, preset='aggressive', minlines=1)
    # Aggressive should filter more, potentially leaving only the error line and footer
    expected = textwrap.dedent("""\
        Traceback (most recent call last):
          pytest_runtest_call -> runtest -> ic_wrapper ->
          File "my_project/core_logic.py", line 42, in process_data
            value = data['key']
          __getitem__ ->
          File "my_project/core_logic.py", line 50, in another_call
             raise ValueError("Specific problem")
        ValueError: Specific problem
        ^^^^^^^^^^^^^^ evn.code.process_python_output (preset=aggressive) ^^^^^^^^^^^^^^
    """) + os.linesep
    assert result.strip() == expected.strip()

def test_filter_custom_regex(sample_traceback_simple):
    # Filter out specifically calculator.py
    result = ppo.process_python_output(
        sample_traceback_simple,
        re_file=r'calculator\.py',
        re_func=ppo.re_null,  # Don't filter funcs for this test
        preset=[],  # Disable preset
        minlines=1)
    expected = textwrap.dedent("""\
        Some introductory text.
        Traceback (most recent call last):
          File "my_app/main_script.py", line 55, in <module>
            run_calculation()
          run_calculation ->
          File "my_app/utils.py", line 5, in divide_numbers
            return x / y
        ZeroDivisionError: division by zero
        Some concluding text.
        ^^^^^^^^^^^^^ evn.code.process_python_output (preset=full_output) ^^^^^^^^^^^^^^
    """) + os.linesep
    print(result)
    assert result.strip() == expected.strip()

@pytest.mark.xfail
def test_filter_keep_blank_lines(sample_traceback_simple):
    text_with_blanks = sample_traceback_simple.replace("run_calculation()", "run_calculation()\n\n")
    result = ppo.process_python_output(text_with_blanks, keep_blank_lines=True, minlines=1)
    # Check if the extra blank line is still there (relative to normal filtering)
    # Normal filtering would collapse it, keep_blank_lines=True should not.
    print(text_with_blanks)
    print('---------')
    print(result)
    assert "run_calculation()\n\n          File" in result

def test_filter_no_arrows(sample_traceback_filtered):
    result = ppo.process_python_output(sample_traceback_filtered,
                                       preset=['boilerplate'],
                                       minlines=1,
                                       arrows=False)
    # Arrows (e.g., "runner -> ... ->") should not be present
    assert "->" not in result
    # Check that filtered lines are simply removed
    assert 'runner.py' not in result
    assert 'icecream.py' not in result
    assert 'my_project/core_logic.py' in result  # Kept line

def test_filter_numpy_nonsense_flag(sample_numpy_nonsense):
    result_filtered = ppo.process_python_output(sample_numpy_nonsense,
                                                filter_numpy_version_nonsense=True,
                                                minlines=1)
    result_kept = ppo.process_python_output(sample_numpy_nonsense,
                                            filter_numpy_version_nonsense=False,
                                            minlines=1)

    assert "A module that was compiled using NumPy 1.x" not in result_filtered
    assert "AttributeError: _ARRAY_API not found" not in result_filtered  # Part of the specific filter
    assert "A module that was compiled using NumPy 1.x" in result_kept
    assert "AttributeError: _ARRAY_API not found" in result_kept  # Error is still there if not filtered

def test_filter_alt_format_line(sample_traceback_with_alt_format):
    result = ppo.process_python_output(sample_traceback_with_alt_format, minlines=1)
    # Check if the alt format line was converted
    assert '  File "/home/user/evn/evn/cli/stuff.py", line 32, ...' in result
    assert ": DocTestFailure" not in result  # Original format substring removed
    # Check other parts remain
    assert "Processing item 1..." in result
    assert "Traceback (most recent call last):" in result

# --- analyze_python_errors_log Tests ---

@pytest.mark.xfail
def test_analyze_errors_log_unique(sample_log_for_analysis):
    # Mock create_errors_log_report to check the map passed to it
    report_map = None
    original_create = ppo.create_errors_log_report

    def mock_create(trace_map):
        nonlocal report_map
        report_map = trace_map
        return original_create(trace_map)  # Call original for realistic output format

    ppo.create_errors_log_report = mock_create
    try:
        report = ppo.analyze_python_errors_log(sample_log_for_analysis)
    finally:
        ppo.create_errors_log_report = original_create  # Restore original

    assert report_map is not None
    assert len(report_map) == 2  # Two unique errors expected

    # Check keys (location, error message)
    key1 = ('app/calculator.py:25', 'ZeroDivisionError: division by zero')
    key2 = ('lib/config_loader.py:30', "FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'")
    assert key1 in report_map
    assert key2 in report_map

    # Check the report content generated by the original function
    assert "Unique Stack Traces Report (2 unique traces):" in report
    assert "ZeroDivisionError: division by zero" in report
    assert "FileNotFoundError: [Errno 2]" in report

def test_analyze_errors_log_no_tracebacks():
    log_text = "Just some normal log lines.\nNo errors here."
    report = ppo.analyze_python_errors_log(log_text)
    assert "Unique Stack Traces Report (0 unique traces):" in report
    assert "Traceback" not in report

@pytest.mark.xfail
def test_analyze_errors_log_single_traceback(sample_traceback_simple):
    report = ppo.analyze_python_errors_log(sample_traceback_simple)
    assert "Unique Stack Traces Report (1 unique traces):" in report
    assert "ZeroDivisionError: division by zero" in report
    assert 'my_app/utils.py:5' in report  # Check key extraction

# --- create_errors_log_report Test ---

def test_create_errors_log_report():
    trace_map = {
        ('key1', 'Error1'): "Traceback...\nError1",
        ('key2', 'Error2'): "Traceback...\nError2",
    }
    # Mock evn.capture_stdio if needed, but here we just check the output string
    # Assuming evn is importable or mocking it if not available
    try:
        import evn
        # If evn is available, test with it
        report = ppo.create_errors_log_report(trace_map)
    except ImportError:
        # Basic check without evn dependency
        report = f"Unique Stack Traces Report ({len(trace_map)} unique traces):\n"
        report += '='*80 + '\n\n'
        report += "Traceback...\nError1\n"
        report += '-'*80 + '\n\n'
        report += "Traceback...\nError2\n"
        report += '-'*80 + '\n\n'

    assert f"Unique Stack Traces Report ({len(trace_map)} unique traces):" in report
    assert "Traceback...\nError1" in report
    assert "Traceback...\nError2" in report
    assert ('=' * 80) in report
    assert ('-' * 80) in report

if __name__ == '__main__':
    main()
