from itertools import chain, zip_longest
from datetime import datetime
from threading import Lock

# helper function to parse strings with expressions
def parse_exprs(expr_str):
    if type(expr_str) != str:
        out_msg = str(expr_str)
    else:
        # parse all instances of ${...} in expr
        # watching out for nested parentheses
        to_parse = expr_str
        out_msg = ""
        while to_parse != "":
            idx = to_parse.find("${")
            if idx == -1: # if no expr to eval
                out_msg += to_parse
                break
            out_msg += to_parse[:idx]
            idx += 2
            if idx < len(to_parse):
                paren_lvl = 0
                found = False
                # sort through nested brackets to find the full expression
                for i in range(idx, len(to_parse)):
                    if to_parse[i] == "{":
                        paren_lvl += 1
                    elif to_parse[i] == "}":
                        if paren_lvl == 0:
                            # found the end of the expr
                            found = True
                            try:
                                evaluated = eval(to_parse[idx:i])
                            except SyntaxError:
                                out_msg += "(Invalid Expr)"
                            except Exception as e:
                                out_msg += "(Eval Error: {})".format(e)
                            else:
                                out_msg += str(evaluated)
                            to_parse = to_parse[i+1:]
                            break
                        else:
                            paren_lvl -= 1
                if not found:
                    raise Exception("Invalid expression: {}".format(expr_str))
    return out_msg

class Log4py:
    def __init__(self, log_file, date_format="%Y-%m-%d %H:%M:%S"):
        self.log_file = log_file
        self.date_format = date_format
        self.file_lock = Lock()

    def log(self, *msgs):
        base_str = parse_exprs(msgs[0])
        expr_strs = msgs[1:]
        # look for "{}" in base_str and replace with expr_strs
        tokenized = base_str.split("{}")
        evaled = [str(parse_exprs(s)) for s in expr_strs]
        message = "".join([s for s in chain(*zip_longest(tokenized, evaled)) if s is not None])

        # add timestamp
        time_str = f'[{datetime.now().strftime(self.date_format)}]'

        log_msg = f'{time_str} {message}\n'

        with self.file_lock:
            with open(self.log_file, "a") as f:
                f.write(log_msg)
            print(log_msg, end="")

    def log_dump(self):
        with self.file_lock:
            with open(self.log_file, "r") as f:
                return f.read()