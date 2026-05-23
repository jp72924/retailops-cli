"""
Global mutable CLI state, set once by the root Typer callback before
any subcommand runs. Each command module reads from here rather than
re-parsing global options.
"""

profile: str | None = None   # active config profile name
output: str = "table"        # table | json | csv | yaml
yes: bool = False            # skip confirmation prompts
verbose: bool = False        # print raw HTTP traffic to stderr
dry_run: bool = False        # mutating commands: preview the request, do not send
page_size: int = 25          # default page size for list commands
