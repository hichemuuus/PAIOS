from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from veyron.core.evaluator import EvalTask


@dataclass
class BenchmarkTask:
    task: EvalTask
    difficulty: str = "basic"
    expected_behavior: str = "success"
    failure_type: str = ""
    tags: list[str] = field(default_factory=list)


FILESYSTEM_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("fs_ls", "List all files in the current directory", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_read_config", "Read the file config.yaml", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_readme", "Show me the contents of README.md", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_find_py", "Find all python files in the project", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_count_lines", "Count lines in all .py files in the backend directory", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("fs_file_size", "What is the size of the file backend/veyron/__init__.py", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_list_dirs", "List all directories in the current folder", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_search_todo", "Search for TODO in all source files", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("fs_check_init", "Read backend/veyron/__init__.py and tell me what it exports", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_find_deprecated", "Search for files containing the word deprecated", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("fs_ls_recursive", "List all files recursively in the backend directory", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("fs_count_py_files", "How many python files are in the project", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("fs_check_version", "Read pyproject.toml and tell me the project version", category="filesystem", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
]

SYSTEM_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("sys_cpu", "What is the current CPU usage", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_memory", "Show me the current memory usage", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_disk", "Check the disk space on the current drive", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_processes", "List the top 5 running processes by CPU usage", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_uptime", "How long has the system been running", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_network", "Show network statistics", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_health", "Give me a system health overview", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_cpu_cores", "How many CPU cores are available", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_overview", "Get a complete system overview: CPU, memory, and disk", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("sys_memory_percent", "What percentage of RAM is in use", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_disk_c", "Show disk usage for the C drive", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_temp", "What is the current system temperature", category="system_monitor", expected_tools=["system_monitor"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("sys_username", "What is my username", category="system_monitor", expected_tools=["system_monitor", "terminal"], min_steps=1, max_steps=5)),
]

TERMINAL_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("term_echo", 'Run the command: echo "hello world"', category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_python_version", "Run python --version", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_whoami", "Run whoami", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_date", "Run the date command", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_env_vars", "List all environment variables", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("term_pwd", "Run the pwd command", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_hostname", "Run hostname", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_uname", "Run uname -a", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_pip_list", "List installed pip packages", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("term_dir", "Run the dir command", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_which_python", "Find where python is installed", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("term_echo_args", 'Run: echo "first" "second" "third"', category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=3)),
    BenchmarkTask(EvalTask("term_git_status", "Run git status", category="terminal", expected_tools=["terminal"], min_steps=1, max_steps=5, expected_outcome="git status output")),
]

CODING_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("code_find_imports", "Find all import statements in the Python files", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_find_syntax", "Check for syntax errors in the backend source code", category="coding", expected_tools=["filesystem_read", "terminal"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_todo_count", "Count how many TODO comments exist in the codebase", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_func_count", "Count how many function definitions are in the agent.py file", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("code_class_count", "How many classes are defined in the project", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_find_type_hints", "Find all files that lack type hints", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_line_count", "Count the total lines of Python code in the project", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_find_dead_code", "Search for functions that are defined but never called", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("code_docstring_ratio", "What percentage of functions have docstrings", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("code_find_error_handling", "Find all try/except blocks in the codebase", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("code_list_async_funcs", "List all async functions in the agent module", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("code_find_test_files", "Find all test files in the project", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("code_count_test_funcs", "Count the number of test functions", category="coding", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
]

ANALYSIS_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("proj_structure", "Analyze the project structure and tell me the main directories", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("proj_deps", "What dependencies does this project use", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("proj_summary", "Give me a summary of what this project does", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("proj_arch", "Describe the architecture of this project", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("proj_entry_points", "What are the main entry points of this application", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("proj_config_files", "Find all configuration files in the project", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("proj_module_deps", "Analyze the dependency graph between modules", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("proj_test_coverage", "Analyze test coverage: which modules have tests", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("proj_version_info", "What version is this project and what are its key features", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=8)),
    BenchmarkTask(EvalTask("proj_code_quality", "Evaluate the code quality of this project", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("proj_find_main", "Find the main module that starts the application", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
    BenchmarkTask(EvalTask("proj_readme_summary", "Read the README and summarize the installation steps", category="project_analysis", expected_tools=["filesystem_read"], min_steps=1, max_steps=5)),
]

MULTI_STEP_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("multi_find_and_count", "Find all python files, count their lines, and sort by size", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_disk_and_files", "Check disk usage, find the largest files, and list the top 3", category="multi_step", expected_tools=["system_monitor", "filesystem_read"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_system_and_analysis", "Check CPU and memory, then analyze if the system is overloaded", category="multi_step", expected_tools=["system_monitor"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_read_and_describe", "Read the main source files and describe how the agent works", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_cpu_twice", "Check CPU usage twice with a delay and report if it changed", category="multi_step", expected_tools=["system_monitor", "system_monitor"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_dir_cpu_mem", "List the current directory, check CPU, check memory, then summarize", category="multi_step", expected_tools=["filesystem_read", "system_monitor", "system_monitor"], min_steps=3, max_steps=12)),
    BenchmarkTask(EvalTask("multi_find_read_summarize", "Find the main config file, read it, and summarize its contents", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=8)),
    BenchmarkTask(EvalTask("multi_project_overview", "List the project structure, find the main entry point, and read its docstring", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_perf_analysis", "Check CPU, memory, and disk, then identify which resource is most constrained", category="multi_step", expected_tools=["system_monitor"], min_steps=3, max_steps=10)),
    BenchmarkTask(EvalTask("multi_code_audit", "Find all python files, count TODO comments, and calculate the TODO density", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_dep_analysis", "Read pyproject.toml, list the dependencies, and categorize them by type", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=10)),
    BenchmarkTask(EvalTask("multi_error_recovery", "Read a nonexistent file, then read a real file as fallback", category="multi_step", expected_tools=["filesystem_read"], min_steps=1, max_steps=8), expected_behavior="recovery"),
    BenchmarkTask(EvalTask("multi_system_full", "Get CPU, memory, disk, and processes in one comprehensive report", category="multi_step", expected_tools=["system_monitor"], min_steps=4, max_steps=12)),
    BenchmarkTask(EvalTask("multi_src_analysis", "Read all source files in the core module and summarize the key classes", category="multi_step", expected_tools=["filesystem_read"], min_steps=2, max_steps=12)),
    BenchmarkTask(EvalTask("multi_compare_metrics", "Check CPU and memory three times and tell me if there are trends", category="multi_step", expected_tools=["system_monitor"], min_steps=3, max_steps=12)),
]

MEMORY_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("mem_store_recall", "Remember that my name is Alice. Then recall my name.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_project_ref", "Remember that the project version is 2.0. Later, what is the version", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_tool_output", "Remember the output of the last command. Then recall it.", category="memory", expected_tools=["terminal"], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_multi_facts", "Remember that the API key is stored in config and the DB is SQLite. Then recall both.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_conversation", "Tell me you will remember my preference for dark mode. Then recall it.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_code_style", "Remember that I prefer tabs over spaces. Then recall my preference.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_project_path", "Remember the project path. Then recall it later.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_test_framework", "Remember that we use pytest. Then tell me what framework we use.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_file_location", "Remember that the log file is at /var/log/app.log. Recall it.", category="memory", expected_tools=[], min_steps=1, max_steps=10)),
    BenchmarkTask(EvalTask("mem_build_command", 'Remember the build command is "python setup.py build". Recall it.', category="memory", expected_tools=[], min_steps=1, max_steps=10)),
]

AMBIGUOUS_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(EvalTask("amb_check_system", "Check the system", category="ambiguous", expected_tools=["system_monitor"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_whats_happening", "What's going on with the system", category="ambiguous", expected_tools=["system_monitor"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_tell_me", "Tell me about this project", category="ambiguous", expected_tools=["filesystem_read"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_analyze", "Analyze this", category="ambiguous", expected_tools=["filesystem_read"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_check_it", "Check it", category="ambiguous", expected_tools=[], min_steps=1, max_steps=5), expected_behavior="clarify"),
    BenchmarkTask(EvalTask("amb_show_status", "Show status", category="ambiguous", expected_tools=["system_monitor"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_run_diagnostics", "Run diagnostics", category="ambiguous", expected_tools=["system_monitor"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_how_are_you", "How are you doing today", category="ambiguous", expected_tools=[], min_steps=1, max_steps=3), expected_behavior="conversation"),
    BenchmarkTask(EvalTask("amb_what_can_you_do", "What can you do", category="ambiguous", expected_tools=[], min_steps=1, max_steps=3), expected_behavior="conversation"),
    BenchmarkTask(EvalTask("amb_fix_it", "Fix it", category="ambiguous", expected_tools=[], min_steps=1, max_steps=5), expected_behavior="clarify"),
    BenchmarkTask(EvalTask("amb_help_me", "Help me understand the codebase", category="ambiguous", expected_tools=["filesystem_read"], min_steps=1, max_steps=8), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_improve_perf", "Improve performance", category="ambiguous", expected_tools=["system_monitor", "filesystem_read"], min_steps=1, max_steps=10), expected_behavior="disambiguate"),
    BenchmarkTask(EvalTask("amb_check_everything", "Check everything", category="ambiguous", expected_tools=["system_monitor"], min_steps=1, max_steps=5), expected_behavior="disambiguate"),
]

ALL_TASKS: list[BenchmarkTask] = (
    FILESYSTEM_TASKS
    + SYSTEM_TASKS
    + TERMINAL_TASKS
    + CODING_TASKS
    + ANALYSIS_TASKS
    + MULTI_STEP_TASKS
    + MEMORY_TASKS
    + AMBIGUOUS_TASKS
)

CATEGORY_MAP: dict[str, str] = {
    "filesystem": "filesystem",
    "system_monitor": "system_monitor",
    "terminal": "terminal",
    "coding": "coding",
    "project_analysis": "project_analysis",
    "multi_step": "multi_step",
    "memory": "memory",
    "ambiguous": "ambiguous",
}


def get_tasks_by_category(category: str | None = None) -> list[BenchmarkTask]:
    if category is None:
        return ALL_TASKS
    return [t for t in ALL_TASKS if t.task.category == category]


def get_task_by_id(task_id: str) -> BenchmarkTask | None:
    for t in ALL_TASKS:
        if t.task.id == task_id:
            return t
    return None


def summary() -> dict[str, Any]:
    by_cat: dict[str, int] = {}
    for t in ALL_TASKS:
        by_cat[t.task.category] = by_cat.get(t.task.category, 0) + 1
    return {
        "total": len(ALL_TASKS),
        "by_category": by_cat,
        "categories": list(by_cat.keys()),
    }
