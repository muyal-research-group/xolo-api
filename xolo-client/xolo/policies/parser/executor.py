import sys
from xolo.policies.parser import build_parser
import pyparsing as pp

# class XoloExecutor:
#     """
#     The XoloExecutor holds the necessary context (client, secrets)
#     and executes a list of parsed commands.
#     """
#     def __init__(self, client, secret=None):
#         self.client = client
#         self.secret = secret
#         self.parser = build_parser()
        
#     def parse_script(self, script_text):
#         """Parses a full script and returns a list of command objects."""
#         try:
#             # parseAll=True ensures the entire script must match the grammar
#             return self.parser.parseString(script_text, parseAll=True)
#         except pp.ParseException as e:
#             print(f"--- PARSING FAILED ---", file=sys.stderr)
#             print(f"Error on line {e.lineno}, col {e.col}:", file=sys.stderr)
#             print(e.line, file=sys.stderr)
#             print(" " * (e.col - 1) + "^", file=sys.stderr)
#             print(e, file=sys.stderr)
#             return []
            
#     def execute_commands(self, commands):
#         """Executes a list of pre-parsed command objects."""
#         results = []
#         for cmd in commands:
#             try:
#                 result = cmd.execute(self)
#                 results.append(result)
#             except Exception as e:
#                 print(f"[FATAL] Unhandled error executing command {cmd}: {e}", file=sys.stderr)
#         return results