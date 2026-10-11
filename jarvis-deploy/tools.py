"""Tool registry. Add a tool = write a function + one entry in TOOLS."""
import ast
import datetime
import operator


def _safe_eval(expr):
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        raise ValueError("unsupported expression")

    return ev(ast.parse(expr, mode="eval").body)


def build_tools(memory):
    def get_time():
        return datetime.datetime.now().strftime("%A, %d %B %Y, %H:%M")

    def calculate(expression):
        try:
            return str(_safe_eval(expression))
        except Exception as e:
            return f"error: {e}"

    def remember(topic, fact):
        memory.remember(topic, fact)
        return "saved"

    def recall(query=""):
        return memory.recall(query) or "nothing found"

    def spec(name, desc, props, required):
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {"type": "object", "properties": props, "required": required},
            },
        }

    s = {"type": "string"}
    schemas = [
        spec("get_time", "Get the current local date and time.", {}, []),
        spec("calculate", "Evaluate an arithmetic expression.", {"expression": s}, ["expression"]),
        spec("remember", "Save a durable fact about the user or their world.",
             {"topic": s, "fact": s}, ["topic", "fact"]),
        spec("recall", "Search saved facts by keyword (empty = most recent).", {"query": s}, []),
    ]
    funcs = {"get_time": get_time, "calculate": calculate, "remember": remember, "recall": recall}
    return schemas, funcs
